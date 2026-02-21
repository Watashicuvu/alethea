import logging
import uuid
from typing import Dict, List, Any, Optional, Tuple, Set
from collections import defaultdict, Counter
from pydantic import BaseModel, Field
from llama_index.core import PromptTemplate
from rapidfuzz import fuzz 
from src.config import config
from src.models.ecs.taxonomy import SemanticTag
from src.models.judge import IdentityVerdict
from src.models.templates_events import EventArchetype
from src.custom_program import LocalStructuredProgram
from src.ingestion.graph_schemas import MoleculeType
from src.debug.telemetry import telemetry, EventType

# === МОДЕЛИ СИНТЕЗА ===

class SynthesizedProfile(BaseModel):
    """
    Чистовой профиль сущности.
    """
    canonical_name: str = Field(description="The most correct, formal name for this entity.")
    summary: str = Field(description="A comprehensive, deep biography/description synthesizing all observations.")
    known_aliases: List[str] = Field(description="List of other names/titles this entity is known by in the text.")
    visual_traits: List[str] = Field(description="Physical characteristics (e.g. 'blonde', 'rusty', 'glowing').")
    personality_traits: List[str] = Field(description="Psychological traits (e.g. 'anxious', 'authoritative').")
    narrative_role_desc: str = Field(description="Brief explanation of their role in the story (e.g. 'The antagonist who steals the key').")
    importance_score: int = Field(
        description="Rating 1-10. How critical is this entity to the plot? "
                    "1=Background noise/One-off mention. 10=Protagonist/Key Item."
    )

class MergeDecision(BaseModel):
    is_same_entity: bool = Field(description="True if Entity A and Entity B refer to the exact same narrative figure.")
    confidence: float = Field(description="Confidence score 0.0-1.0.")
    reasoning: str = Field(description="Why? e.g. 'Both have white fur and a watch' vs 'One is a cat, one is a rabbit'.")

class SynthesizedEpisode(BaseModel):
    title: str = Field(description="A dramatic title for the scene.")
    summary: str = Field(description="A detailed chronicle of the event.")
    key_participants: List[str] = Field(description="Names of entities crucial to this scene.")
    significance_score: int = Field(description="1-10. 1=Filler, 10=Major Plot Point.")
    archetype: EventArchetype = Field(description="The core gameplay archetype of this scene.")
    dominant_tags: List[SemanticTag] = Field(description="3-5 tags defining the mood and mechanics.")
    start_tick: int
    end_tick: int

class SynthesizedLocation(BaseModel):
    canonical_name: str = Field(description="Official name (e.g. 'The Grand Hall').")
    summary: str = Field(description="Architectural and sensory description.")
    geometry_tags: List[str] = Field(description="Tags: 'narrow', 'vertical', 'open', 'hub', 'labyrinth'.")
    material_tags: List[str] = Field(description="Tags: 'stone', 'wood', 'flesh', 'void'.")
    detected_exits: List[str] = Field(description="Mentioned exits.")
    importance_score: int = Field(description="1-10.")

