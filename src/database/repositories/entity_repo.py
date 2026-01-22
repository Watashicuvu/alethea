from typing import Dict, List, Optional
from src.database.neo4j_client import Neo4jClient

class EntityRepository:
    def __init__(self, client: Neo4jClient):
        self.client = client

    def upsert_molecule(self, uid: str, name: str, category: str, 
                        role_id: str = None, 
                        component_ids: list = [],
                        stats: dict = None): # <--- Принимаем словарь
        
        stats = stats or {}
        
        # 1. Распаковываем словарь в плоские переменные
        params = {
            "mid": uid,
            "name": name,
            "cat": category,
            "role": role_id,
            "comps": component_ids,
            
            # РАСПАКОВКА
            "mat": stats.get("material", 0.0),
            "vit": stats.get("vitality", 0.0),
            "soc": stats.get("social", 0.0),
            "cog": stats.get("cognitive", 0.0)
        }

        query = """
        MERGE (m:Molecule {id: $mid})
        SET m.name = $name,
            m.category = $cat,
            m.narrative_role = $role,
            m.components = $comps,
            
            // Сохраняем распакованные значения
            m.val_material  = $mat,
            m.val_vitality  = $vit,
            m.val_social    = $soc,
            m.val_cognitive = $cog,
            
            m.last_updated = timestamp()
        """
        
        # 2. Передаем kwargs
        self.client.execute_write(query, **params)

    def find_entity_in_location(self, location_id: str, name_query: str) -> Optional[str]:
        """Ищет сущность по имени внутри конкретной локации (контекстный поиск)."""
        # Используем индекс полнотекстового поиска или просто CONTAINS
        query = """
        MATCH (l:Location {id: $lid})<-[:LOCATED_AT]-(m:Molecule)
        WHERE toLower(m.name) CONTAINS toLower($name)
        RETURN m.id as id LIMIT 1
        """
        res = self.client.execute_query(query, lid=location_id, name=name_query.lower()).single()
        return res['id'] if res else None

    def fuzzy_search_molecule(self, name_query: str, threshold: float = 0.85) -> Optional[str]:
        """Глобальный поиск по индексу имен."""
        # Требуется индекс: CREATE FULLTEXT INDEX molecule_name_index ...
        safe_query = name_query.replace("-", "\\-") + "~"
        query = """
        CALL db.index.fulltext.queryNodes("molecule_name_index", $q) YIELD node, score
        WHERE score > $thresh
        RETURN node.id as id LIMIT 1
        """
        # Оборачиваем в try/except на случай отсутствия индекса
        try:
            res = self.client.execute_query(query, q=safe_query, thresh=threshold).single()
            return res['id'] if res else None
        except Exception:
            return None

    def upsert_shadow_node(self, uid: str, name: str, source_text: str):
        """
        Создает 'Теневой Узел'.
        Используется, когда мы знаем, что кто-то совершил действие, но не знаем кто.
        """
        query = """
        MERGE (m:Molecule {id: $uid})
        ON CREATE SET 
            m.name = $name,
            m.category = 'SHADOW',
            m.is_shadow = true,
            m.source_ref = $src,
            m.created_at = timestamp()
        """
        self.client.execute_write(query, uid=uid, name=name, src=source_text)

    def link_generic(self, source_id: str, target_id: str, rel_type: str, description: str):
        """
        Сохраняет любую связь, которая не подошла под специальные категории (Social/Spatial/Mental).
        Создает ребро RELATED_TO с атрибутами типа и описания.
        """
        query = """
        MATCH (a:Molecule {id: $aid})
        MATCH (b {id: $bid})  // Target может быть Molecule, Event или Location
        MERGE (a)-[r:RELATED_TO]->(b)
        SET r.category = 'GENERIC',
            r.type = $type,          // Например: "USED", "ATTACKED", "COOKED"
            r.description = $desc,   // Оригинальный текст: "hit with a frying pan"
            r.last_updated = timestamp()
        """
        self.client.execute_write(query, aid=source_id, bid=target_id, type=rel_type, desc=description)

    def link_molecule_to_location(self, molecule_id: str, location_id: str):
        """Простая привязка сущности к локации (без удаления старых связей, для stub)."""
        query = """
        MATCH (m:Molecule {id: $mid})
        MATCH (l:Location {id: $lid})
        MERGE (m)-[:LOCATED_AT]->(l)
        """
        self.client.execute_write(query, mid=molecule_id, lid=location_id)

    def link_thought(self, thinker_id: str, target_id: str, type: str = "THINKS_OF"):
        """Ментальная связь (кто-то думает о ком-то/чем-то)."""
        query = """
        MATCH (a:Molecule {id: $aid})
        MATCH (b {id: $bid})  // Target может быть Molecule или Event
        MERGE (a)-[r:THINKS_OF]->(b)
        SET r.subtype = $type
        """
        self.client.execute_write(query, aid=thinker_id, bid=target_id, type=type)

    def link_social(self, entity_a_id: str, entity_b_id: str, 
                    rel_type: str, intensity: float = 1.0, 
                    confidence: float = 1.0, public: bool = True):
        """
        Обновление социального отношения.
        Мнение меняется со временем, поэтому мы перезаписываем тип и интенсивность,
        а не плодим связи (A)-[HATES]->(B) и (A)-[LOVES]->(B) одновременно.
        """
        query = """
        MATCH (a:Molecule {id: $aid})
        MATCH (b:Molecule {id: $bid})
        
        // Используем MERGE: если связь уже есть, мы её обновим
        MERGE (a)-[r:RELATED_TO]->(b)
        
        // Перезаписываем состояние на актуальное
        SET r.type = $type,
            r.intensity = $intensity,
            r.confidence = $conf,
            r.is_public = $public,
            r.last_updated = timestamp()
        """
        self.client.execute_write(query, aid=entity_a_id, bid=entity_b_id, 
                                  type=rel_type, intensity=intensity, 
                                  conf=confidence, public=public)

    def link_membership(self, molecule_id: str, faction_id: str):
        """
        Если персонаж может быть только в одной фракции одновременно (опционально).
        """
        query = """
        MATCH (m:Molecule {id: $mid})
        MATCH (f:Faction {id: $fid})
        
        // Опционально: удалить старое членство
        // OPTIONAL MATCH (m)-[old:MEMBER_OF]->() DELETE old
        
        MERGE (m)-[:MEMBER_OF]->(f)
        """
        self.client.execute_write(query, mid=molecule_id, fid=faction_id)

    # =========================================================================
    # 3. POSSESSION & CONTAINMENT (Inventory System)
    # =========================================================================

    def link_possession(self, item_id: str, owner_id: str, rel_type: str):
        """
        Перемещение предмета.
        Гарантирует, что предмет находится ТОЛЬКО в одном месте в один момент времени (Snapshot).
        """
        # Нормализация типа связи
        valid_types = ["LOCATED_AT", "STORED_BY", "EQUIPPED_BY", "IS_INSIDE", "IMPLANTED_IN"]
        clean_type = rel_type.upper() if rel_type.upper() in valid_types else "LOCATED_AT"

        query = f"""
        MATCH (item:Molecule {{id: $iid}})
        MATCH (owner {{id: $oid}}) 
        
        // 1. Находим и удаляем ЛЮБЫЕ старые физические привязки этого предмета
        OPTIONAL MATCH (item)-[old]->() 
        WHERE type(old) IN {str(valid_types)}
        DELETE old
        
        // 2. Создаем новую связь
        MERGE (item)-[:{clean_type}]->(owner)
        """
        self.client.execute_write(query, iid=item_id, oid=owner_id)

    # =========================================================================
    # 4. KNOWLEDGE (Secrets)
    # =========================================================================

    def link_knowledge(self, entity_id: str, secret_node_id: str):
        """
        Сущность 'знает' о секрете/факте.
        """
        query = """
        MATCH (e:Molecule {id: $eid})
        MATCH (s:Secret {id: $sid}) // Или Event/Fact
        MERGE (e)-[:KNOWS]->(s)
        """
        with self.client.driver.session() as session:
            session.run(query, eid=entity_id, sid=secret_node_id)
    
    def delete_molecule(self, uid: str):
        with self.client.driver.session() as session:
            session.run("MATCH (n:Molecule {id: $id}) DETACH DELETE n", id=uid)
