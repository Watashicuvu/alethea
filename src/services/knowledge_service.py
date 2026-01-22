import logging
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

    def calculate_interaction_outcome(self, 
                                      source_vec: List[float], 
                                      target_vec: List[float]) -> float:
        """
        Simple cosine similarity for Level 1 'Brownian Motion'.
        If score > 0.7 -> Attraction (Merge/Trade).
        If score < 0.3 -> Repulsion (Conflict/Bounce).
        """
        # Manual cosine similarity if not using numpy
        import numpy as np
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
