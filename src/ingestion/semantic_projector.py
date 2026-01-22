import numpy as np
from typing import Dict, List, Tuple
# Импортируем ваш Enum, чтобы ключи совпадали со старой версией
from src.models.ecs.ontology_schemas import Sphere 
from llama_index.core.base.embeddings.base import BaseEmbedding

class SemanticProjector:
    """
    Проецирует текст на 4 фундаментальные оси бытия.
    Использует Contrastive Anchors (разность между позитивным и негативным примером).
    """
    def __init__(self, embedder: BaseEmbedding):
        self.embedder = embedder
        
        # === 1. КОНФИГУРАЦИЯ ЯКОРЕЙ (AXIS DEFINITIONS) ===
        # Используем ключи Sphere Enum, чтобы сохранить совместимость с БД
        self.axis_definitions = {
            Sphere.MATERIAL: (
                ["solid object", "heavy metal", "stone wall", "dense matter", "wealth", "infrastructure"], 
                ["abstract thought", "ghost", "empty air", "illusion", "spiritual concept", "nothing"]
            ),
            Sphere.VITALITY: (
                ["thriving life", "strong health", "biological growth", "pulsing blood", "survival instinct", "nature"],
                ["dead corpse", "inanimate rock", "withered decay", "mechanical robot", "dust", "undead"]
            ),
            Sphere.SOCIAL: (
                ["royal court", "political hierarchy", "crowded market", "organized guild", "diplomacy", "reputation"],
                ["lonely wilderness", "complete isolation", "hermit", "empty void", "antisocial", "outcast"]
            ),
            Sphere.COGNITIVE: (
                ["complex magic spell", "scientific theory", "ancient library", "intellect", "strategic plan", "logic"],
                ["brute force", "simple instinct", "mindless chaos", "dull object", "random noise", "stupidity"]
            )
        }
        
        # Кэш векторов (tuple of pos_centroid, neg_centroid)
        self.axis_vectors: Dict[Sphere, Tuple[np.ndarray, np.ndarray]] = {}
        self._init_axis_vectors()

    def _init_axis_vectors(self):
        """Превращает слова-якоря в эталонные векторы (центроиды)."""
        print("   ⚖️  Calibrating Semantic Axes (Contrastive)...")
        for sphere, (pos_words, neg_words) in self.axis_definitions.items():
            # Получаем векторы
            pos_vecs = [self.embedder.get_text_embedding(w) for w in pos_words]
            neg_vecs = [self.embedder.get_text_embedding(w) for w in neg_words]
            
            # Считаем центроиды
            pos_centroid = np.mean(pos_vecs, axis=0)
            neg_centroid = np.mean(neg_vecs, axis=0)
            
            # Нормализуем
            pos_centroid = pos_centroid / (np.linalg.norm(pos_centroid) + 1e-9)
            neg_centroid = neg_centroid / (np.linalg.norm(neg_centroid) + 1e-9)
            
            self.axis_vectors[sphere] = (pos_centroid, neg_centroid)

    def project(self, embedding: List[float]) -> Dict[str, float]:
        """
        Проецирует вектор.
        Возвращает Dict[str, float], где ключи - значения Enum (например 'material').
        """
        target_vec = np.array(embedding)
        norm = np.linalg.norm(target_vec)
        target_vec = target_vec / (norm + 1e-9)
        
        results = {}
        for sphere, (pos_vec, neg_vec) in self.axis_vectors.items():
            # Dot Product
            sim_pos = np.dot(target_vec, pos_vec)
            sim_neg = np.dot(target_vec, neg_vec)
            
            # === CONTRASTIVE FORMULA ===
            # (Pos - Neg) / 2 + 0.5 -> диапазон [0, 1]
            score = (sim_pos - sim_neg) / 2 + 0.5
            
            # Клиппинг [0, 1]
            final_score = float(np.clip(score, 0.0, 1.0))
            
            # Используем sphere.value ('material'), как в старом коде
            results[sphere.value] = final_score
            
        return results

    def normalize_batch(self, stats_batch: List[Dict[str, float]]) -> List[Dict[str, float]]:
        """
        Новый метод. Если вы не вызовете его в pipeline, код не упадет, 
        просто не будет эффекта растягивания гистограммы.
        """
        # TODO: numpy !!!
        if not stats_batch:
            return []
            
        keys = list(stats_batch[0].keys())
        normalized_batch = [d.copy() for d in stats_batch]
        
        for key in keys:
            values = [d[key] for d in stats_batch]
            v_min, v_max = min(values), max(values)
            delta = v_max - v_min
            
            if delta < 0.02: continue # Слишком малый разброс, пропускаем
                
            for i in range(len(normalized_batch)):
                original = values[i]
                # Min-Max Scaling в [0.05 ... 0.95]
                scaled = (original - v_min) / delta
                normalized_batch[i][key] = round(0.05 + (scaled * 0.9), 3)
                
        return normalized_batch
    