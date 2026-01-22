from __future__ import annotations
import uuid
import logging
from typing import TYPE_CHECKING, List, Tuple, Optional, Dict
from llama_index.core import PromptTemplate
from qdrant_client.models import PointStruct

from src.ingestion.graph_schemas import SceneEventBatch, GraphEvent
from src.ingestion.game_math import GameMath
from src.registries.all_registries import EVENTS
from src.custom_program import LocalStructuredProgram as LLMTextCompletionProgram
from src.config import config

if TYPE_CHECKING:
    from src.pipeline.context import PipelineContext

class ChronicleWeaver:
    """
    Worker 3: Narrative Chronicle.
    Строит граф событий (Event Graph), обрабатывает время и связывает действия с сущностями.
    """
    def __init__(self, ctx: PipelineContext):
        self.ctx = ctx
        self._init_program()
        self.global_tick = 0
        self.last_scene_uuid = None

    def _init_program(self):
        prompt = PromptTemplate(
            "Analyze the SCENE. Extract chain of EVENTS (Beats) in chronological order.\n"
            "Focus on significant actions. Identify flashbacks.\n"
            "If possible, list the 'participants' (names) involved in each beat.\n"
            "SCENE TEXT:\n{text}\n"
        )
        self.program = LLMTextCompletionProgram(
            output_cls=SceneEventBatch,
            llm=self.ctx.llm,
            prompt=prompt,
            verbose=True,
            api_key=config.llm.api_key,
            base_url=config.llm.base_url
        )

    def weave(self, full_text: str, scene_ranges: List[tuple], source_doc: str, source_id: str):
        print(f"   🎬 Pass 3: Weaving Chronicle...")
        
        self.global_tick = 0
        self.last_scene_uuid = None
        last_beat_uuid = None

        for start, end, loc_uuid, context_data in scene_ranges:
            text = full_text[start:end]
            if len(text) < 50: continue

            # === 1. PREPARE CAST MAP (Name -> UUID) ===
            # Это и есть реализация вашего плана: мы готовим "Золотой список" для этой сцены.
            scene_cast_names: List[str] = context_data.get("cast", [])
            scene_cast_map: Dict[str, str] = {} # "Alice" -> "uuid-123"
            
            for name in scene_cast_names:
                # Используем резолвер, чтобы найти UUID по имени.
                # Так как реестр уже загружен в GraphBuilder, это будет быстрый lookup.
                uid = self.ctx.resolver.resolve_name(name, loc_uuid) 
                if uid:
                    scene_cast_map[name] = uid
                else:
                    # Если вдруг не нашли (редкость), можно попробовать создать Shadow, 
                    # но лучше просто пропустить, чтобы не плодить мусор.
                    pass
            
            # Список приоритетных UUID для этой сцены (передадим в резолвер событий)
            priority_uids = list(scene_cast_map.values())

            # === 2. LLM EXTRACTION ===
            prompt_in = f"[SCENE: {context_data.get('label', 'Unknown')}]\n{text}"
            try:
                res: SceneEventBatch = self.program(text=prompt_in)
            except Exception as e:
                logging.error(f"Chronicle extraction failed: {e}")
                continue
            
            if not res.events: continue

            # === 3. MACRO: REGISTER EPISODE ===
            scene_uuid = self._register_episode(res, loc_uuid, source_id, self.global_tick + 1)

            # === 4. MICRO: PROCESS BEATS ===
            for beat in res.events:
                last_beat_uuid = self._process_beat(
                    beat=beat,
                    scene_uuid=scene_uuid,
                    prev_beat_id=last_beat_uuid,
                    source_doc=source_doc,
                    source_id=source_id,
                    
                    # Передаем контекст сцены
                    loc_uuid=loc_uuid,           # <--- Место действия
                    scene_cast_map=scene_cast_map, # <--- Словарь имен (для поиска в тексте)
                    priority_uids=priority_uids,   # <--- Приоритеты для LLM резолвера
                    full_scene_text=text           # <--- Текст сцены для контекста LLM
                )

    def _register_episode(self, data: SceneEventBatch, loc_uuid: str, source_id: str, start_tick: int) -> str:
        uid = str(uuid.uuid4())
        
        full_text = f"{data.scene_title}. {data.scene_summary}"
        vec = self.ctx.embedder.get_text_embedding(full_text)
        
        # Neo4j
        self.ctx.repos.chronicle.upsert_episode(
            uid=uid, name=data.scene_title, summary=data.scene_summary,
            tick=start_tick, location_id=loc_uuid
        )
        
        if self.last_scene_uuid:
            self.ctx.repos.chronicle.link_episode_chain(self.last_scene_uuid, uid)
        self.last_scene_uuid = uid
        
        # Qdrant Draft (Full data comes in Synthesis)
        self.ctx.qdrant.upsert("chronicle", [PointStruct(
            id=uid, vector=vec, payload={
                "name": data.scene_title, "type": "episode", 
                "source_id": source_id, "tick": start_tick
            }
        )])
        return uid

    def _process_beat(self, beat: GraphEvent, scene_uuid: str, prev_beat_id: str, 
                      source_doc: str, source_id: str, 
                      loc_uuid: str, 
                      scene_cast_map: Dict[str, str], # Для текстового поиска
                      priority_uids: List[str],       # Для LLM резолвера
                      full_scene_text: str) -> str:
        
        # --- A. CONTINUATION ---
        if beat.is_continuation and prev_beat_id:
            self.ctx.repos.chronicle.append_description(prev_beat_id, beat.description)
            return prev_beat_id

        # --- B. FLASHBACK ---
        if beat.is_flashback:
            # Тот самый метод, который вы просили (_find_historic_event)
            historic_id = self._find_historic_event(beat.description)
            
            if historic_id:
                if prev_beat_id:
                    self.ctx.repos.chronicle.link_recollection(prev_beat_id, historic_id)
            else:
                # Detached Memory
                # TODO: stats!
                mem_id = str(uuid.uuid4())
                self.ctx.repos.chronicle.upsert_event(
                    uid=mem_id, name=beat.name, tick_estimate=-1, 
                    archetype_id="memory"
                )
                if prev_beat_id:
                    self.ctx.repos.chronicle.link_recollection(prev_beat_id, mem_id)
                
                vec = self.ctx.embedder.get_text_embedding(beat.description)
                self.ctx.qdrant.upsert("chronicle", [PointStruct(
                    id=mem_id, vector=vec, payload={
                        "name": beat.name, "description": beat.description,
                        "type": "memory", "source_id": source_id, "source_doc": source_doc
                    }
                )])
            return prev_beat_id 

        # --- C. STANDARD EVENT ---
        self.global_tick += 1
        evt_uuid = str(uuid.uuid4())
        
        # 1. Math & Projection
        full_text = f"{beat.name}. {beat.description}"
        vec = self.ctx.embedder.get_text_embedding(full_text)
        raw_stats = self.ctx.projector.project(vec)
        
        arch_id = None
        if self.ctx.options.project_events:
            arch_id = self.ctx.classifier.classify(full_text, EVENTS, top_k=1)
        
        final_stats = GameMath.calculate_stats(raw_stats, {}, arch_id or "generic", is_event=True)

        # 2. === PARTICIPANT RESOLUTION (HYBRID) ===
        involved_uids = set()
        
        # Стратегия 1: LLM Participants (Явный список)
        # Если экстрактор вернул имена в beat.participants
        raw_candidates = beat.participants if beat.participants else []
        
        # Стратегия 2: Fallback Text Match (Если список пуст)
        # Ищем имена участников сцены в тексте описания
        if not raw_candidates:
            beat_text_lower = beat.description.lower()
            for name in scene_cast_map.keys():
                if name.lower() in beat_text_lower:
                    raw_candidates.append(name)

        # Стратегия 3: Advanced Resolver
        for name in raw_candidates:
            # Вызываем наш новый крутой Resolver
            # Он попробует найти имя в реестре, а если не найдет — использует LLM
            # с передачей full_scene_text и priority_uids
            uid = self.ctx.resolver.resolve(
                name_query=name,
                context_text=full_scene_text, # Контекст для "She"
                scene_cast_uids=priority_uids # Подсказка для LLM
            )
            
            if uid:
                involved_uids.add(uid)

        # 3. NEO4J SAVE
        self.ctx.repos.chronicle.upsert_event(
            uid=evt_uuid, name=beat.name, tick_estimate=self.global_tick,
            stats=final_stats, archetype_id=arch_id
        )
        # Сцена содержит событие
        self.ctx.repos.chronicle.link_event_hierarchy(scene_uuid, evt_uuid) 
        # Событие произошло в локации
        self.ctx.repos.chronicle.link_event_location(evt_uuid, loc_uuid) 
        
        if prev_beat_id:
            self.ctx.repos.chronicle.link_next_event(prev_beat_id, evt_uuid)

        # 4. HISTORY LINKING (Event -> Molecule)
        for part_id in involved_uids:
            self.ctx.repos.chronicle.link_participant(evt_uuid, part_id)

        # 5. CAUSALITY
        # if prev_beat_id and beat.causal_tag and beat.causal_tag != "NONE":
        #     self.ctx.repos.chronicle.link_causality(prev_beat_id, evt_uuid, beat.causal_tag)

        # 6. QDRANT SAVE
        self.ctx.qdrant.upsert("chronicle", [PointStruct(
            id=evt_uuid, vector=vec, payload={
                "name": beat.name, "description": beat.description,
                "type": "beat", "tick": self.global_tick,
                "stats": final_stats, "source_id": source_id,
                "parent_scene_id": scene_uuid,
                "participant_ids": list(involved_uids) # Для фильтрации
            }
        )])
        
        return evt_uuid
    
    def _find_historic_event(self, query_text: str, threshold: float = 0.7) -> Optional[str]:
        """
        Ищет событие в ПРОШЛОМ (коллекция 'chronicle'), похожее по описанию.
        """
        # Векторизуем описание воспоминания
        query_vec = self.ctx.embedder.get_text_embedding(query_text)
        
        # Ищем в Qdrant (коллекция chronicle уже должна существовать)
        if not self.ctx.qdrant.collection_exists("chronicle"):
            return None

        # Ищем только среди реальных событий (не 'memory'), и только те, что уже произошли
        # (фильтрацию по tick сложно сделать эффективно без payload index, пока просто search)
        result = self.ctx.qdrant.query_points(
            collection_name="chronicle",
            query=query_vec,
            limit=1,
            # Можно добавить фильтр, чтобы не искать среди самих же воспоминаний
            # query_filter=models.Filter(...) 
        )
        
        hits = result.points
        if hits and hits[0].score > threshold:
            # Нашли похожее событие!
            found_name = hits[0].payload.get('name', 'Unknown')
            print(f"         🧠 Dejavu: '{query_text[:20]}...' ≈ '{found_name}' ({hits[0].score:.2f})")
            return hits[0].id
            
        return None
    