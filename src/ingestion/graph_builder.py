import uuid
import logging
from typing import Dict, List, Optional, Tuple
from llama_index.core.node_parser import TokenTextSplitter
from llama_index.core import PromptTemplate
#from llama_index.core.program import LLMTextCompletionProgram
from llama_index.llms.openai_like import OpenAILike
from llama_index.embeddings.openai_like import OpenAILikeEmbedding
from llama_index.core.base.embeddings.base import Embedding
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
from llama_index.core import Document
from llama_index.core.schema import BaseNode
from llama_index.core.schema import MetadataMode

from src.infrastructure.llama_adapter import SmartLlamaLLM
from src.infrastructure.smart_client import SmartOpenAI
from src.ingestion.scene_splitter import SemanticSceneSplitter
from src.ingestion.synthesizer import EntitySynthesizer
from src.config import config, PipelineOptions
from src.registries.all_registries import TOPOLOGIES, EVENTS
from src.database.graph_db import Neo4jConnector
from src.custom_program import LocalStructuredProgram as LLMTextCompletionProgram
from src.ingestion.classifier import HybridClassifier
from src.ingestion.graph_schemas import AssetSubtype, CausalLink, DetectedEntity, EntityBatch, GraphEvent, GraphLocation, LocationConnection, SceneBatch, SceneEventBatch, SkeletonBatch
#from src.ingestion.mappers import RELATIONS
from src.ingestion.semantic_projector import SemanticProjector


