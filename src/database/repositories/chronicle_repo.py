from typing import Dict, List, Optional
from src.database.neo4j_client import Neo4jClient
import uuid

class ChronicleRepository:
    def __init__(self, client: Neo4jClient):
        self.client = client

    # =========================================================================
    # UPSERT METHODS (WRITES)
    # Используем execute_write, так как он управляет транзакциями.
    # Важно: Распаковываем словари stats, чтобы не получить Map Error.
    # =========================================================================

    def upsert_episode(self, uid: str, name: str, summary: str, tick: int, location_id: str, 
                       archetype: Optional[str] = None, stats: Optional[Dict] = None):
        """Создает или обновляет Эпизод."""
        stats = stats or {}
        params = {
            "eid": uid,
            "name": name,
            "sum": summary,
            "tick": tick,
            "lid": location_id,
            "arch": archetype or "generic",
            "mat": stats.get("material", 0.0),
            "vit": stats.get("vitality", 0.0),
            "soc": stats.get("social", 0.0),
            "cog": stats.get("cognitive", 0.0)
        }

        query = """
        MERGE (e:Episode {id: $eid})
        SET e.name = $name,
            e.summary = $sum,
            e.tick = $tick,
            e.archetype = $arch,
            e.val_material = $mat,
            e.val_vitality = $vit,
            e.val_social   = $soc,
            e.val_cognitive= $cog,
            e.last_updated = timestamp()

        WITH e
        MATCH (l:Location {id: $lid})
        MERGE (e)-[:HAPPENED_AT]->(l)
        """
        self.client.execute_write(query, **params)

    def upsert_event(self, uid: str, name: str, tick_estimate: int, 
                     stats: Optional[Dict] = None, archetype_id: str = None):
        """Создает или обновляет Событие."""
        stats = stats or {}
        params = {
            "eid": uid,
            "name": name,
            "tick": tick_estimate,
            "arch": archetype_id,
            "mat": stats.get("material", 0.0),
            "vit": stats.get("vitality", 0.0),
            "soc": stats.get("social", 0.0),
            "cog": stats.get("cognitive", 0.0)
        }
        
        query = """
        MERGE (e:Event {id: $eid})
        SET e.name = $name,
            e.tick_estimate = $tick,
            e.archetype = $arch,
            e.val_material = $mat,
            e.val_vitality = $vit,
            e.val_social   = $soc,
            e.val_cognitive= $cog,
            e.created_at = timestamp()
        """
        self.client.execute_write(query, **params)

    def upsert_narrative_instance(self, instance_id: str, template_id: str, name: str):
        """Создает инстанс нарративной арки."""
        query = """
        MERGE (n:NarrativeInstance {id: $nid})
        SET n.template_id = $tid,
            n.name = $name,
            n.created_at = timestamp()
        """
        self.client.execute_write(query, nid=instance_id, tid=template_id, name=name)

    # =========================================================================
    # READ METHODS (QUERIES)
    # Используем явное открытие сессии и .data(), чтобы избежать ResultConsumedError.
    # =========================================================================

    def fetch_recent_events(self, limit: int = 10) -> List[Dict]:
        """
        Возвращает список последних эпизодов для анализа сюжета.
        """
        query = """
        MATCH (e:Episode)
        RETURN e.id AS id, e.name AS name, e.summary AS description, e.archetype AS archetype, e.tick AS tick
        ORDER BY e.tick DESC
        LIMIT $limit
        """
        
        # БЕЗОПАСНОЕ ЧТЕНИЕ:
        with self.client.driver.session() as session:
            result = session.run(query, limit=limit)
            # Жадная загрузка: превращаем данные в список прямо здесь, пока сессия жива
            data = [record.data() for record in result]
            
        # Возвращаем в хронологическом порядке [Old -> New]
        return data[::-1]

    def find_episode_by_tick(self, location_id: str, target_tick: int, window: int = 20) -> Optional[str]:
        """
        Ищет эпизод по времени.
        """
        query = """
        MATCH (e:Episode)-[:HAPPENED_AT]->(l:Location {id: $lid})
        WHERE abs(e.tick - $tick) <= $window
        RETURN e.id as id, abs(e.tick - $tick) as delta
        ORDER BY delta ASC
        LIMIT 1
        """
        
        with self.client.driver.session() as session:
            result = session.run(query, lid=location_id, tick=target_tick, window=window)
            record = result.single()
            if record:
                return record["id"]
            return None

    # =========================================================================
    # LINKING METHODS (EDGES)
    # =========================================================================

    def link_event_to_arc(self, event_id: str, arc_instance_id: str):
        query = """
        MATCH (e) WHERE e.id = $eid  // (Event|Episode)
        MATCH (n:NarrativeInstance {id: $nid})
        MERGE (e)-[:PART_OF_ARC]->(n)
        """
        self.client.execute_write(query, eid=event_id, nid=arc_instance_id)

    def link_next_event(self, prev_event_id: str, curr_event_id: str):
        query = """
        MATCH (prev:Event {id: $pid})
        MATCH (curr:Event {id: $cid})
        MERGE (prev)-[:NEXT]->(curr)
        """
        self.client.execute_write(query, pid=prev_event_id, cid=curr_event_id)

    def link_causality(self, cause_id: str, effect_id: str, reason: Optional[str] = None):
        query = """
        MATCH (c:Event {id: $cid})
        MATCH (e:Event {id: $eid})
        MERGE (c)-[r:CAUSED]->(e)
        SET r.reason = $reason
        """
        self.client.execute_write(query, cid=cause_id, eid=effect_id, reason=reason)

    def link_episode_chain(self, prev_ep_id: str, curr_ep_id: str):
        query = """
        MATCH (prev:Episode {id: $pid})
        MATCH (curr:Episode {id: $cid})
        MERGE (prev)-[:NEXT_EPISODE]->(curr)
        """
        self.client.execute_write(query, pid=prev_ep_id, cid=curr_ep_id)

    def link_recollection(self, current_event_id: str, historic_event_id: str):
        query = """
        MATCH (curr:Event {id: $cid})
        MATCH (hist:Event {id: $hid})
        MERGE (curr)-[:RECALLS]->(hist)
        """
        self.client.execute_write(query, cid=current_event_id, hid=historic_event_id)

    def link_participant(self, event_id: str, molecule_id: str):
        query = """
        MATCH (e:Event {id: $eid})
        MATCH (m:Molecule {id: $mid})
        MERGE (e)-[:INVOLVED]->(m)
        """
        self.client.execute_write(query, eid=event_id, mid=molecule_id)

    def link_event_location(self, event_id: str, location_id: str):
        query = """
        MATCH (e:Event {id: $eid})
        MATCH (l:Location {id: $lid})
        MERGE (e)-[:HAPPENED_AT]->(l)
        """
        self.client.execute_write(query, eid=event_id, lid=location_id)

    def link_event_hierarchy(self, scene_id: str, event_id: str):
        query = """
        MATCH (s:Episode {id: $sid})
        MATCH (e:Event {id: $eid})
        MERGE (s)-[:CONTAINS]->(e)
        """
        self.client.execute_write(query, sid=scene_id, eid=event_id)

    def append_description(self, event_id: str, text_to_append: str):
        query = """
        MATCH (e:Event {id: $eid})
        SET e.description = e.description + '\n' + $text
        """
        self.client.execute_write(query, eid=event_id, text=text_to_append)