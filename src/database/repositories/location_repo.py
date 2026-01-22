from typing import Dict, List, Optional
from src.database.neo4j_client import Neo4jClient

class LocationRepository:
    def __init__(self, client: Neo4jClient):
        self.client = client

    def upsert_stub(self, uid: str, name: str, source_doc: str):
        """Черновое создание (Pass 1)."""
        query = """
        MERGE (l:Location {id: $uid})
        ON CREATE SET l.name = $name, l.source_doc = $src, l.created_at = timestamp()
        ON MATCH SET l.name = CASE WHEN size($name) > size(l.name) THEN $name ELSE l.name END
        """
        self.client.execute_write(query, uid=uid, name=name, src=source_doc)

    def save_physics(self, uid: str, name: str, description: str, 
                     physics: dict, geo_tags: list = []):
        """
        Сохраняет физику локации. 
        physics — это словарь {'material': 0.9, ...}, его нужно распаковать.
        """
        physics = physics or {}
        
        params = {
            "lid": uid,
            "name": name,
            "desc": description,
            "tags": geo_tags,
            
            # РАСПАКОВКА
            "mat": physics.get("material", 0.0),
            "vit": physics.get("vitality", 0.0),
            "soc": physics.get("social", 0.0),
            "cog": physics.get("cognitive", 0.0)
        }

        query = """
        MERGE (l:Location {id: $lid})
        SET l.name = $name,
            l.description = $desc,
            l.geo_tags = $tags,
            
            // Физика
            l.val_material  = $mat,
            l.val_vitality  = $vit,
            l.val_social    = $soc,
            l.val_cognitive = $cog
        """
        
        self.client.execute_write(query, **params)

    def update_atmosphere(self, uid: str, stats: Dict[str, float], weight: float):
        """Метод EMA из старого graph_db."""
        query = """
        MATCH (l:Location {id: $uid})
        SET l.atmos_material  = l.atmos_material  + $w * ($mat - l.atmos_material),
            l.atmos_vitality  = l.atmos_vitality  + $w * ($vit - l.atmos_vitality),
            l.atmos_social    = l.atmos_social    + $w * ($soc - l.atmos_social),
            l.atmos_cognitive = l.atmos_cognitive + $w * ($cog - l.atmos_cognitive)
        """
        self.client.execute_write(
            query, uid=uid, w=weight,
            mat=stats.get("material", 0), vit=stats.get("vitality", 0),
            soc=stats.get("social", 0), cog=stats.get("cognitive", 0)
        )

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
        with self.client.driver.session() as session:
            result = session.run(query, q=safe_query, thresh=threshold).single()
            
            if result:
                print(f"   🕵️ Neo4j Fuzzy Match: '{name_query}' ≈ '{result['name']}' (Score: {result['score']:.2f})")
                return result["id"]
        return None
    
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
        with self.client.driver.session() as session:
            session.run(query, from_id=from_id, to_id=to_id, type=connection_type)
    
    def cleanup_merged(self, uid: str):
        self.client.execute_write("MATCH (l:Location {id: $uid}) DETACH DELETE l", uid=uid)