class GraphBuilder:
    def __init__(self, synthesizer=None, options: PipelineOptions = PipelineOptions()):
        """
        Инициализация GraphBuilder с поддержкой опций пайплайна.
        """
        # 1. Models
        # self.llm = OpenAILike(model=config.llm.model_name, 
        #                   api_base=config.llm.base_url,
        #                   temperature=0.1)
        # 1. ЯДРО: Smart Client (для прямого доступа и Structured Outputs)
        self.smart_client = SmartOpenAI(
            api_key=config.llm.api_key,
            base_url=config.llm.base_url,
            cache_dir="cache/global_llm"
        )
        
        # 2. ОБЕРТКА: LlamaIndex LLM (для индексов и ретриверов)
        self.llm = SmartLlamaLLM(
            model_name=config.llm.model_name,
            smart_client=self.smart_client
        )
        self.embedder = OpenAILikeEmbedding(
                        model_name=config.vector.model_name,
                        api_base=config.vector.base_url,
                        api_key=config.vector.api_key
        )
        self.classifier = HybridClassifier(self.llm)
        self.projector = SemanticProjector(self.embedder)
        if synthesizer:
            self.synthesizer = synthesizer
        else:
            self.synthesizer = EntitySynthesizer(self.llm)

        # 2. DB Connections
        self.neo4j = Neo4jConnector(uri=config.neo4j.uri, user=config.neo4j.user, password=config.neo4j.password)
        self.qdrant = QdrantClient(url=config.qdrant.url)
        self._init_lookup_collection()

        # 3. Macro-Splitter
        # self.macro_splitter = TokenTextSplitter(
        #     chunk_size=4_000, 
        #     chunk_overlap=250,
        #     separator="\n\n"
        # )
        self.macro_splitter = SemanticSceneSplitter(llm=self.llm, window_size=30_000)

        # 4. === Programs ===
        self._init_programs()

        # 5. Runtime State (Global Registries)
        self.global_entity_registry: Dict[str, str] = {} # Name -> UUID
        self.scene_map: Dict[int, str] = {} # Chunk_Index -> Location_UUID
        
        # 5. Pipeline Options (NEW)
        self.options = options
    
    def _init_programs(self):
        """Инициализация LLM программ с чистыми промптами (без JSON схем)."""
        
        # A. ENTITY EXTRACTOR PROMPT [cite: 19]
        # Мы объясняем суть типов, но формат оставляет Pydantic
        entity_prompt = PromptTemplate(
            "Analyze the narrative text. Extract persistent 'Canonical Molecules'.\n"
            "Classify them into 6 types based on function:\n\n"
            "1. AGENT: Living beings (Characters, Monsters).\n"
            "2. GROUP: Social structures (Factions, Armies).\n"
            "3. ASSET: Material objects, NOT living beings. Subtypes: 'ARTIFACT' (Unique/Named) vs 'COMMODITY' (Fungible/Resource).\n"
            "4. LOCATION: Physical places or Biomes.\n"
            "5. CONSTRUCT: Skills, Spells, Tech, Phenomena.\n"
            "6. LORE: Secrets, Legends, Information.\n\n"
            "RULES:\n"
            "- Ignore transient items (e.g. 'a cup' unless critical).\n"
            "- Merge synonyms ('The Cat' = 'Cheshire Cat').\n"
            "- Extract 'Fireball' as a CONSTRUCT, not an object.\n\n"
            "TEXT:\n{text}\n"
        )
        self.entity_program = LLMTextCompletionProgram(
            output_cls=EntityBatch,
            llm=self.llm,
            prompt=entity_prompt,
            verbose=True,
            api_key=config.llm.api_key,
            base_url=config.llm.base_url
        )

        # B. SCENE SEGMENTATION PROMPT
        # Вместо сложного Resolver'а просто спрашиваем "Где мы?" для каждого куска
        scene_prompt = PromptTemplate(
            "Analyze the text chunk. Identify the PRIMARY physical location where the events occur.\n"
            "If the location changes, identify the dominant one.\n"
            "Provide a brief summary of the scene.\n\n"
            "TEXT:\n{text}\n"
        )
        self.scene_program = LLMTextCompletionProgram(
            output_cls=SceneBatch,
            llm=self.llm,
            prompt=scene_prompt,
            verbose=True,
            api_key=config.llm.api_key,
            base_url=config.llm.base_url
        )

        event_prompt = PromptTemplate(
            "Analyze the following SCENE from a story.\n"
            "Extract the chain of EVENTS (Beats) in strict chronological order.\n"
            "Granularity: Focus on significant actions and changes in state.\n"
            "- Good: 'Alice sees the rabbit', 'Alice chases the rabbit', 'Alice falls'.\n"
            "- Bad: 'Alice went on an adventure' (Too abstract).\n\n"
            "SCENE TEXT:\n{text}\n"
        )
        self.event_program = LLMTextCompletionProgram(
            output_cls=SceneEventBatch,
            llm=self.llm,
            prompt=event_prompt,
            verbose=True,
            api_key=config.llm.api_key,
            base_url=config.llm.base_url
        )

    def _find_historic_event(self, query_text: str, threshold: float = 0.85) -> Optional[str]:
        """
        Ищет событие в ПРОШЛОМ (уже записанном в Qdrant).
        """
        vec = self.embedder.get_text_embedding(query_text)
        
        # Важно: ищем в коллекции chronicle
        if not self.qdrant.collection_exists("chronicle"):
            return None

        result = self.qdrant.query_points(
            collection_name="chronicle",
            query=vec,
            limit=1
        )
        
        hits = result.points
        if hits and hits[0].score > threshold:
            existing_name = hits[0].payload.get('name', 'Unknown')
            print(f"         🕰️ Detected Flashback: '{query_text[:30]}...' -> '{existing_name}' ({hits[0].score:.2f})")
            return hits[0].id
        return None

    def _pass_3_chronicle(self, full_text: str, scene_ranges: List[Tuple[int, int, str, dict]], source_doc: str):
        """
        Проход 3: Хроника и Сюжет.
        Строит иерархический граф: (Scene) -> [CONTAINS] -> (Events).
        Обрабатывает флешбеки, причинность и классификацию событий.
        """
        print(f"   🎬 Pass 3: Extracting Narrative Chronicle (Hierarchy Mode)...")
        
        global_tick = 0
        last_beat_uuid = None       # Курсор для связи событий (Event -> NEXT -> Event)
        last_scene_uuid = None      # Курсор для связи сцен (Scene -> NEXT -> Scene)
        
        # Проходим по заранее нарезанным сценам (из Pass 1)
        for start, end, loc_uuid, context_data in scene_ranges:
            scene_text = full_text[start:end]
            # Пропускаем слишком короткие куски (обычно мусор или заголовки)
            if len(scene_text) < 50: 
                continue
            # Если это MEMORY, мы можем пометить создаваемый Эпизод специальным флагом
            is_memory = context_data["type"] in ["MEMORY", "DREAM"]
            
            try:
                # 1. LLM генерирует структуру Сцены и список Битов
                prompt_text = f"[SCENE TYPE: {context_data['type']} | SUMMARY: {context_data['label']}]\n{scene_text}"
                response: SceneEventBatch = self.event_program(text=prompt_text)
                
                if not response.events: continue

                # =========================================================
                # LEVEL 2: MACRO (SCENE / EPISODE)
                # =========================================================
                scene_uuid = str(uuid.uuid4())
                scene_start_tick = global_tick + 1
                
                print(f"      🎬 Processing Scene: '{response.scene_title}' ({len(response.events)} beats)")

                # A. Векторизуем Сцену (для поиска Арок и RAG по эпизодам)
                # Саммари сцены лучше передает смысл для глобального сюжета, чем мелкие биты.
                scene_vec_text = f"{response.scene_title}. {response.scene_summary}"
                scene_vec = self.embedder.get_text_embedding(scene_vec_text)
                
                # B. Сохраняем Эпизод в Neo4j и вяжем к Локации
                self.neo4j.upsert_episode(
                    uid=scene_uuid,
                    name=response.scene_title,
                    summary=response.scene_summary,
                    start_tick=scene_start_tick,
                    location_id=loc_uuid
                    # Можно добавить поле is_dream в метод upsert_episode
                )
                
                # Если это MEMORY, линкуем к локации не как HAPPENED_AT, а как RECALLED_AT?
                # Для простоты пока оставляем HAPPENED_AT, но в summary будет написано "Alice remembered..."

                # C. Связываем Сцены хронологически (Цепочка эпизодов)
                if last_scene_uuid:
                    self.neo4j.link_episode_chain(last_scene_uuid, scene_uuid)

                # D. Индексируем Сцену в Qdrant
                self.qdrant.upsert("chronicle", [PointStruct(
                    id=scene_uuid,
                    vector=scene_vec,
                    payload={
                        "name": response.scene_title,
                        "description": response.scene_summary,
                        "type": "episode",      # Тип узла
                        "granularity": "macro", # Уровень детализации
                        "source": source_doc,
                        "tick": scene_start_tick
                    }
                )])

                # =========================================================
                # LEVEL 1: MICRO (BEATS / EVENTS)
                # =========================================================
                for beat in response.events:
                    
                    # --- ЛОГИКА А: ПРОДОЛЖЕНИЕ (Merge) ---
                    # Если LLM говорит, что это уточнение предыдущего действия
                    if beat.is_continuation and last_beat_uuid:
                        print(f"         📎 Merging continuation...")
                        # Дописываем описание в Neo4j
                        self.neo4j.driver.execute_query(
                            """
                            MATCH (e:Event {id: $eid})
                            SET e.description = e.description + '\n\n' + $new_desc
                            """,
                            eid=last_beat_uuid, new_desc=beat.description
                        )
                        # (Опционально: можно обновить и Qdrant payload, но это дорого.
                        # Обычно поиск находит событие и по первой части описания).
                        continue 

                    # --- ЛОГИКА Б: ФЛЕШБЕК (Recollection) ---
                    if beat.is_flashback:
                        # Пытаемся найти, о чем именно вспоминает герой
                        historic_id = self._find_historic_event(beat.description)
                        
                        if historic_id:
                            # 1. Если нашли реальное событие в прошлом
                            print(f"         🧠 Linked Flashback to History: {historic_id}")
                            if last_beat_uuid:
                                self.neo4j.driver.execute_query(
                                    "MATCH (curr:Event {id: $cid}), (old:Event {id: $oid}) MERGE (curr)-[:RECALLS]->(old)",
                                    cid=last_beat_uuid, oid=historic_id
                                )
                        else:
                            # 2. Если это "Backstory" (событие до начала игры) или ложная память
                            mem_uuid = str(uuid.uuid4())
                            print(f"         ✨ Created Detached Memory: {beat.name}")
                            
                            # Создаем событие вне времени (tick = -1)
                            self.neo4j.upsert_event(mem_uuid, beat.name, tick_estimate=-1)
                            
                            # Линкуем "воспоминание" к текущему моменту
                            if last_beat_uuid:
                                self.neo4j.driver.execute_query(
                                    "MATCH (curr:Event {id: $cid}), (mem:Event {id: $mid}) MERGE (curr)-[:RECALLS]->(mem)",
                                    cid=last_beat_uuid, mid=mem_uuid
                                )
                            
                            # Индексируем память в Qdrant (чтобы потом её можно было вспомнить)
                            mem_vec = self.embedder.get_text_embedding(beat.description)
                            self.qdrant.upsert("chronicle", [PointStruct(
                                id=mem_uuid, 
                                vector=mem_vec, 
                                payload={
                                    "name": beat.name, 
                                    "description": beat.description, 
                                    "tick": -1, 
                                    "type": "memory",
                                    "granularity": "micro"
                                }
                            )])
                        
                        # Важно: Флешбек не сдвигает last_beat_uuid и global_tick!
                        continue

                    # --- ЛОГИКА В: СТАНДАРТНЫЙ ПОТОК (Standard Beat) ---
                    global_tick += 1
                    evt_uuid = str(uuid.uuid4())
                    
                    # 1. Классификация (Hybrid Search: Vector + LLM check)
                    archetype_id = None
                    if self.options.project_events:
                        query_for_classifier = f"{beat.name}. {beat.description}"
                        archetype_id = self.classifier.classify(
                            query_text=query_for_classifier,
                            registry=EVENTS,       # Ссылка на реестр событий
                            threshold_high=0.88,
                            threshold_low=0.45,
                            top_k=5
                        )

                    # 2. Расчет игровых статов (через Projector)
                    # Если нужно, здесь можно применить маски (Bias), аналогичные молекулам
                    vec_text = f"{beat.name}. {beat.description}"
                    embedding = self.embedder.get_text_embedding(vec_text)
                    evt_stats = self.projector.project(embedding)

                    # 3. Сохранение в Neo4j
                    self.neo4j.upsert_event(
                        evt_uuid, 
                        beat.name, 
                        global_tick, 
                        archetype_id=archetype_id, 
                        semantic_stats=evt_stats
                    )
                    
                    # 4. Связи графа
                    # А. Вкладываем Бит в Сцену (Hierarchy)
                    self.neo4j.link_episode_to_event(scene_uuid, evt_uuid)
                    
                    # Б. Хронология Битов (Next)
                    if last_beat_uuid:
                        self.neo4j.driver.execute_query(
                            "MATCH (a:Event {id: $aid}), (b:Event {id: $bid}) MERGE (a)-[:NEXT]->(b)",
                            aid=last_beat_uuid, bid=evt_uuid
                        )
                    
                    # В. Причинность (Causality)
                    # Если LLM выделила явную причину (MOTIVATION / ENABLE)
                    if last_beat_uuid and beat.causal_tag and beat.causal_tag != "NONE":
                        self.neo4j.link_causality(last_beat_uuid, evt_uuid, beat.causal_tag)

                    # 5. Индексация в Qdrant
                    payload = {
                        "name": beat.name,
                        "description": beat.description,
                        "type": "beat",
                        "granularity": "micro",
                        "tick": global_tick,
                        "source": source_doc,
                        "archetype_id": archetype_id,
                        "parent_scene_id": scene_uuid, # Ссылка на родителя
                        "stats": evt_stats
                    }
                    self.qdrant.upsert("chronicle", [PointStruct(id=evt_uuid, vector=embedding, payload=payload)])
                    
                    # Сдвигаем курсор события
                    last_beat_uuid = evt_uuid

                # Сдвигаем курсор сцены
                last_scene_uuid = scene_uuid

            except Exception as e:
                logging.error(f"Error in Scene Pass (Chunk {start}-{end}): {e}", exc_info=True)

    def _resolve_or_create_location_id(self, name: str, summary: str) -> str:
        """
        Hybrid Search для дедупликации локаций.
        """
        # 1. FUZZY MATCH (Neo4j - Имена)
        fuzzy_id = self.neo4j.fuzzy_search_location(name, threshold=0.9)
        if fuzzy_id:
            return fuzzy_id

        # 2. SEMANTIC MATCH (Qdrant - Описания)
        vec_text = f"{name}. {summary}"
        query_vector = self.embedder.get_text_embedding(vec_text)
        
        result = self.qdrant.query_points(
            collection_name="skeleton_locations",
            query=query_vector,
            limit=1
        )

        hits = result.points
        
        if hits and hits[0].score > 0.92:
            existing_name = hits[0].payload.get("name", "Unknown")
            print(f"   🧠 Qdrant Semantic Match: '{name}' ≈ '{existing_name}' (Score: {hits[0].score:.2f})")
            return hits[0].id

        # 3. NO MATCH -> Create New
        return str(uuid.uuid4())

    def _init_lookup_collection(self):
        """
        Создает динамические коллекции для графа (локации-скелеты и хроники).
        """
        # skeleton_locations: для быстрого поиска "Где я?" по описанию
        if not self.qdrant.collection_exists("skeleton_locations"):
            self.qdrant.create_collection(
                collection_name="skeleton_locations",
                vectors_config=VectorParams(size=config.v_size, distance=Distance.COSINE),
                shard_number=1 # Оптимизация памяти
            )
        
        # chronicle: для поиска исторических событий (флешбеки)
        if not self.qdrant.collection_exists("chronicle"):
             self.qdrant.create_collection(
                collection_name="chronicle",
                vectors_config=VectorParams(size=config.v_size, distance=Distance.COSINE),
                shard_number=1
            )

    def build_world_skeleton(self, full_text: str, source_doc: str) -> Tuple[List[Tuple[int, int, str]], Dict[str, str]]:
        """
        Возвращает:
        1. scene_ranges: Список [(start_char, end_char, location_uuid)]
        2. entity_registry: Словарь { "canonical_name": "uuid" }
        """
        print(f"🏗️  Starting World Architecture for: {source_doc}")
        
        doc = Document(text=full_text, id_=source_doc)
        macro_nodes: List[BaseNode] = self.macro_splitter.get_nodes_from_documents([doc])
        
        # --- STEP 1: SCENE MAPPING ---
        print(f"   🗺️  Pass 1: Mapping Scenes & Locations ({len(macro_nodes)} chunks)...")
        # ВАЖНО: Передаем full_text для ручного расчета индексов
        scene_ranges = self._pass_1_scenes(macro_nodes, full_text, source_doc)
        
        # --- STEP 2: GLOBAL ENTITY REGISTRY ---
        print(f"   🧬 Pass 2: Extracting Canonical Molecules...")
        chunks_text = [n.text for n in macro_nodes] 
        self._pass_2_entities(chunks_text, source_doc)

        # --- STEP 3: CHRONICLE ---
        print(f"   🎬 Pass 3: Extracting Narrative Chronicle...")
        self._pass_3_chronicle(full_text, scene_ranges, source_doc)

        print("✅ Skeleton Build Complete.")
        return scene_ranges, self.global_entity_registry
    
    def _pass_1_scenes(self, nodes: List[BaseNode], full_text: str, source_doc: str) -> List[Tuple[int, int, str, dict]]:
        """
        Проход 1: Топология и Скелет.
        Использует метаданные от SemanticSplitter для определения границ и типов сцен.
        """
        scene_ranges = []
        text_cursor = 0 
        prev_loc_uuid = None
        
        print(f"   🕵️ Pass 1: Semantic Scene Survey...")

        for i, node in enumerate(nodes):
            # 1. Получаем текст и метаданные от Сплиттера
            # Сплиттер уже нарезал текст по смыслу, поэтому node_text — это цельная сцена.
            node_text = node.get_content(metadata_mode=MetadataMode.NONE)
            
            # Метаданные, которые мы добавили в RobustSemanticSplitter
            scene_type = node.metadata.get("scene_type", "PHYSICAL")   # PHYSICAL / MEMORY / DREAM / DOCUMENT
            context_label = node.metadata.get("context_label", "")     # "Alice enters the forest"
            
            # === РАСЧЕТ КООРДИНАТ ===
            # (Без изменений, но критично для маппинга)
            start_idx = node.metadata.get('start_char_idx')
            if start_idx is None:
                start_idx = full_text.find(node_text, text_cursor)
                if start_idx == -1:
                    start_idx = text_cursor
                end_idx = start_idx + len(node_text)
            text_cursor = end_idx
            
            # Формируем контекстный объект для передачи дальше
            context_data = {
                "type": scene_type,
                "label": context_label
            }

            try:
                # === ЛОГИКА А: МЕНТАЛЬНЫЕ СЦЕНЫ (MEMORY / DREAM) ===
                if scene_type in ["MEMORY", "DREAM", "THOUGHT"]:
                    print(f"      🧠 Detected {scene_type}: '{context_label}'")
                    
                    # Если это воспоминание, физическая локация НЕ меняется.
                    # Мы наследуем локацию, где герой стоял до этого.
                    current_loc_uuid = prev_loc_uuid
                    
                    # Если это самое начало книги и prev_loc_uuid нет — создаем "Limbo/Unknown"
                    if not current_loc_uuid:
                        current_loc_uuid = self._resolve_or_create_location_stub("Unknown Void", "Abstract space", source_doc)

                    # Мы НЕ вызываем scene_program (экономим токены), так как локация не изменилась.
                    # Но мы можем сохранить саммари в досье локации как "мысль, посетившая здесь".
                    if hasattr(self, 'synthesizer') and current_loc_uuid:
                         self.synthesizer.collect_location_observation(
                            current_loc_uuid, 
                            f"[ATMOSPHERE/THOUGHT] In this place, the character recalled: {context_label}",
                            "Current Location"
                        )

                # === ЛОГИКА Б: ФИЗИЧЕСКИЕ СЦЕНЫ (PHYSICAL) ===
                else:
                    # Это реальное перемещение. Спрашиваем LLM: "Что это за место?"
                    
                    # Впрыскиваем контекст, чтобы LLM знала, о чем речь
                    augmented_text = f"[SCENE CONTEXT: {context_label}]\n{node_text}"
                    
                    response: SceneBatch = self.scene_program(text=augmented_text)
                    
                    if not response.scenes:
                        # Если LLM не поняла, где мы — остаемся на месте
                        current_loc_uuid = prev_loc_uuid
                    else:
                        scene_data = response.scenes[0]
                        raw_name = scene_data.location_name.strip()
                        
                        # Фильтр: Если имя слишком абстрактное, игнорируем
                        if len(raw_name) < 3 or raw_name.lower() in ["unknown", "none", "location"]:
                            current_loc_uuid = prev_loc_uuid
                        else:
                            # 1. Резолвинг ID (Fuzzy/Semantic)
                            current_loc_uuid = self._resolve_or_create_location_stub(
                                raw_name, scene_data.summary, source_doc
                            )
                            
                            # 2. Досье Локации
                            if hasattr(self, 'synthesizer'):
                                self.synthesizer.collect_location_observation(
                                    current_loc_uuid, 
                                    scene_data.summary, 
                                    raw_name
                                )

                            # 3. Топология (Связь с предыдущей)
                            # Создаем связь только если это PHYSICAL -> PHYSICAL переход
                            if prev_loc_uuid and prev_loc_uuid != current_loc_uuid:
                                self.neo4j.link_locations(prev_loc_uuid, current_loc_uuid, "TRANSITION")
                                print(f"      🔗 Path: ... -> {raw_name}")

                # === ФИНАЛИЗАЦИЯ ===
                if current_loc_uuid:
                    scene_ranges.append((start_idx, end_idx, current_loc_uuid, context_data)) # <--- 4 элемента!
                    prev_loc_uuid = current_loc_uuid
                else:
                    # Fallback на случай первой сцены без локации
                    pass 

            except Exception as e:
                logging.error(f"Error in Scene Pass chunk {i}: {e}", exc_info=True)
        
        return scene_ranges

    def _pass_2_entities(self, chunks: List[str], source_doc: str):
        print(f"   🧬 Pass 2: Extracting Canonical Molecules...")
        for i, chunk in enumerate(chunks):
            try:
                response: EntityBatch = self.entity_program(text=chunk)
                
                for entity in response.entities:
                    # === НОВАЯ ЛОГИКА ===
                    if entity.category == "LOCATION":
                        # Не регистрируем как молекулу!
                        # Вместо этого ищем/создаем Stub и пишем в Досье.
                        
                        # 1. Резолвим ID (Fuzzy/Semantic Search)
                        loc_id = self._resolve_or_create_location_stub(
                            entity.name, entity.description, source_doc
                        )
                        
                        # 2. Сохраняем наблюдение в Синтезатор
                        self.synthesizer.collect_location_observation(
                            loc_id, 
                            entity.description, 
                            entity.name
                        )
                        print(f"      🏰 Collected Location Note: {entity.name}")
                        
                    else:
                        # Все остальное (Agent, Asset, Lore) — это молекулы
                        self._register_molecule(entity, source_doc)
                    
            except Exception as e:
                logging.error(f"Error in Entity Pass chunk {i}: {e}")

    def _register_molecule(self, entity: DetectedEntity, source_doc: str):
        """
        Умная регистрация: проверяет, есть ли сущность в глобальном реестре.
        Если нет -> создает, считает статы, пишет в БД.
        """
        # Нормализация имени для ключа реестра
        reg_key = entity.name.lower().strip()
        
        if reg_key in self.global_entity_registry:
            # Уже знаем такую (например, "Alice" встретилась во 2-м чанке после 1-го)
            return

        # Создаем новый ID
        mol_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, reg_key))
        self.global_entity_registry[reg_key] = mol_uuid

        print(f"      🧬 New Molecule: [{entity.category}] {entity.name} ({entity.subtype if entity.subtype else ''})")
        
        # === 1. Calculate Stats (Projection) ===
        # Здесь мы используем описания, чтобы посчитать игровые статы
        vec_text = f"{entity.name}. {entity.description} Type: {entity.category}"
        embedding = self.embedder.get_text_embedding(vec_text)
        game_stats = self.projector.project(embedding)

        # === 2. Special Logic per Type ===
        
        # Пример: Если это COMMODITY (Золото), форсируем fungibility=1.0
        if entity.subtype == AssetSubtype.COMMODITY:
            # TODO [cite: 33, 34] Force fungibility for commodities
            # game_stats['mat_fungibility'] = 1.0 (если проектор поддерживает перезапись)
            pass

        # === 3. Upsert to DB ===
        # Qdrant
        payload = {
            "name": entity.name,
            "type": entity.category.value,
            "subtype": entity.subtype.value if entity.subtype else None,
            "description": entity.description,
            "source": source_doc,
            "stats": game_stats
        }
        
        self.qdrant.upsert(
            "molecules",
            [PointStruct(id=mol_uuid, vector=embedding, payload=payload)]
        )
        
        # Neo4j
        # Здесь сохраняем базовый узел. Связи добавятся на Micro-Pass или Event-Pass.
        self.neo4j.upsert_molecule(
            mol_uuid, 
            entity.name, 
            entity.category.value,
            semantic_stats=game_stats
        )

        if hasattr(self, 'synthesizer'):
            self.synthesizer.collect(
                uid=mol_uuid,
                observation=f"[MACRO-CONTEXT]: {entity.description}", # Помечаем, что это макро
                metadata={
                    "name": entity.name,
                    "category": entity.category.value,
                    "subtype": entity.subtype.value if entity.subtype else None,
                    "source_doc": source_doc
                }
            )

    def _resolve_or_create_location_stub(self, name: str, summary: str, source_doc: str) -> str:
        """
        Ищет существующую локацию по всей базе. Если не находит — создает новую.
        """
        # --- ЭТАП 1: FUZZY SEARCH (Neo4j) ---
        # Ищем опечатки или вариации имен ("Dark Forest" vs "The Dark Forest")
        fuzzy_id = self.neo4j.fuzzy_search_location(name, threshold=0.9) #
        if fuzzy_id:
            return fuzzy_id

        # --- ЭТАП 2: SEMANTIC SEARCH (Qdrant) ---
        # Ищем по смыслу описания. Полезно, если имя другое, но суть та же.
        # Векторизуем "Имя + Описание"
        vec_text = f"{name}. {summary}"
        query_vector = self.embedder.get_text_embedding(vec_text)
        
        # Проверяем, есть ли коллекция (на всякий случай)
        if self.qdrant.collection_exists("skeleton_locations"):
            result = self.qdrant.query_points(
                collection_name="skeleton_locations",
                query=query_vector,
                limit=1
            )
            hits = result.points
            
            # Если нашли очень похожее (Score > 0.93 - высокий порог для безопасности)
            if hits and hits[0].score > 0.93:
                existing_name = hits[0].payload.get("name", "Unknown")
                print(f"      🧠 Qdrant Semantic Match: '{name}' ≈ '{existing_name}' (Score: {hits[0].score:.2f})")
                return hits[0].id

        # --- ЭТАП 3: СОЗДАНИЕ НОВОЙ ---
        # Если совпадений нет, создаем новую "Stub" локацию
        new_id = str(uuid.uuid4())
        
        # A. Пишем в Neo4j (чтобы fuzzy search находил её для следующих чанков)
        self.neo4j.upsert_location(
            loc_id=new_id, 
            name=name, 
            summary=summary, 
            source_doc=source_doc,
            semantic_stats=None # Статы посчитаем позже или тут же, если хотим
        ) #
        
        # B. Пишем в Qdrant (чтобы semantic search находил её для следующих чанков)
        # Нам нужны хоть какие-то статы для payload, сделаем проекцию сейчас
        loc_stats = self.projector.project(query_vector)
        
        self.qdrant.upsert(
            "skeleton_locations",
            [PointStruct(
                id=new_id,
                vector=query_vector,
                payload={
                    "name": name, 
                    "summary": summary,
                    "source": source_doc,
                    "stats": loc_stats
                }
            )]
        )
        
        print(f"      ✨ Created New Location: '{name}'")
        return new_id

    def _process_locations(
            self, locations: List[GraphLocation], 
            connections: List[LocationConnection], 
            source_doc: str) -> Dict[str, str]:
        slug_to_uuid = {}
        
        # --- NODES (ЛОКАЦИИ) ---
        for loc in locations:
            # 1. Резолвинг ID
            real_uuid = self._resolve_or_create_location_id(loc.name, loc.summary)
            slug_to_uuid[loc.suggested_id] = real_uuid
            
            # Подготовка вектора
            vec_text = f"{loc.name}. {loc.summary}"
            embedding = self.embedder.get_text_embedding(vec_text)
            
            # 2. === PROJECTION: TOPOLOGY & STATS ===
            template_id = None
            loc_stats = None
            
            if self.options.project_topology:
                # Классификация через реестр
                query_text = f"{loc.type}. {loc.summary}"
                found_templates = TOPOLOGIES.classify(query_text, threshold=0.6, top_k=1)
                
                if found_templates:
                    template_obj = found_templates[0][0] # Сам объект TopologyTemplate
                    template_id = template_obj.id
                    
                    # === ЛОГИКА ВОССТАНОВЛЕНА ===
                    # Если нашли шаблон, берем его "Идеальный Вектор" (query_vector)
                    # Это гарантирует, что "Тюрьма" всегда будет ощущаться как "Тюрьма"
                    loc_stats = template_obj.query_vector.model_dump()
                    
                    print(f"   🗺️ Mapped Location '{loc.name}' -> Template '{template_id}' (Using Static Stats)")
            
            # Если шаблон не найден (или отключена проекция), вычисляем "Вайб" из текста
            if not loc_stats:
                # SemanticProjector возвращает словарь координат
                loc_stats = self.projector.project(embedding)
                print(f"   🎨 Calculated Dynamic Stats for '{loc.name}'")

            # 3. Сохранение проекции (DB)
            if template_id:
                self.neo4j.upsert_location_projection(real_uuid, template_id)

            # 4. Сохранение в Neo4j (передаем stats)
            self.neo4j.upsert_location(
                real_uuid, 
                loc.name, 
                loc.summary, 
                source_doc, 
                template_id=template_id,
                semantic_stats=loc_stats # <--- Важно
            )
            
            # 5. Индексация в Qdrant
            self.qdrant.upsert(
                "skeleton_locations",
                [PointStruct(
                    id=real_uuid,
                    vector=embedding,
                    payload={
                        "name": loc.name, 
                        "slug": loc.suggested_id, 
                        "source": source_doc,
                        "template_id": template_id,
                        "stats": loc_stats # <--- Важно
                    }
                )]
            )
            
        # --- EDGES (СВЯЗИ) ---
        for conn in connections:
            from_id = slug_to_uuid.get(conn.from_slug)
            to_id = slug_to_uuid.get(conn.to_slug)
            if from_id and to_id:
                # TODO: классификация рёбер (но мб уже есть)
                self.neo4j.link_locations(from_id, to_id, conn.type)
                
        return slug_to_uuid
    
    def _process_chronology_stream(
            self, events: List[GraphEvent], 
            causal_links: List[CausalLink], 
            slug_map: Dict[str, str], 
            start_tick: int, 
            prev_chunk_last_event_id: str, 
            source_doc: str
        ):
        # Сортируем локально
        sorted_events = sorted(events, key=lambda x: x.order_index)
        local_index_map = {} 
        current_timeline_cursor = prev_chunk_last_event_id
        
        for i, evt in enumerate(sorted_events):
            
            # --- ЛОГИКА 1: ПРОДОЛЖЕНИЕ ---
            if evt.is_continuation and current_timeline_cursor:
                print(f"   📎 Merging continuation into {current_timeline_cursor}...")
                self.neo4j.driver.execute_query(
                    """
                    MATCH (e:Event {id: $eid})
                    SET e.description = e.description + '\n\n[Continuation]: ' + $new_desc
                    """,
                    eid=current_timeline_cursor, 
                    new_desc=evt.description
                )
                # Мы обновляем payload текущего события в Qdrant? 
                # Пока пропустим, считая первое описание ключевым.
                local_index_map[evt.order_index] = current_timeline_cursor
                continue 

            # --- ЛОГИКА 2: ВОСПОМИНАНИЕ ---
            if evt.is_recollection:
                historic_id = self._find_historic_event(evt.name)
                if historic_id:
                    print(f"   🧠 Linking Flashback: Current -> {historic_id}")
                    if current_timeline_cursor:
                         self.neo4j.driver.execute_query(
                            """
                            MATCH (curr:Event {id: $cid}), (old:Event {id: $oid}) 
                            MERGE (curr)-[:RECALLS]->(old)
                            """,
                            cid=current_timeline_cursor, oid=historic_id
                        )
                    continue 
                else:
                    # Создаем "Detached Memory"
                    print(f"   ✨ Creating new Memory Node (detached): {evt.name}")
                    memory_uuid = str(uuid.uuid4())
                    
                    self.neo4j.upsert_event(memory_uuid, evt.name, -1)
                    if current_timeline_cursor:
                        self.neo4j.driver.execute_query(
                            "MATCH (curr:Event {id: $cid}), (mem:Event {id: $mid}) MERGE (curr)-[:RECALLS]->(mem)",
                            cid=current_timeline_cursor, mid=memory_uuid
                        )
                    
                    vec_text = f"{evt.name}. {evt.description}"
                    embedding = self.embedder.get_text_embedding(vec_text)
                    evt_stats = self.projector.project(embedding)
                    
                    self._index_event_vector(
                        memory_uuid, evt.name, evt.description, -1, 
                        embedding, evt_stats, source_doc=source_doc # <--- Source
                    )
                    continue

            # --- STANDARD FLOW ---
            evt_uuid = str(uuid.uuid4())
            local_index_map[evt.order_index] = evt_uuid
            absolute_tick = start_tick + i + 1
            
           # === PROJECTION: EVENTS ===
            archetype_id = None
            evt_stats = None # Инициализируем None
            
            vec_text = f"{evt.name}. {evt.description}"
            embedding = self.embedder.get_text_embedding(vec_text)

            if self.options.project_events:
                # Ищем архетип события ("Ambush", "Negotiation")
                found = EVENTS.classify(f"{evt.name}. {evt.description}", threshold=0.2, top_k=1)
                
                if found:
                    archetype_obj = found[0][0]
                    archetype_id = archetype_obj.id
                    
                    # === ЛОГИКА ВОССТАНОВЛЕНА ===
                    # Если событие распознано как "Битва", берем эталонный вектор Битвы.
                    # Это гарантирует, что система среагирует на это как на боевую сцену.
                    # Предполагаем, что поле вектора называется 'vector' или 'step_vector'
                    if hasattr(archetype_obj, 'vector'):
                        evt_stats = archetype_obj.vector.model_dump()
                    elif hasattr(archetype_obj, 'step_vector'): # На случай другой схемы
                        evt_stats = archetype_obj.step_vector.model_dump()
                        
                    print(f"   ⚔️  Event Projection: '{evt.name}' -> {archetype_id} (Using Static Stats)")

            # Если архетип не найден или у него нет вектора — считаем проекцию сами
            if not evt_stats:
                evt_stats = self.projector.project(embedding)

            # Сохраняем в Neo4j
            self.neo4j.upsert_event(
                evt_uuid, 
                evt.name, 
                absolute_tick, 
                archetype_id=archetype_id,
                semantic_stats=evt_stats # <--- Передаем
            )

            # Связь с Локацией
            if evt.location_slug and evt.location_slug in slug_map:
                self.neo4j.link_event_to_location(evt_uuid, slug_map[evt.location_slug])
            
            # Хронологическая связь
            if current_timeline_cursor:
                self.neo4j.driver.execute_query(
                    "MATCH (a:Event {id: $aid}), (b:Event {id: $bid}) MERGE (a)-[:NEXT]->(b)",
                    aid=current_timeline_cursor, bid=evt_uuid
                )
            
            # 6. Сохранение в Qdrant
            self._index_event_vector(
                evt_uuid, 
                evt.name, 
                evt.description, 
                absolute_tick, 
                embedding,  
                evt_stats,
                source_doc=source_doc, # <--- Source
                archetype_id=archetype_id
            )

            current_timeline_cursor = evt_uuid

        # --- CAUSALITY ---
        for link in causal_links:
            cause = local_index_map.get(link.cause_event_index)
            effect = local_index_map.get(link.effect_event_index)
            if cause and effect:
                self.neo4j.link_causality(cause, effect, link.reason)
                
        return current_timeline_cursor

    # def _classify_event(self, evt) -> Optional[str]:
    #     """Хелпер для классификации события через реестр."""
    #     query = f"{evt.name}. {evt.description}"
    #     found = EVENTS.classify(query, threshold=0.2, top_k=1)
    #     if found:
    #         print(f"   ⚔️  Event Projection: '{evt.name}' -> {found[0][0].id}")
    #         return found[0][0].id
    #     return None

    def _index_event_vector(
            self, uuid_str: str, 
            name: str, 
            description: str, 
            tick: int, 
            embedding: Embedding, 
            stats: Dict[str, float], 
            source_doc: str, 
            archetype_id: Optional[str] = None
        ):
        """Хелпер для записи в Qdrant (Chronicle)."""
        payload = {
            "name": name, 
            "tick": tick, 
            "source": source_doc, # <--- Added
            "description": description,
            "archetype_id": archetype_id,
            "stats": stats
        }
        
        self.qdrant.upsert(
            "chronicle",
            [PointStruct(
                id=uuid_str,
                vector=embedding,
                payload=payload
            )]
        )
    