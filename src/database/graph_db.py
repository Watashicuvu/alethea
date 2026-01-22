from neo4j import GraphDatabase
from typing import List, Dict, Optional
import time

class Neo4jConnector:
    def __init__(self, uri: str ="bolt://localhost:7687", user: str ="neo4j", password: str ="password"):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self._init_constraints()

    def close(self):
        self.driver.close()

    def _init_constraints(self):
        queries = [
            # Basic constraints
            "CREATE CONSTRAINT IF NOT EXISTS FOR (l:Location) REQUIRE l.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (e:Event) REQUIRE e.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (m:Molecule) REQUIRE m.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (f:Faction) REQUIRE f.id IS UNIQUE", 
            "CREATE CONSTRAINT IF NOT EXISTS FOR (ep:Episode) REQUIRE ep.id IS UNIQUE",
            
            # Indexes for search
            "CREATE INDEX IF NOT EXISTS FOR (l:Location) ON (l.name)",
            "CREATE INDEX IF NOT EXISTS FOR (m:Molecule) ON (m.name)",
            "CREATE INDEX IF NOT EXISTS FOR (ep:Episode) ON (ep.start_tick)",
            
            # Fulltext indexes (Fuzzy Search)
            "CREATE FULLTEXT INDEX location_name_index IF NOT EXISTS FOR (n:Location) ON EACH [n.name]",
            "CREATE FULLTEXT INDEX faction_name_index IF NOT EXISTS FOR (n:Faction) ON EACH [n.name]",
            "CREATE FULLTEXT INDEX molecule_name_index IF NOT EXISTS FOR (n:Molecule) ON EACH [n.name]",
        ]
        with self.driver.session() as session:
            for q in queries:
                session.run(q)

    # Новый метод для нечеткого поиска
    def fuzzy_search_location(self, name_query: str, threshold: float = 0.8) -> Optional[str]:
        """
        Ищет локацию по имени с учетом опечаток.
        Возвращает UUID наиболее похожего кандидата или None.
        """
        # Тильда ~ указывает на нечеткий поиск (edit distance)
        # Мы экранируем спецсимволы, чтобы Lucene не ругался
        safe_query = name_query.replace("-", "\\-").replace(":", "\\:") + "~"
        
        query = """
        CALL db.index.fulltext.queryNodes("location_name_index", $q) YIELD node, score
        WHERE score > $thresh
        RETURN node.id AS id, node.name AS name, score
        LIMIT 1
        """
        with self.driver.session() as session:
            result = session.run(query, q=safe_query, thresh=threshold).single()
            
            if result:
                print(f"   🕵️ Neo4j Fuzzy Match: '{name_query}' ≈ '{result['name']}' (Score: {result['score']:.2f})")
                return result["id"]
        return None

    # =========================================================================
    # TOPOLOGY METHODS (Скелет карты)
    # =========================================================================
    
    def upsert_location(
            self, loc_id: str, name: str, summary: str, 
            source_doc: str, template_id: Optional[str] = None,
            semantic_stats: Optional[Dict[str, float]] = None
        ):
        """
        Создает узел Локации с привязкой к Топологическому Шаблону.
        """
        stats = semantic_stats or {"material": 0.0, "vitality": 0.0, "social": 0.0, "cognitive": 0.0}

        query = """
        MERGE (l:Location {id: $loc_id})
        SET l.name = $name,
            l.summary = $summary,
            l.source_doc = $source_doc,
            l.template_id = $template_id,

            l.val_material  = $mat,
            l.val_vitality  = $vit,
            l.val_social    = $soc,
            l.val_cognitive = $cog,

            l.last_updated = timestamp()
        """
        with self.driver.session() as session:
            session.run(query, 
                        loc_id=loc_id, name=name, summary=summary, 
                        source_doc=source_doc, template_id=template_id,
                        mat=stats.get("material", 0),
                        vit=stats.get("vitality", 0),
                        soc=stats.get("social", 0),
                        cog=stats.get("cognitive", 0)
            )

    def link_locations(self, from_id: str, to_id: str, connection_type: str = "PATH"):
        """
        Создает ребро с типом (EdgeType).
        """
        query = """
        MATCH (a:Location {id: $from_id})
        MATCH (b:Location {id: $to_id})
        MERGE (a)-[r:CONNECTED_TO]->(b)
        SET r.type = $type
        """
        with self.driver.session() as session:
            session.run(query, from_id=from_id, to_id=to_id, type=connection_type)

    # def link_location_parent(self, child_id: str, parent_id: str):
    #     """
    #     NEW: Иерархия (Room -> Building -> City -> Region).
    #     """
    #     query = """
    #     MATCH (c:Location {id: $cid})
    #     MATCH (p:Location {id: $pid})
    #     MERGE (c)-[:IS_INSIDE]->(p)
    #     """
    #     with self.driver.session() as session:
    #         session.run(query, cid=child_id, pid=parent_id)

    # =========================================================================
    # CHRONICLE METHODS (Скелет истории)
    # =========================================================================

    def upsert_event(self, event_id: str, name: str, tick_estimate: int, 
                     archetype_id: Optional[str] = None,
                     semantic_stats: Optional[Dict[str, float]] = None): # <--- NEW
        stats = semantic_stats or {}
        
        query = """
        MERGE (e:Event {id: $eid})
        SET e.name = $name,
            e.tick_estimate = $tick,
            e.archetype_id = $aid,
            
            // Координаты события
            e.val_material  = $mat,
            e.val_vitality  = $vit,
            e.val_social    = $soc,
            e.val_cognitive = $cog
        """
        with self.driver.session() as session:
            session.run(query, eid=event_id, name=name, tick=tick_estimate, aid=archetype_id,
                        mat=stats.get("material", 0.0),
                        vit=stats.get("vitality", 0.0),
                        soc=stats.get("social", 0.0),
                        cog=stats.get("cognitive", 0.0))

    def link_causality(self, cause_event_id: str, effect_event_id: str, reason: Optional[str] = None):
        """Связь А -> Б (Причинность)"""
        query = """
        MATCH (c:Event {id: $cid})
        MATCH (e:Event {id: $eid})
        MERGE (c)-[r:CAUSED]->(e)
        SET r.reason = $reason
        """
        with self.driver.session() as session:
            session.run(query, cid=cause_event_id, eid=effect_event_id, reason=reason)

    def link_event_to_location(self, event_id: str, location_id: str):
        """Где произошло событие?"""
        query = """
        MATCH (e:Event {id: $eid})
        MATCH (l:Location {id: $lid})
        MERGE (e)-[:HAPPENED_AT]->(l)
        """
        with self.driver.session() as session:
            session.run(query, eid=event_id, lid=location_id)

    # =========================================================================
    # ENTITY RESOLUTION HELPER
    # =========================================================================
    
    def find_potential_duplicates(self, label: str = "Location"):
        """
        Находит узлы с похожими именами (простая эвристика для начала).
        Для продакшена здесь нужен векторный поиск или LLM.
        """
        # Это placeholder. В реальности мы будем делать это через Qdrant + LLM
        pass

    def upsert_molecule(self, molecule_id: str, name: str, category: str, 
                        role_id: Optional[str] = None, 
                        component_ids: List[str] = [],
                        semantic_stats: Optional[Dict[str, float]] = None): 
        """
        Создает узел сущности с данными проекции и рассчитанными статами.
        """
        # Если статов нет, ставим по нулям
        stats = semantic_stats or {"material": 0.0, "vitality": 0.0, "social": 0.0, "cognitive": 0.0}
        
        query = """
        MERGE (m:Molecule {id: $mid})
        SET m.name = $name,
            m.category = $category,
            m.narrative_role = $role_id,    
            m.components = $comp_ids,
            
            // --- NEW: Semantic Stats ---
            m.val_material  = $mat,
            m.val_vitality  = $vit,
            m.val_social    = $soc,
            m.val_cognitive = $cog,
            
            m.last_updated = timestamp()
        """
        with self.driver.session() as session:
            session.run(query, 
                        mid=molecule_id, 
                        name=name, 
                        category=category, 
                        role_id=role_id, 
                        comp_ids=component_ids,
                        # Распаковываем статы
                        mat=stats.get("material", 0),
                        vit=stats.get("vitality", 0),
                        soc=stats.get("social", 0),
                        cog=stats.get("cognitive", 0)
            )

    def upsert_faction(self, faction_id: str, name: str, description: str):
        """
        Создает узел Фракции.
        """
        query = """
        MERGE (f:Faction {id: $fid})
        SET f.name = $name,
            f.description = $desc
        """
        with self.driver.session() as session:
            session.run(query, fid=faction_id, name=name, desc=description)

    def link_molecule_to_faction(self, molecule_id: str, faction_id: str):
        """
        Членство во фракции.
        """
        query = """
        MATCH (m:Molecule {id: $mid})
        MATCH (f:Faction {id: $fid})
        MERGE (m)-[:MEMBER_OF]->(f)
        """
        with self.driver.session() as session:
            session.run(query, mid=molecule_id, fid=faction_id)

    def link_molecule_to_location(self, molecule_id: str, location_id: str):
        """
        Связывает предмет с локацией.
        Используем MERGE, чтобы не дублировать связи, если предмет уже там.
        """
        # -- Удаляем старую связь, если предмет перенесли (опционально, зависит от игры)
        # -- OPTIONAL MATCH (m)-[old:LOCATED_AT]->(:Location)
        # -- DELETE old
        query = """
        MATCH (m:Molecule {id: $mid})
        MATCH (l:Location {id: $lid})
        
        MERGE (m)-[:LOCATED_AT]->(l)
        """
        with self.driver.session() as session:
            session.run(query, mid=molecule_id, lid=location_id)


    # =========================================================================
    # 1. HIERARCHY & TOPOLOGY (Missing Methods)
    # =========================================================================

    def link_location_parent(self, child_id: str, parent_id: str):
        """
        Создает иерархию: Комната -> Здание -> Район -> Город.
        Важно для зума карты.
        """
        query = """
        MATCH (c:Location {id: $cid})
        MATCH (p:Location {id: $pid})
        MERGE (c)-[:IS_INSIDE]->(p)
        """
        with self.driver.session() as session:
            session.run(query, cid=child_id, pid=parent_id)

    # =========================================================================
    # 2. SOCIAL GRAPH (New Layer)
    # =========================================================================

    def link_social(self, entity_a_id: str, entity_b_id: str, 
                    rel_type: str, intensity: float = 1.0, public: bool = True):
        """
        Создает социальную связь между Agent A и Agent B.
        rel_type берется из SocialRelType (ally, hostile...).
        """
        query = """
        MATCH (a:Molecule {id: $aid})
        MATCH (b:Molecule {id: $bid})
        MERGE (a)-[r:RELATED_TO]->(b)
        SET r.type = $type,
            r.intensity = $intensity,
            r.is_public = $public
        """
        with self.driver.session() as session:
            session.run(query, aid=entity_a_id, bid=entity_b_id, 
                        type=rel_type, intensity=intensity, public=public)

    # =========================================================================
    # 3. POSSESSION & CONTAINMENT (Inventory System)
    # =========================================================================

    def link_possession(self, item_id: str, owner_id: str, rel_type: str):
        """
        Перемещает предмет в инвентарь/руки сущности или в контейнер.
        Логика: Предмет может быть физически только в ОДНОМ месте.
        Поэтому мы сначала удаляем старые связи.
        """
        # rel_type: "equipped_by", "stored_by", "located_at"
        
        query = """
        MATCH (item:Molecule {id: $iid})
        MATCH (owner {id: $oid})  // owner может быть Molecule или Location
        
        // 1. Удаляем старые физические привязки предмета
        OPTIONAL MATCH (item)-[old]->() 
        WHERE type(old) IN ['LOCATED_AT', 'STORED_BY', 'EQUIPPED_BY', 'IS_INSIDE']
        DELETE old
        
        // 2. Создаем новую связь (динамический тип связи через APOC или просто MERGE c параметром нельзя)
        // Neo4j не позволяет параметр в типе связи MERGE (a)-[:$type]->(b).
        // Приходится использовать APOC или if/case на стороне Python.
        """
        
        # В Python делаем выборку для формирования корректного Cypher запроса
        # Это безопаснее и быстрее, чем APOC.
        valid_types = ["LOCATED_AT", "STORED_BY", "EQUIPPED_BY", "IS_INSIDE", "IMPLANTED_IN"]
        clean_type = rel_type.upper()
        
        if clean_type not in valid_types:
            clean_type = "LOCATED_AT" # Fallback

        final_query = f"""
        MATCH (item:Molecule {{id: $iid}})
        MATCH (owner {{id: $oid}})
        OPTIONAL MATCH (item)-[old]->() 
        WHERE type(old) IN ['LOCATED_AT', 'STORED_BY', 'EQUIPPED_BY', 'IS_INSIDE', 'IMPLANTED_IN']
        DELETE old
        MERGE (item)-[:{clean_type}]->(owner)
        """
        
        with self.driver.session() as session:
            session.run(final_query, iid=item_id, oid=owner_id)

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
        with self.driver.session() as session:
            session.run(query, eid=entity_id, sid=secret_node_id)

    # =========================================================================
    # MISSING TOPOLOGY METHODS
    # =========================================================================

    def upsert_location_projection(self, loc_id: str, template_id: str):
        """
        Обновляет локацию, присваивая ей найденный Топологический Шаблон.
        Вызывается из GraphBuilder после классификации.
        """
        query = """
        MATCH (l:Location {id: $lid})
        SET l.template_id = $tid
        """
        with self.driver.session() as session:
            session.run(query, lid=loc_id, tid=template_id)

    def link_location_hierarchy(self, child_id: str, parent_id: str):
        """
        Связывает локации отношением вложенности (Room IS_INSIDE House).
        """
        query = """
        MATCH (c:Location {id: $cid})
        MATCH (p:Location {id: $pid})
        MERGE (c)-[:IS_INSIDE]->(p)
        """
        with self.driver.session() as session:
            session.run(query, cid=child_id, pid=parent_id)

    # =========================================================================
    # MISSING CHRONICLE METHODS
    # =========================================================================

    def upsert_event_projection(self, event_id: str, archetype_id: str):
        """
        Присваивает событию его Архетип (например, 'evt_battle').
        """
        query = """
        MATCH (e:Event {id: $eid})
        SET e.archetype_id = $aid
        """
        with self.driver.session() as session:
            session.run(query, eid=event_id, aid=archetype_id)

    def link_event_to_arc(self, event_id: str, arc_instance_id: str):
        """
        Связывает Событие ИЛИ Эпизод с Нарративной Аркой.
        """
        query = """
        MATCH (e) WHERE e.id = $eid  // Ищем по ID без жесткой метки, или (e:Event|Episode)
        MATCH (n:NarrativeInstance {id: $nid})
        MERGE (e)-[:PART_OF_ARC]->(n)
        """
        with self.driver.session() as session:
            session.run(query, eid=event_id, nid=arc_instance_id)

    def upsert_narrative_instance(self, instance_id: str, template_id: str, name: str):
        """
        Создает узел Нарративной Арки (Инстанс сюжета).
        """
        query = """
        MERGE (n:NarrativeInstance {id: $nid})
        SET n.template_id = $tid,
            n.name = $name,
            n.created_at = timestamp()
        """
        with self.driver.session() as session:
            session.run(query, nid=instance_id, tid=template_id, name=name)
            
    def find_entity_in_location(self, location_id: str, name_query: str) -> Optional[str]:
        """
        Ищет сущность (Molecule) по имени, но ТОЛЬКО внутри конкретной локации.
        Помогает от коллизий (два 'Guard' в разных городах).
        """
        # Используем contains для частичного совпадения или toLower для точного
        query = """
        MATCH (l:Location {id: $lid})<-[:LOCATED_AT]-(m:Molecule)
        WHERE toLower(m.name) CONTAINS toLower($name)
        RETURN m.id as id
        LIMIT 1
        """
        with self.driver.session() as session:
            result = session.run(query, lid=location_id, name=name_query).single()
            if result:
                return result["id"]
        return None

    def fuzzy_search_molecule(self, name_query: str, threshold: float = 0.85) -> Optional[str]:
        """
        Ищет сущность по всему миру с учетом опечаток.
        Требует индекса: CREATE FULLTEXT INDEX molecule_name_index IF NOT EXISTS FOR (n:Molecule) ON EACH [n.name]
        """
        # Сначала создадим индекс, если его нет (лучше добавить в _init_constraints)
        
        safe_query = name_query.replace("-", "\\-") + "~"
        query = """
        CALL db.index.fulltext.queryNodes("molecule_name_index", $q) YIELD node, score
        WHERE score > $thresh
        RETURN node.id as id
        LIMIT 1
        """
        with self.driver.session() as session:
            # Важно: индекс molecule_name_index должен существовать!
            try:
                result = session.run(query, q=safe_query, thresh=threshold).single()
                if result:
                    return result["id"]
            except Exception:
                # Если индекса нет или ошибка синтаксиса
                return None
        return None
    
    # =========================================================================
    # EPISODE / SCENE METHODS (New Macro-Layer)
    # =========================================================================

    def upsert_episode(self, uid: str, name: str, summary: str, start_tick: int, location_id: str):
        """
        Создает узел Сцены (Episode) и сразу привязывает его к Локации.
        """
        query = """
        MERGE (ep:Episode {id: $uid})
        SET ep.name = $name,
            ep.summary = $summary,
            ep.start_tick = $tick
            
        WITH ep
        MATCH (l:Location {id: $lid})
        MERGE (ep)-[:HAPPENED_AT]->(l)
        """
        with self.driver.session() as session:
            session.run(query, uid=uid, name=name, summary=summary, tick=start_tick, lid=location_id)

    def link_episode_chain(self, prev_ep_id: str, curr_ep_id: str):
        """
        Связывает сцены в хронологическую цепочку: (Scene A)-[:NEXT_EPISODE]->(Scene B)
        """
        query = """
        MATCH (prev:Episode {id: $pid})
        MATCH (curr:Episode {id: $cid})
        MERGE (prev)-[:NEXT_EPISODE]->(curr)
        """
        with self.driver.session() as session:
            session.run(query, pid=prev_ep_id, cid=curr_ep_id)

    def link_episode_to_event(self, episode_id: str, event_id: str):
        """
        Вкладывает мелкое событие (Beat) в сцену: (Scene)-[:CONTAINS]->(Event)
        """
        query = """
        MATCH (ep:Episode {id: $sid})
        MATCH (ev:Event {id: $eid})
        MERGE (ep)-[:CONTAINS]->(ev)
        """
        with self.driver.session() as session:
            session.run(query, sid=episode_id, eid=event_id)

    # =========================================================================
    # VIBE / ATMOSPHERE METHODS (New Mechanics)
    # =========================================================================

    def update_location_atmosphere(self, location_id: str, batch_stats: Dict[str, float], weight: float = 0.2):
        """
        Внедряет вектор настроения в локацию.
        Использует 'Exponential Moving Average' (EMA) для смешивания.
        
        Args:
            location_id: UUID локации.
            batch_stats: Средний вектор вайбов из текущего куска текста.
            weight: Насколько сильно этот кусок влияет на общую атмосферу (0.0 - 1.0).
        """
        query = """
        MATCH (l:Location {id: $lid})
        
        // 1. Инициализируем атмосферу, если её нет (копируем базовые статы или нули)
        SET l.atmos_material  = coalesce(l.atmos_material,  l.val_material, 0.0),
            l.atmos_vitality  = coalesce(l.atmos_vitality,  l.val_vitality, 0.0),
            l.atmos_social    = coalesce(l.atmos_social,    l.val_social, 0.0),
            l.atmos_cognitive = coalesce(l.atmos_cognitive, l.val_cognitive, 0.0)
            
        // 2. Смешиваем текущее значение с новым (EMA Formula)
        // New = Old + Weight * (Batch - Old)
        SET l.atmos_material  = l.atmos_material  + $w * ($mat - l.atmos_material),
            l.atmos_vitality  = l.atmos_vitality  + $w * ($vit - l.atmos_vitality),
            l.atmos_social    = l.atmos_social    + $w * ($soc - l.atmos_social),
            l.atmos_cognitive = l.atmos_cognitive + $w * ($cog - l.atmos_cognitive)
        """
        
        with self.driver.session() as session:
            session.run(query, lid=location_id, w=weight,
                        mat=batch_stats.get("material", 0),
                        vit=batch_stats.get("vitality", 0),
                        soc=batch_stats.get("social", 0),
                        cog=batch_stats.get("cognitive", 0))

    def get_location_atmosphere(self, location_id: str) -> Dict[str, float]:
        """Для дебага или геймплея: получить текущий вайб локации."""
        query = """
        MATCH (l:Location {id: $lid})
        RETURN l.atmos_material as mat, l.atmos_vitality as vit, 
               l.atmos_social as soc, l.atmos_cognitive as cog
        """
        with self.driver.session() as session:
            r = session.run(query, lid=location_id).single()
            if r:
                return {"material": r["mat"], "vitality": r["vit"], "social": r["soc"], "cognitive": r["cog"]}
            return {}
        
    # =========================================================================
    # SIMULATION READ METHODS (The Loader)
    # =========================================================================

    def get_molecules_in_location(self, location_id: str) -> List[Dict]:
        """
        Retrieves all molecules currently physically located in a specific place.
        Used to populate the 'Petri Dish' for simulation.
        """
        query = """
        MATCH (m:Molecule)-[:LOCATED_AT]->(l:Location {id: $lid})
        RETURN m.id as id, m.name as name, m.category as category, 
               m.val_material as material, m.val_vitality as vitality,
               m.val_social as social, m.val_cognitive as cognitive
        """
        results = []
        with self.driver.session() as session:
            rows = session.run(query, lid=location_id)
            for row in rows:
                results.append(row.data())
        return results

    def get_connected_locations(self, location_id: str) -> List[Dict]:
        """
        Returns navigation options for Agents (Topology).
        """
        query = """
        MATCH (start:Location {id: $lid})-[r:CONNECTED_TO]-(end:Location)
        RETURN end.id as id, end.name as name, type(r) as path_type
        """
        results = []
        with self.driver.session() as session:
            rows = session.run(query, lid=location_id)
            for row in rows:
                results.append(row.data())
        return results
    
    # =========================================================================
    # LOCATION SKELETON & PHYSICS METHODS
    # =========================================================================

    def upsert_location_stub(self, uid: str, name: str, source_doc: str):
        """
        Pass 1: Создает 'черновой' узел локации.
        Мы еще не знаем физику, только ID и Имя.
        """
        query = """
        MERGE (l:Location {id: $uid})
        ON CREATE SET 
            l.name = $name,
            l.source_doc = $src,
            l.created_at = timestamp()
        // Если узел уже есть, обновляем имя (если новое длиннее/лучше), но не трогаем статы
        ON MATCH SET
            l.name = CASE WHEN size($name) > size(l.name) THEN $name ELSE l.name END
        """
        with self.driver.session() as session:
            session.run(query, uid=uid, name=name, src=source_doc)

    def update_location_physics(self, uid: str, name: str, description: str, 
                                physics_stats: Dict[str, float], geometry_tags: List[str]):
        """
        Post-Processing: Заливаем 'бетон' (Физику) в скелет.
        ВАЖНО: Мы пишем в поля val_* (Value), а не atmos_* (Atmosphere).
        """
        query = """
        MATCH (l:Location {id: $uid})
        SET l.name = $name,
            l.description = $desc,
            l.geometry_tags = $geo,
            
            // Базовая физика (Immutable Physics)
            l.val_material = $mat,
            l.val_vitality = $vit,
            l.val_social = $soc,
            l.val_cognitive = $cog,
            
            // Если атмосферы еще нет, инициализируем её физикой (базовое состояние)
            l.atmos_material = coalesce(l.atmos_material, $mat),
            l.atmos_vitality = coalesce(l.atmos_vitality, $vit),
            l.atmos_social = coalesce(l.atmos_social, $soc),
            l.atmos_cognitive = coalesce(l.atmos_cognitive, $cog)
        """
        with self.driver.session() as session:
            session.run(query, uid=uid, name=name, desc=description, geo=geometry_tags,
                        mat=physics_stats.get("material", 0.0),
                        vit=physics_stats.get("vitality", 0.0),
                        soc=physics_stats.get("social", 0.0),
                        cog=physics_stats.get("cognitive", 0.0))

    def delete_location(self, uid: str):
        """Удаляет локацию и все связи, если она признана мусором/дублем."""
        with self.driver.session() as session:
            session.run("MATCH (l:Location {id: $uid}) DETACH DELETE l", uid=uid)

    def delete_molecule(self, uid: str):
        with self.driver.session() as session:
            session.run("MATCH (n:Molecule {id: $id}) DETACH DELETE n", id=uid)
