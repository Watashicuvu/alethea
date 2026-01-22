import uuid
import logging
import numpy as np
from typing import Dict, List, Any, Optional

from qdrant_client.models import PointStruct
from src.pipeline.context import PipelineContext
from src.ingestion.game_math import GameMath
from src.registries.all_registries import ATOMS, ROLES, ARCS

class WorldSynthesizer:
    """
    Stage 3: Post-Processing & Synthesis.
    
    Оркестратор, который:
    1. Берет сырые данные из ctx.synthesizer (память).
    2. Прогоняет их через LLM (генерация чистовых описаний).
    3. Прогоняет через GameMath (расчет RPG-статов).
    4. Сохраняет результат синхронно в:
       - Neo4j (через ctx.repos.*) - для графовой логики.
       - Qdrant (напрямую) - для векторного поиска и RAG.
    """

    def __init__(self, ctx: PipelineContext):
        self.ctx = ctx

    def run(self, source_id: str):
        print(f"\n⚙️ Starting World Synthesis for source '{source_id}'...")

        print("🔍 Resolving Ambiguities & Buckets...")
        self.ctx.synthesizer.finalize_entities() 
        
        self.ctx.synthesizer.consolidate_locations()

        # 2. Location Blueprints (Строим мир)
        self._synthesize_locations(source_id)

        # 3. Entity Profiles (Заселяем мир)
        self._synthesize_entities(source_id)

        # 4. Chronicles (Пишем историю)
        self._synthesize_chronicles(source_id)

        # 5. Narrative Arcs (Понимаем сюжет)
        if self.ctx.options.detect_arcs:
            self._detect_narrative_arcs(source_id)

        # 6. Global Normalization (Баланс сил)
        if self.ctx.options.project_atoms:
            self._normalize_global_stats()

        print("✅ Synthesis Complete.")

    # =========================================================================
    # 1. LOCATIONS
    # =========================================================================
    def _synthesize_locations(self, source_id: str):
        print("🏰 Synthesizing Location Blueprints...")
        synth = self.ctx.synthesizer
        
        # Берем ключи напрямую из компонента
        loc_uids = list(synth._location_dossiers.keys())
        
        for loc_id in loc_uids:
            # Пропускаем, если локация была слита (Redirect)
            if loc_id in synth._redirect_map: continue

            # Генерация (LLM)
            loc_data = synth.synthesize_location(loc_id)
            if not loc_data: continue

            # Расчет физики (GameMath)
            # Берем только структурное описание для физики
            physics_text = f"{loc_data.canonical_name}. {loc_data.summary}"
            embedding = self.ctx.embedder.get_text_embedding(physics_text)
            raw_stats = self.ctx.projector.project(embedding)
            
            final_physics = GameMath.calculate_stats(
                base_vector_stats=raw_stats,
                atom_influence={},
                category="LOCATION"
            )

            # Сохранение (Repository)
            self.ctx.repos.locations.save_physics(
                uid=loc_id,
                name=loc_data.canonical_name,
                description=loc_data.summary,
                physics=final_physics,
                geo_tags=loc_data.geometry_tags
            )

            # D. Save to Qdrant
            self.ctx.qdrant.upsert("skeleton_locations", [PointStruct(
                id=loc_id,
                vector=embedding,
                payload={
                    "name": loc_data.canonical_name,
                    "description": loc_data.summary,
                    "exits": loc_data.detected_exits,
                    "physics": final_physics,
                    "type": "location",
                    "importance": loc_data.importance_score,
                    "source_id": source_id # <--- TAG
                }
            )])

        # E. Cleanup Merged
        for old_id in synth._redirect_map.keys():
            if old_id in synth._location_dossiers:
                self.ctx.repos.locations.cleanup_merged(old_id)
                self.ctx.qdrant.delete("skeleton_locations", points_selector=[old_id])

    # =========================================================================
    # 2. ENTITIES
    # =========================================================================
    def _synthesize_entities(self, source_id: str):
        print("🧪 Synthesizing Entities...")
        synth = self.ctx.synthesizer
        valid_uids = set()
        
        # Бежим по UID, которые остались после finalize_entities()
        all_uids = list(synth._dossiers.keys())
        
        for uid in all_uids:
            # Генерация профиля (LLM)
            # Внутри synthesize_profile теперь передаются aliases и фильтруются [UNCERTAIN]
            result = synth.synthesize_profile(uid)
            if not result: continue
            
            profile, final_uid = result
            valid_uids.add(final_uid)
            
            meta = synth._metadata[final_uid]
            category = meta.get('category', 'UNKNOWN')
            
            # --- MATH PROJECTION ---
            rich_text = f"{profile.canonical_name}. {profile.summary} Traits: {', '.join(profile.personality_traits)}."
            embedding = self.ctx.embedder.get_text_embedding(rich_text)
            raw_stats = self.ctx.projector.project(embedding)

            # Atom Influence
            atom_infl = {}
            if self.ctx.options.project_atoms:
                atom_infl = self._get_atom_influence(category, rich_text)
            
            # Final Stats
            final_stats = GameMath.calculate_stats(
                base_vector_stats=raw_stats,
                atom_influence=atom_infl,
                category=category
            )

            # Role Detection
            role_id = None
            if category in ["AGENT", "GROUP"] and self.ctx.options.project_roles:
                role_id = self.ctx.classifier.classify(rich_text, ROLES, top_k=3)

            # --- UPSERT (Repository) ---
            self.ctx.repos.entities.upsert_molecule(
                uid=final_uid, 
                name=profile.canonical_name, 
                category=category,
                role_id=role_id, 
                stats=final_stats
            )
            
            # D. Save to Qdrant
            payload = {
                **meta,
                "description": profile.summary,
                "visuals": profile.visual_traits,
                "psychology": profile.personality_traits,
                "role_desc": profile.narrative_role_desc,
                "importance": profile.importance_score,
                # Для RAG полезно хранить сырые наблюдения, чтобы видеть эволюцию
                "raw_observations": synth.get_raw_observations(final_uid),
                "stats": final_stats,
                "source_id": source_id,
                "is_draft": False
            }
            
            self.ctx.qdrant.upsert("molecules", [PointStruct(
                id=final_uid, 
                vector=embedding, 
                payload=payload
            )])

        # E. Cleanup Garbage
        self._cleanup_entities(valid_uids)

    # =========================================================================
    # 3. CHRONICLES
    # =========================================================================
    def _synthesize_chronicles(self, source_id: str):
        print("📜 Synthesizing Chronicles...")
        synth = self.ctx.synthesizer
        
        for loc_id in synth._scene_dossiers:
            # A. LLM Generate Episodes
            episodes = synth.synthesize_episodes_for_loc(loc_id)
            
            for ep in episodes:
                if ep.significance_score < 3: continue

                # B. Math
                full_text = f"{ep.title}. {ep.summary}"
                embedding = self.ctx.embedder.get_text_embedding(full_text)
                raw_stats = self.ctx.projector.project(embedding)
                
                # Atoms for Events
                atom_infl = {}
                if self.ctx.options.project_atoms:
                    atom_infl = self._get_atom_influence("EVENT", full_text)

                final_stats = GameMath.calculate_stats(
                    base_vector_stats=raw_stats,
                    atom_influence=atom_infl,
                    category= 'general',#ep.archetype, # "conflict", "discovery"...
                    is_event=True
                )

                # C. Find or Create ID (через Repository)
                # Ищем, не создали ли мы этот эпизод уже на этапе Pass 3
                target_id = self.ctx.repos.chronicle.find_episode_by_tick(loc_id, ep.start_tick) 
                if not target_id:
                    target_id = str(uuid.uuid4())

                # D. Save to Neo4j
                self.ctx.repos.chronicle.upsert_episode(
                    uid=target_id,
                    name=ep.title,
                    summary=ep.summary,
                    tick=ep.start_tick,
                    location_id=loc_id,
                    stats=final_stats,
                    archetype='general',
                )

                # E. Save to Qdrant
                payload = {
                    "name": ep.title,
                    "description": ep.summary,
                    "type": "episode",
                    "archetype": ep.archetype,
                    "tags": ep.dominant_tags,
                    "participants": ep.key_participants,
                    "significance": ep.significance_score,
                    "source_loc_id": loc_id,
                    "stats": final_stats,
                    "source_id": source_id
                }
                
                self.ctx.qdrant.upsert("chronicle", [PointStruct(
                    id=target_id,
                    vector=embedding,
                    payload=payload
                )])

    # =========================================================================
    # 4. NARRATIVE ARCS
    # =========================================================================
    def _detect_narrative_arcs(self, source_id: str):
        print("🕵️‍♂️ Running Narrative Arc Detection...")
        
        # 1. Fetch Context (Using Repository!)
        recent_episodes = self.ctx.repos.chronicle.fetch_recent_events(limit=8)
        if not recent_episodes: return

        # 2. Prepare Text
        story_text = "\n".join([f"- [{e['archetype']}] {e['name']}: {e['description']}" for e in recent_episodes])
        
        # 3. Classify (Hybrid)
        detected_arc_id = self.ctx.classifier.classify(
            query_text=story_text,
            registry=ARCS,
            threshold_high=0.65,
            top_k=3
        )

        if detected_arc_id:
            arc = ARCS.get(detected_arc_id)
            arc_name = arc.name if arc else "Unknown Arc"
            print(f"   🎭 DETECTED ARC: '{arc_name}'")
            
            instance_id = str(uuid.uuid4())
            
            # 4. Save to Neo4j
            self.ctx.repos.chronicle.upsert_narrative_instance(
                instance_id, detected_arc_id, f"{arc_name} (Auto-detected)"
            )
            # Link episodes
            for ep in recent_episodes:
                self.ctx.repos.chronicle.link_event_to_arc(ep['id'], instance_id)

            # 5. Save to Qdrant
            arc_vec = self.ctx.embedder.get_text_embedding(story_text)
            self.ctx.qdrant.upsert("narrative_instances", [PointStruct(
                id=instance_id, vector=arc_vec, payload={
                    "name": f"{arc_name} Instance",
                    "template_id": detected_arc_id,
                    "description": "Auto-detected narrative arc.",
                    "involved_episodes": [ep['id'] for ep in recent_episodes],
                    "source_id": source_id
                }
            )])

    # =========================================================================
    # 5. GLOBAL NORMALIZATION
    # =========================================================================
    def _normalize_global_stats(self):
        print("   ⚖️  Running Global Stat Normalization...")
        
        # 1. Fetch Data (Qdrant)
        try:
            scroll_res = self.ctx.qdrant.scroll("molecules", limit=10_000, with_payload=True)
            points = scroll_res[0]
            if not points: return
        except Exception as e:
            logging.error(f"Norm fetch failed: {e}")
            return

        # 2. Calculate Bounds
        axes = ["material", "vitality", "social", "cognitive"]
        values_map = {ax: [] for ax in axes}
        
        for p in points:
            stats = p.payload.get("stats", {})
            for ax in axes: values_map[ax].append(stats.get(ax, 0.0))

        bounds = {}
        for ax, vals in values_map.items():
            if not vals: continue
            bounds[ax] = (np.percentile(vals, 2), np.percentile(vals, 98))

        # 3. Normalize & Update
        updated_points = []
        for p in points:
            old_stats = p.payload.get("stats", {})
            new_stats = {}
            
            for ax, (v_min, v_max) in bounds.items():
                val = old_stats.get(ax, 0.0)
                if v_max - v_min < 0.01: new_val = val
                else:
                    scaled = (val - v_min) / (v_max - v_min)
                    new_val = float(np.clip(0.05 + (scaled * 0.9), 0.0, 1.0))
                new_stats[ax] = round(new_val, 3)
            
            p.payload["stats"] = new_stats
            updated_points.append(p)

            # Update Neo4j (Sync)
            # В EntityRepo нужно добавить метод update_stats_only, но можно и через upsert_molecule
            self.ctx.repos.entities.upsert_molecule(
                p.id, p.payload["name"], p.payload.get("category", "UNKNOWN"), 
                stats=new_stats
            )

        # 4. Update Qdrant Batch
        for p in updated_points:
             self.ctx.qdrant.overwrite_payload("molecules", p.payload, points=[p.id])

    # =========================================================================
    # HELPERS
    # =========================================================================
    def _get_atom_influence(self, category: str, text: str) -> Dict[str, List[float]]:
        influence = {"material": [], "vitality": [], "social": [], "cognitive": []}
        found = ATOMS.classify(f"{category}: {text}", threshold=0.55, top_k=5)
        
        for atom, score in found:
            # Поддержка Pydantic и dict
            if hasattr(atom.base_vector, 'model_dump'): stats = atom.base_vector.model_dump()
            elif isinstance(atom.base_vector, dict): stats = atom.base_vector
            else: continue # Fallback or error

            for axis, val in stats.items():
                if axis in influence: influence[axis].append(val * score)
        return influence

    def _cleanup_entities(self, valid_uids: set):
        all_uids = list(self.ctx.synthesizer._dossiers.keys())
        for uid in all_uids:
            # Если не валидный и не редирект -> удаляем
            if uid not in valid_uids and uid not in self.ctx.synthesizer._redirect_map:
                self.ctx.repos.entities.delete_molecule(uid)
                self.ctx.qdrant.delete("molecules", points_selector=[uid])
            # Если редирект -> удаляем (он уже слит)
            elif uid in self.ctx.synthesizer._redirect_map:
                self.ctx.repos.entities.delete_molecule(uid)
                self.ctx.qdrant.delete("molecules", points_selector=[uid])
                