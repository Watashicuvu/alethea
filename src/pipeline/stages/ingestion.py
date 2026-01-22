import uuid
import logging
from typing import Dict, List, Optional
from qdrant_client.models import PointStruct

from src.pipeline.context import PipelineContext
from src.ingestion.schemas import ExtractionBatch, ExtractedRelationship
from src.ingestion.game_math import GameMath
from src.ingestion.mappers import RelationshipSanitizer, RELATIONS
from src.registries.all_registries import VERBS

class BatchIngestor:
    """
    Stage 2: Ingestion & Storage.
    Принимает структурированные данные (Batch) и раскладывает их по базам.
    """

    def __init__(self, ctx: PipelineContext):
        self.ctx = ctx

    def process(self, batch: ExtractionBatch, source_ref: str, 
                loc_id: str, entity_registry: Dict[str, str], 
                source_id: str, current_tick: int = -1):
        
        points = {"molecules": [], "verbs": [], "vibes": []}

        # 1. MOLECULES
        self._process_molecules(batch.molecules, source_ref, loc_id, entity_registry, source_id, points)

        # 2. VERBS
        self._process_verbs(batch.verbs, loc_id, source_id, current_tick, points)

        # 3. VIBES
        self._process_vibes(batch.vibes, loc_id, source_id, points)

        # 4. QDRANT UPSERT
        for col_name, pts in points.items():
            if pts:
                self.ctx.qdrant.upsert(collection_name=col_name, points=pts)

        # 5. RELATIONSHIPS
        # Восстанавливаем маппинг имен (включая локальные)
        full_name_map = entity_registry.copy()
        self._process_relationships(batch.relationships, full_name_map, loc_id)

    def _process_molecules(self, molecules, source_ref, loc_id, entity_registry, source_id, points_dict):
        for m in molecules:
            clean_name = m.name.lower().strip()
            
            # А. ID RESOLUTION
            if clean_name in entity_registry:
                mol_id = entity_registry[clean_name]
            else:
                mol_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, clean_name))
                entity_registry[clean_name] = mol_id

            # Б. COLLECT OBSERVATION
            self.ctx.synthesizer.collect(
                uid=mol_id,
                observation=m.description,
                metadata={
                    "name": m.name,
                    "category": m.category,
                    "subtype": m.subtype,
                    "source_doc": source_ref,
                    "world_id": source_id 
                }
            )

            # В. NEO4J STUB
            # Используем репозиторий entities
            self.ctx.repos.entities.upsert_molecule(
                mol_id, m.name, m.category
            )
            
            if loc_id:
                # Используем репозиторий entities
                self.ctx.repos.entities.link_molecule_to_location(mol_id, loc_id)

            # Г. QDRANT DRAFT
            emb = self.ctx.embedder.get_text_embedding(f"{m.name} {m.description}")
            points_dict["molecules"].append(PointStruct(
                id=mol_id, vector=emb, payload={
                    "name": m.name, 
                    "type": "molecule", 
                    "is_draft": True,
                    "source_id": source_id
                }
            ))

    def _process_verbs(self, verbs, loc_id, source_id, current_tick, points_dict):
        GARBAGE_VERBS = {"did", "do", "does", "be", "is", "was", "went", "go", "said", "look", "saw"}
        
        for v in verbs:
            clean_name = v.name.lower().strip()
            
            if clean_name in GARBAGE_VERBS or len(clean_name) < 3:
                if loc_id:
                    self.ctx.synthesizer.collect_scene_beat(loc_id, f"{v.name}: {v.context_usage}", tick=current_tick)
                continue

            cache_key = f"{clean_name}|{v.implied_system}"
            primitive_id = self.ctx.verb_cache.get(cache_key)
            
            if primitive_id is None:
                if v.implied_system == "FLAVOR" or "narrative" in v.implied_system.lower():
                    primitive_id = None 
                else:
                    query = f"{v.name}. {v.context_usage}. System: {v.implied_system}"
                    primitive_id = self.ctx.classifier.classify(
                        query_text=query,
                        registry=VERBS,
                        threshold_high=0.88,
                        threshold_low=0.65,
                        top_k=3
                    )
                self.ctx.verb_cache[cache_key] = primitive_id

            if primitive_id:
                emb = self.ctx.embedder.get_text_embedding(f"{v.name} {v.force_desc}")
                raw_stats = self.ctx.projector.project(emb)
                final_stats = GameMath.calculate_action_stats(raw_stats, v.implied_system)

                verb_id = str(uuid.uuid4())
                points_dict["verbs"].append(PointStruct(
                    id=verb_id, vector=emb, payload={
                        "name": v.name,
                        "system": v.implied_system,
                        "primitive_id": primitive_id,
                        "stats": final_stats,
                        "location_id": loc_id,
                        "source_id": source_id
                    }
                ))
                
                if loc_id:
                    self.ctx.synthesizer.collect_scene_beat(loc_id, f"[Mechanic] {v.name}", tick=current_tick)
            else:
                if loc_id:
                    self.ctx.synthesizer.collect_scene_beat(loc_id, f"{v.name}: {v.context_usage}", tick=current_tick)

    def _process_vibes(self, vibes, loc_id, source_id, points_dict):
        batch_vibe_stats = {"material": [], "vitality": [], "social": [], "cognitive": []}
        
        for vb in vibes:
            if len(vb.snippet) < 5: continue

            vibe_id = str(uuid.uuid4())
            emb = self.ctx.embedder.get_text_embedding(vb.snippet)
            raw_stats = self.ctx.projector.project(emb)
            final_stats = GameMath.calculate_vibe_stats(raw_stats, vb.tags)
            
            for k, v in final_stats.items():
                if k in batch_vibe_stats:
                    batch_vibe_stats[k].append(v)
            
            points_dict["vibes"].append(PointStruct(
                id=vibe_id, vector=emb, payload={
                    "snippet": vb.snippet,
                    "tags": vb.tags,
                    "stats": final_stats,
                    "location_id": loc_id,
                    "source_id": source_id
                }
            ))

        if loc_id and any(batch_vibe_stats.values()):
            avg_stats = {}
            for axis, values in batch_vibe_stats.items():
                avg_stats[axis] = sum(values) / len(values) if values else 0.0
            
            # ВАЖНО: Используем репозиторий locations
            self.ctx.repos.locations.update_atmosphere(loc_id, avg_stats, weight=0.3)

    def _process_relationships(self, relationships, full_registry, loc_id):
        last_subject_id = None
        
        for rel in relationships:
            try:
                subj_id = self._resolve_entity_id(rel.subject_name, full_registry, loc_id, last_subject_id)
                if subj_id: last_subject_id = subj_id
                obj_id = self._resolve_entity_id(rel.target_name, full_registry, loc_id, last_subject_id)
                
                if not subj_id or not obj_id: continue

                # Пытаемся достать категории, если они есть в метаданных
                subj_meta = self.ctx.synthesizer._metadata.get(subj_id, {})
                obj_meta = self.ctx.synthesizer._metadata.get(obj_id, {})
                
                raw_rel_type = RELATIONS.map_container(rel.description) or "RELATED_TO"
                if rel.category == "MENTAL": raw_rel_type = "THINKS_OF"

                final_rel_type = RelationshipSanitizer.validate_and_fix(
                    subj_meta.get('category', 'UNKNOWN'), 
                    obj_meta.get('category', 'UNKNOWN'), 
                    raw_rel_type, rel.description
                )
                
                self._apply_neo4j_relationship(final_rel_type, subj_id, obj_id, rel.description)

            except Exception as e:
                logging.error(f"Rel Error: {e}")

    def _apply_neo4j_relationship(self, rel_type, subj_id, obj_id, desc):
        # Используем репозитории
        entities = self.ctx.repos.entities
        locations = self.ctx.repos.locations
        
        # 1. PHYSICAL / POSSESSION
        if rel_type == "LOCATED_AT":
            entities.link_possession(item_id=subj_id, owner_id=obj_id, rel_type="LOCATED_AT")
            
        elif rel_type == "POSSESSES":
            entities.link_possession(item_id=obj_id, owner_id=subj_id, rel_type="EQUIPPED")
            
        # 2. SOCIAL / PROXIMITY
        elif rel_type == "NEAR":
            entities.link_social(subj_id, obj_id, "NEAR", intensity=0.5, confidence=1.0)
            
        elif rel_type == "SOCIAL":
            # Если классификатор вернул просто SOCIAL, сохраняем как есть
            entities.link_social(subj_id, obj_id, "INTERACTS", intensity=0.5)

        # 3. MENTAL
        elif rel_type in ["THINKS_OF", "RECALLS", "KNOWS"]:
            entities.link_thought(subj_id, obj_id, type=rel_type)

        # 4. KNOWLEDGE (Секреты)
        # Если вы уже реализовали Secrets, раскомментируйте:
        # elif rel_type == "KNOWS_SECRET":
        #     entities.link_knowledge(subj_id, obj_id)

        # === 5. FALLBACK (НОВОЕ) ===
        else:
            # Если связь не попала ни в одну категорию (например "ATTACKED", "CREATED", "USED")
            # Мы всё равно сохраняем её, чтобы не терять контекст.
            entities.link_generic(
                source_id=subj_id, 
                target_id=obj_id, 
                rel_type=rel_type, 
                description=desc
            )

    def _resolve_entity_id(self, name, registry, loc_id, context_agent_id):
        clean = name.lower().strip()
        if clean in ["he", "she", "it", "him", "her"] and context_agent_id:
            return context_agent_id
        if clean in ["here", "this place"]:
            return loc_id
        if clean in registry:
            return registry[clean]
        
        for reg_name, uid in registry.items():
            if clean in reg_name or reg_name in clean:
                if len(clean) > 3: return uid
        
        return None
    