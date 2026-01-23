import logging
import numpy as np
from typing import List, Dict, Optional, Tuple
from qdrant_client import QdrantClient
from qdrant_client.http import models

# Import your existing connector
from src.database.graph_db import Neo4jConnector
from src.config import config

class WorldKnowledgeService:
    """
    The interface between the Runtime Simulation (The Ant Farm) 
    and the Static Data (Neo4j + Qdrant).
    """
    def __init__(self):
        # Re-use existing config connections
        self.neo4j = Neo4jConnector(
            uri=config.neo4j.uri,
            user=config.neo4j.user,
            password=config.neo4j.password
        )
        self.qdrant = QdrantClient(url=config.qdrant.url)
        self.vector_size = config.v_size

    def close(self):
        self.neo4j.close()

    # =========================================================================
    # 1. THE LOADER (Scene Initialization)
    # Reference: 
    # =========================================================================

    def load_scene_snapshot(self, location_id: str) -> List[Dict]:
        """
        Loads all entities in a location + their Qdrant Vectors.
        Returns a list of 'RuntimeEntity' dicts ready for simulation.
        """
        # A. Get Topology & Basic Stats from Neo4j
        graph_entities = self.neo4j.get_molecules_in_location(location_id)
        
        if not graph_entities:
            logging.warning(f"Location {location_id} is empty.")
            return []

        # B. Get Vectors from Qdrant (Batch Fetch)
        ids = [e['id'] for e in graph_entities]
        
        # We fetch from 'molecules' collection (Dynamic World State)
        vectors = self.qdrant.retrieve(
            collection_name="molecules",
            ids=ids,
            with_vectors=True,
            with_payload=True 
        )
        
        # Create a lookup map for vectors
        vec_map = {pt.id: pt.vector for pt in vectors}
        payload_map = {pt.id: pt.payload for pt in vectors}

        # C. Merge Data
        snapshot = []
        for ge in graph_entities:
            uid = ge['id']
            if uid in vec_map:
                # Combine Graph Stats (Current) with Vector (Immutable semantic soul)
                entity_data = {
                    "id": uid,
                    "name": ge['name'],
                    "category": ge['category'],
                    # Current Stats (Mutable)
                    "stats": {
                        "material": ge.get('material', 0),
                        "vitality": ge.get('vitality', 0),
                        "social": ge.get('social', 0),
                        "cognitive": ge.get('cognitive', 0),
                    },
                    # Vector for "Physics" calculations
                    "vector": vec_map[uid],
                    # Extra metadata from payload
                    "subtype": payload_map[uid].get('subtype')
                }
                snapshot.append(entity_data)
        
        return snapshot

    # =========================================================================
    # 2. THE RESOLVER SUPPORT (Vector Physics)
    # Reference: 
    # =========================================================================

    def find_compatible_mechanics(self, entity_vector: List[float], top_k: int = 3) -> List[Dict]:
        """
        Level 1 Physics: "What can this object/person DO?"
        Searches 'ontology_static' (Verbs) for mechanics close to the entity's nature.
        
        Example: 
        - Input: Vector of 'Rusty Sword'
        - Output: Verb 'Slash' (High Match), Verb 'Break' (Medium Match)
        """
        result = self.qdrant.query_points(
            collection_name="ontology_static",
            query=entity_vector,
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="doc_type",
                        match=models.MatchValue(value="verb")
                    )
                ]
            ),
            limit=top_k
        )
        hits = result.points
        
        mechanics = []
        for hit in hits:
            mechanics.append({
                "verb_name": hit.payload.get("name"),
                "score": hit.score,
                "stats": hit.payload.get("stats", {}) # e.g. material_cost, damage_mod
            })
        return mechanics

    def find_best_verb(self, query_vector: List[float], top_k: int = 3) -> Optional[Dict]:
        """
        Ищет наиболее подходящий Глагол (Verb) в онтологии.
        Возвращает payload с готовыми статами.
        """
        hits = self.qdrant.search(
            collection_name="ontology_static",
            query_vector=query_vector,
            query_filter=models.Filter(
                must=[models.FieldCondition(key="doc_type", match=models.MatchValue(value="verb"))]
            ),
            limit=top_k
        )
        if not hits:
            return None
            
        # Возвращаем лучший матч (или можно добавить стохастику здесь)
        best = hits[0]
        return {
            "id": best.id,
            "name": best.payload.get("name"),
            "stats": best.payload.get("stats", {}), # Material, Vitality, etc.
            "score": best.score
        }

    def apply_interaction_physics(self, 
                                  target_entity: Dict, 
                                  verb_data: Dict, 
                                  intent_multiplier: float) -> Dict:
        """
        Главная физика мира.
        Применяет статы Глагола к статам Сущности с учетом Намерения.
        
        target_entity: Словарь сущности (snapshot)
        verb_data: Payload глагола (из find_best_verb)
        intent_multiplier: 
             +1.0 (Cooperation/Buff)
             -1.0 (Conflict/Damage)
             0.5 (Learning/Modification)
        """
        current_stats = target_entity['stats'].copy()
        effect_stats = verb_data['stats'] # Например: {"vitality": 0.8, "social": 0.1}
        
        updated_stats = {}
        log_changes = []

        # Константа "Силы воздействия" (чтобы одно событие не меняло мир слишком резко)
        IMPACT_FACTOR = 0.15 

        for axis in ["material", "vitality", "social", "cognitive"]:
            curr_val = current_stats.get(axis, 0.0)
            
            # Сила эффекта по этой оси (от 0 до 1)
            effect_val = effect_stats.get(axis, 0.0)
            
            # Формула: New = Old + (Effect * Impact * Sign)
            delta = effect_val * IMPACT_FACTOR * intent_multiplier
            
            new_val = curr_val + delta
            
            # Clamping (0.0 - 1.0)
            new_val = max(0.0, min(1.0, new_val))
            
            updated_stats[axis] = round(new_val, 3)
            
            if abs(delta) > 0.01:
                log_changes.append(f"{axis[:3].upper()}{'+' if delta>0 else ''}{delta:.2f}")

        return updated_stats, ", ".join(log_changes)

    def calculate_interaction_outcome(self, 
                                      source_vec: List[float], 
                                      target_vec: List[float]) -> float:
        """
        Simple cosine similarity for Level 1 'Brownian Motion'.
        If score > 0.7 -> Attraction (Merge/Trade).
        If score < 0.3 -> Repulsion (Conflict/Bounce).
        """
        # Manual cosine similarity if not using numpy
        a = np.array(source_vec)
        b = np.array(target_vec)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

    # =========================================================================
    # 3. STATE PERSISTENCE
    # Reference: 
    # =========================================================================

    def update_entity_state(self, entity_id: str, new_stats: Dict[str, float]):
        """
        Saves the results of a simulation tick back to the DB.
        Only updates Neo4j (Graph state), assuming Vectors don't change often.
        """
        # 1. Update Graph Properties (Fast lookup)
        # We reuse upsert_molecule but only with stats
        # Note: You might want to create a dedicated 'update_stats' method in graph_db.py 
        # to avoid overwriting names/links, but upsert works if ID matches.
        
        # Here we do a lightweight Cypher update for speed
        query = """
        MATCH (m:Molecule {id: $mid})
        SET m.val_material  = $mat,
            m.val_vitality  = $vit,
            m.val_social    = $soc,
            m.val_cognitive = $cog,
            m.last_updated = timestamp()
        """
        with self.neo4j.driver.session() as session:
            session.run(query, mid=entity_id, 
                        mat=new_stats.get("material", 0),
                        vit=new_stats.get("vitality", 0),
                        soc=new_stats.get("social", 0),
                        cog=new_stats.get("cognitive", 0))

        # 2. Update Qdrant Payload (for retrieval consistency)
        # We use set_payload to avoid re-uploading the vector
        self.qdrant.set_payload(
            collection_name="molecules",
            payload={"stats": new_stats},
            points=[entity_id]
        )

    # =========================================================================
    # 4. ENTROPY & CHAOS MECHANICS
    # =========================================================================

    def inject_noise(self, vector: List[float], intensity: float = 0.1) -> List[float]:
        """
        Механизм "Пинка". Добавляет Гауссовский шум к вектору сущности.
        Это смещает фокус внимания NPC в случайную сторону.
        """
        vec_np = np.array(vector)
        noise = np.random.normal(0, 1, len(vec_np))
        
        # Нормализуем шум, чтобы он был сопоставим с вектором
        noise_norm = noise / np.linalg.norm(noise)
        
        # Смешиваем: V_new = (1 - alpha) * V_old + alpha * Noise
        # Где alpha = intensity
        perturbed_vec = (1 - intensity) * vec_np + intensity * noise_norm
        
        # Ре-нормализуем, чтобы косинусное расстояние работало корректно
        return (perturbed_vec / np.linalg.norm(perturbed_vec)).tolist()
    
    def get_orthogonal_query(self, current_vector: List[float], intensity: float = 0.5) -> List[float]:
        """
        Генерирует вектор запроса, который 'перпендикулярен' текущему состоянию.
        Помогает найти события, которые НЕ связаны с текущей повесткой.
        """
        v = np.array(current_vector)
        
        # 1. Генерируем случайный вектор намерений
        random_vec = np.random.normal(0, 1, len(v))
        
        # 2. Проецируем random_vec на v
        # proj = (r . v) / (v . v) * v
        v_norm_sq = np.dot(v, v)
        if v_norm_sq == 0: 
            return random_vec.tolist()
            
        proj = (np.dot(random_vec, v) / v_norm_sq) * v
        
        # 3. Вычитаем проекцию (получаем ортогональную компоненту)
        # rejection = r - proj
        orthogonal_vec = random_vec - proj
        
        # 4. Смешиваем с исходным вектором (или возвращаем чистый ортогонал)
        # intensity 1.0 = ищем что-то вообще перпендикулярное (Смена темы)
        # intensity 0.1 = небольшое отклонение
        
        # Нормализуем оба
        v_norm = v / np.linalg.norm(v)
        o_norm = orthogonal_vec / np.linalg.norm(orthogonal_vec)
        
        final_query = (1 - intensity) * v_norm + intensity * o_norm
        return final_query.tolist()

    def select_outcome_stochastic(self, candidates: List[Dict], temperature: float = 0.1) -> Dict:
        """
        Выбирает действие не строго по Score, а вероятностно (Softmax).
        
        Candidates: список dict c ключом 'score' (cosine similarity).
        Temperature:
           - 0.01 -> Почти всегда выбирается Top-1 (Строгая логика)
           - 1.0  -> Выбирается случайно с весом (Хаос)
           - 5.0  -> Полный рандом (Броуновское движение)
        """
        if not candidates:
            return None
            
        scores = np.array([c['score'] for c in candidates])
        
        # Softmax с температурой
        # exp(score / temp) / sum(...)
        try:
            exp_scores = np.exp(scores / temperature)
            probabilities = exp_scores / np.sum(exp_scores)
        except RuntimeWarning:
            # Если scores слишком большие или temp слишком маленький
            return candidates[0]

        # Выбор взвешенным рандомом
        chosen_index = np.random.choice(len(candidates), p=probabilities)
        return candidates[chosen_index]