class EntitySynthesizer:
    def __init__(self, llm):
        self.llm = llm
        
        # === PRIMARY STORAGE (UID-based) ===
        # Хранилище подтвержденных фактов: UID -> Список наблюдений
        self._dossiers: Dict[str, List[str]] = defaultdict(list)
        # Хранилище синонимов: UID -> Set("The Cat", "Cheshire Cat")
        self._aliases: Dict[str, Set[str]] = defaultdict(set)
        
        self._scene_dossiers: Dict[str, List[Tuple[int, str]]] = defaultdict(list)
        self._location_dossiers: Dict[str, List[str]] = defaultdict(list)
        
        self._metadata: Dict[str, Dict[str, Any]] = {}
        self._redirect_map: Dict[str, str] = {}

        # === LAZY STORAGE (String-based) ===
        # Ведра для сбора фактов до разрешения UID.
        # Key: Normalized Name (str) -> Content
        self._buckets: Dict[str, Dict] = defaultdict(lambda: {
            "observations": [], 
            "aliases": set(), 
            "metadata": {}
        })
        
        # Буфер для неоднозначных местоимений
        self._ambiguous_buffer: List[Dict] = []

        # === PROMPTS ===
        self._init_programs()

    def _init_programs(self):
        self.profile_prompt = PromptTemplate(
            "You are a World Archivist. Analyze the gathered notes about '{name}' ({category}).\n"
            "KNOWN ALIASES: {aliases}\n\n"
            "RAW NOTES:\n{notes}\n\n"
            "CRITICAL INSTRUCTION ON UNCERTAIN DATA:\n"
            "- Some notes are marked `[UNCERTAIN]`. This means the source text used a pronoun (e.g. 'She') "
            "and it could refer to this entity OR someone else.\n"
            "- **VALIDATE BY CHARACTER**: Does this action fit the established personality of {name}?\n"
            "   - Example: If {name} is 'Alice' (polite child), exclude `[UNCERTAIN] shouted 'Off with his head!'`.\n"
            "   - Example: If {name} is 'Queen', INCLUDE it.\n"
            "- If valid, incorporate it into the summary naturally (remove the tag).\n"
            "- If invalid/contradictory, DISCARD it.\n\n"
            "TASK:\n"
            "1. **Assess Importance**: Rate 1-10.\n"
            "2. **Canonical Name**: Best formal name.\n"
            "3. **Synthesize**: Create a deep profile.\n"
        )
        self.profile_program = LocalStructuredProgram(
            output_cls=SynthesizedProfile,
            llm=self.llm,
            prompt=self.profile_prompt,
            verbose=True,
            api_key=config.llm.api_key,
            base_url=config.llm.base_url
        )

        self.episode_prompt = PromptTemplate(
            "You are a Royal Chronicler. Log actions.\nNOTES:\n{notes}\n"
        )
        self.episode_program = LocalStructuredProgram(
            output_cls=SynthesizedEpisode,
            llm=self.llm,
            prompt=self.episode_prompt,
            verbose=True,
            api_key=config.llm.api_key,
            base_url=config.llm.base_url
        )

        self.judge_prompt = PromptTemplate(
            "Determine if ENTITY A and ENTITY B are the same.\n"
            "A ({name_a}): {notes_a}\n"
            "B ({name_b}): {notes_b}\n"
        )
        self.judge_program = LocalStructuredProgram(
            output_cls=MergeDecision,
            llm=self.llm,
            prompt=self.judge_prompt, 
            verbose=True,
            api_key=config.llm.api_key,
            base_url=config.llm.base_url
        )

        self.location_program = LocalStructuredProgram(
            output_cls=SynthesizedLocation,
            llm=self.llm,
            prompt=PromptTemplate("Analyze location '{name}'. Notes:\n{notes}"),
            verbose=True,
            api_key=config.llm.api_key,
            base_url=config.llm.base_url
        )

    # =========================================================================
    # COLLECTION METHODS (Input Funnel)
    # =========================================================================

    def collect(self, uid: str, observation: str, metadata: Dict[str, Any] = None):
        """Trusted method: Add observation to a specific UID."""
        if not observation: return
        self._dossiers[uid].append(observation)

        # можно более интеллектуально это добавлять
        telemetry.emit(EventType.STATE_SNAP, f"Fact added for {uid}", {"obs": observation})
        
        if metadata:
            name = metadata.get('name')
            if name: self._aliases[uid].add(name)
            
            if uid not in self._metadata:
                self._metadata[uid] = metadata
            else:
                old_name = self._metadata[uid].get('name', '')
                if len(name or "") > len(old_name):
                    self._metadata[uid] = metadata

    def collect_by_name(self, name: str, observation: str, 
                        aliases: Optional[List[str]] = None, 
                        metadata: Optional[Dict[str, Any]] = None):
        """Spotlight method: Add to Name Bucket."""
        if not name or not observation: return
        
        key = name.strip() 
        bucket = self._buckets[key]
        
        bucket["observations"].append(observation)
        if aliases:
            bucket["aliases"].update(aliases)
        bucket["aliases"].add(name)
        
        if metadata:
            bucket["metadata"].update(metadata)

    def collect_ambiguous(self, ref_text: str, observation: str, candidates: List[str]):
        """Store pronouns for later resolution."""
        self._ambiguous_buffer.append({
            "ref": ref_text,
            "obs": observation,
            "candidates": candidates
        })

    def collect_location_observation(self, loc_id: str, text: str, name: str):
        if text and len(text) > 5:
            self._location_dossiers[loc_id].append(text)
            if loc_id not in self._metadata:
                self._metadata[loc_id] = {"name": name, "category": "LOCATION"}
            else:
                # Обновляем имя, если нашли более полное
                curr = self._metadata[loc_id].get("name", "")
                if len(name) > len(curr):
                     self._metadata[loc_id]["name"] = name

    def collect_scene_beat(self, loc_id: str, beat_text: str, tick: int):
        if beat_text and len(beat_text) > 5:
            self._scene_dossiers[loc_id].append((tick, beat_text))

    # =========================================================================
    # RESOLUTION & SYNTHESIS
    # =========================================================================

    def finalize_entities(self):
        """
        Главный метод: Местоимения -> Ведра -> Досье -> Консолидация.
        """
        telemetry.emit(
            EventType.STEP_INFO, 
            "Start Entity Resolution", 
            {
                "buckets_count": len(self._buckets),
                "ambiguous_buffer": len(self._ambiguous_buffer)
            }
        )
        print(f"🧹 Finalizing Entities: {len(self._ambiguous_buffer)} ambiguous refs, {len(self._buckets)} buckets.")
        
        # 1. Resolve Pronouns
        self._resolve_ambiguous_buffer()
        
        # 2. Flush Buckets (String -> UID)
        self._flush_buckets_to_dossiers()
        
        # 3. Merge Duplicates (UID -> UID)
        self.consolidate_dossiers()

        # После слияния
        telemetry.emit(
            EventType.STATE_SNAP,
            "Resolution Complete",
            data={
                "final_entities_count": len(self._dossiers),
                "merged_redirects": len(self._redirect_map),
                "top_entities": [
                    # Выводим топ-5 самых "жирных" досье для проверки
                    (k, len(v), self._metadata.get(k, {}).get('name')) 
                    for k, v in sorted(self._dossiers.items(), key=lambda x: len(x[1]), reverse=True)[:15]
                ]
            }
        )

    def _resolve_ambiguous_buffer(self):
        """
        Разбирает буфер местоимений. 
        Логика: Если кандидатов несколько, мы раздаем факт ВСЕМ, 
        но с пометкой [UNCERTAIN], чтобы LLM на этапе синтеза решила, 
        кому это свойственно по характеру.
        """
        resolved_count = 0
        speculative_count = 0
        
        for entry in self._ambiguous_buffer:
            candidates = entry["candidates"]
            # Очищаем список кандидатов от мусора (пустых строк)
            candidates = [c for c in candidates if c]
            
            raw_obs = entry['obs']
            ref_text = entry['ref'] # "She", "The ruler"
            
            if not candidates:
                continue
                
            # СЛУЧАЙ 1: Кандидат один -> Уверенное присвоение
            if len(candidates) == 1:
                target_name = candidates[0]
                obs = f"[{ref_text}] {raw_obs}" # "[She] laughed"
                self.collect_by_name(target_name, obs)
                resolved_count += 1
                
            # СЛУЧАЙ 2: Кандидатов несколько -> Суперпозиция
            else:
                # Пример: Candidates=["Alice", "Red Queen"], Obs="shouted 'Off with his head!'"
                # Мы запишем этот факт обоим.
                
                for cand in candidates:
                    # Маркер для LLM-архивариуса
                    speculative_obs = (
                        f"[UNCERTAIN: Could be {', '.join(candidates)}] "
                        f"{raw_obs} (Context: {ref_text})"
                    )
                    self.collect_by_name(cand, speculative_obs)
                
                speculative_count += 1
                
        # Очищаем буфер
        self._ambiguous_buffer = []
        print(f"   ✨ Ambiguity Resolution: {resolved_count} direct, {speculative_count} distributed to multiple.")

    def _flush_buckets_to_dossiers(self):
        """
        Переносит данные из временных ведер в постоянные досье.
        """
        print(f"   🚰 Flushing {len(self._buckets)} buckets...")
        
        # Индекс существующих UID для быстрого поиска
        uid_name_map = {uid: m.get("name", "").lower() for uid, m in self._metadata.items()}
        
        for name_key, bucket in self._buckets.items():
            norm_name = name_key.lower().strip()
            observations = bucket["observations"]
            aliases = bucket["aliases"]
            meta = bucket["metadata"]
            
            match_uid = None
            
            # 1. Прямой поиск
            for uid, known_name in uid_name_map.items():
                if norm_name == known_name:
                    match_uid = uid
                    break
            
            # 2. Fuzzy поиск (если прямого нет)
            if not match_uid:
                best_score = 0
                for uid, known_name in uid_name_map.items():
                    score = fuzz.ratio(norm_name, known_name)
                    if score > 90:
                        if score > best_score:
                            best_score = score
                            match_uid = uid
            
            # 3. Слияние или Создание
            if match_uid:
                self._dossiers[match_uid].extend(observations)
                self._aliases[match_uid].update(aliases)
                if meta and len(meta.get("name", "")) > len(self._metadata[match_uid].get("name", "")):
                    self._metadata[match_uid].update(meta)
            else:
                new_uid = str(uuid.uuid4())
                self._dossiers[new_uid] = observations
                self._aliases[new_uid] = aliases
                
                if not meta:
                    meta = {"name": name_key, "category": "UNKNOWN"}
                self._metadata[new_uid] = meta
                
                # Добавляем в локальный индекс, чтобы следующие ведра могли прилипнуть сюда
                uid_name_map[new_uid] = norm_name

        self._buckets.clear()

    def consolidate_dossiers(self):
        """
        Склейка дубликатов сущностей (Merge by ID).
        """
        print(f"🧹 Running UID Consolidation...")
        by_category = defaultdict(list)
        for uid, meta in self._metadata.items():
            cat = meta.get('category', 'UNKNOWN')
            by_category[cat].append(uid)

        remap_count = 0
        
        for cat, uids in by_category.items():
            uids.sort(key=lambda u: len(self._metadata[u].get('name', '')), reverse=True)
            processed = set()
            
            for i in range(len(uids)):
                main_uid = uids[i]
                if main_uid in processed: continue
                main_name = self._metadata[main_uid].get('name', '').lower()
                
                for j in range(i + 1, len(uids)):
                    cand_uid = uids[j]
                    if cand_uid in processed: continue
                    cand_name = self._metadata[cand_uid].get('name', '').lower()
                    
                    should_merge = False
                    
                    # Имя
                    if fuzz.ratio(main_name, cand_name) > 88: should_merge = True
                    elif cand_name in main_name and len(cand_name) > 4: should_merge = True
                    
                    # Алиасы (Новая логика)
                    if not should_merge:
                        aliases_main = {a.lower() for a in self._aliases[main_uid]}
                        aliases_cand = {a.lower() for a in self._aliases[cand_uid]}
                        # Если есть пересечение синонимов (кроме совсем коротких)
                        intersection = [x for x in aliases_main.intersection(aliases_cand) if len(x) > 3]
                        if intersection:
                            should_merge = True

                    if should_merge:
                        self._dossiers[main_uid].extend(self._dossiers[cand_uid])
                        self._aliases[main_uid].update(self._aliases[cand_uid])
                        self._redirect_map[cand_uid] = main_uid
                        processed.add(cand_uid)
                        remap_count += 1
                        
        print(f"✅ Entity consolidation complete. Merged {remap_count} duplicates.")

    def consolidate_locations(self):
        """
        Склейка дубликатов локаций.
        """
        print(f"🏰 Consolidating Locations...")
        uids = list(self._location_dossiers.keys())
        uids.sort(key=lambda u: len(self._metadata.get(u, {}).get('name', '')), reverse=True)
        
        processed = set()
        remap_count = 0
        
        for i in range(len(uids)):
            main_uid = uids[i]
            if main_uid in processed: continue
            main_name = self._metadata.get(main_uid, {}).get('name', '').lower()
            
            for j in range(i + 1, len(uids)):
                cand_uid = uids[j]
                if cand_uid in processed: continue
                cand_name = self._metadata.get(cand_uid, {}).get('name', '').lower()
                
                should_merge = False
                
                # 1. Fuzzy Name
                if fuzz.ratio(main_name, cand_name) > 85:
                    should_merge = True
                    print(f'SYN: {main_name}, {cand_name} has merged!')
                elif cand_name in main_name and len(cand_name) > 4:
                    # "Dark Hall" in "The Dark Hall"
                    should_merge = True
                    print(f'SYN: {main_name}, {cand_name} has merged!')
                else:
                    print(f'SYN: {main_name}, {cand_name} has NOT merged!')
                    
                if should_merge:
                    # Слияние наблюдений
                    self._location_dossiers[main_uid].extend(self._location_dossiers[cand_uid])
                    
                    # Слияние сцен (событий), происходивших в этих локациях
                    if cand_uid in self._scene_dossiers:
                        self._scene_dossiers[main_uid].extend(self._scene_dossiers[cand_uid])
                        # Сортируем по времени после слияния
                        self._scene_dossiers[main_uid].sort(key=lambda x: x[0])
                    
                    self._redirect_map[cand_uid] = main_uid
                    processed.add(cand_uid)
                    remap_count += 1
                    
        print(f"✅ Location consolidation complete. Merged {remap_count} duplicates.")

    def synthesize_profile(self, uid: str) -> Optional[Tuple[SynthesizedProfile, str]]:
        if uid in self._redirect_map: return None

        notes = self._dossiers.get(uid, [])
        if not notes: return None

        meta = self._metadata.get(uid, {})
        category = meta.get('category', 'UNKNOWN')

        if len(notes) < 2 and category != 'ASSET':
             return None

        # Собираем алиасы для контекста
        aliases_list = list(self._aliases[uid])
        aliases_str = ", ".join(aliases_list[:10])

        try:
            profile = self.profile_program(
                name=meta.get('name', 'Unknown'), 
                category=category, 
                aliases=aliases_str, # <--- Передаем в промпт
                notes="\n- ".join(set(notes[:60]))
            )
            
            if profile.importance_score < 3:
                return None
            
            return profile, uid
            
        except Exception as e:
            print(f"Error synthesizing {uid}: {e}")
            return None

    # === HELPERS FOR EPISODES (Unchanged) ===
    
    def synthesize_location(self, loc_id: str) -> Optional[SynthesizedLocation]:
        if loc_id in self._redirect_map: return None
        notes = self._location_dossiers.get(loc_id, [])
        if not notes: return None
        meta = self._metadata.get(loc_id, {})
        try:
            return self.location_program(name=meta.get("name"), notes="\n- ".join(set(notes[:50])))
        except Exception: return None

    def synthesize_episodes_for_loc(self, loc_id: str) -> List[SynthesizedEpisode]:
        # Если локация была слита, берем данные из "родителя"
        if loc_id in self._redirect_map: return [] 
        
        raw_beats = self._scene_dossiers.get(loc_id, [])
        if not raw_beats: return []
        
        clusters = self._cluster_beats(raw_beats)
        results = []
        for cluster in clusters:
            if len(cluster) < 2: continue
            try:
                ep = self.episode_program(notes="\n- ".join([b[1] for b in cluster]))
                ep.start_tick = cluster[0][0]
                ep.end_tick = cluster[-1][0]
                results.append(ep)
            except Exception: pass
        return results

    def _cluster_beats(self, beats: List[Tuple[int, str]], gap_threshold: int = 15):
        if not beats: return []
        beats.sort(key=lambda x: x[0])
        clusters = []
        current = [beats[0]]
        for i in range(1, len(beats)):
            if beats[i][0] - beats[i-1][0] > gap_threshold:
                clusters.append(current)
                current = []
            current.append(beats[i])
        if current: clusters.append(current)
        return clusters
    
    def get_raw_observations(self, uid: str) -> List[str]:
        return self._dossiers.get(uid, [])
    