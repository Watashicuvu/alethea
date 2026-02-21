import uuid
import logging
import numpy as np
from typing import Dict, List, Optional, Tuple
from llama_index.core import SimpleDirectoryReader, Document
from llama_index.core.text_splitter import SentenceSplitter
from llama_index.llms.openai_like import OpenAILike
from llama_index.core import PromptTemplate
#from llama_index.core.program import LLMTextCompletionProgram
from llama_index.embeddings.openai_like import OpenAILikeEmbedding
from llama_index.core.schema import MetadataMode
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
from src.infrastructure.llama_adapter import SmartLlamaLLM
from src.infrastructure.smart_client import SmartOpenAI
from transformers import AutoTokenizer
from qdrant_client import models

from src.config import PipelineOptions, config
from src.ingestion.scene_splitter import AdaptiveMicroSplitter
from src.ingestion.mappers import RelationshipSanitizer
from src.ingestion.game_math import GameMath
from src.ingestion.synthesizer import EntitySynthesizer
from src.ingestion.classifier import HybridClassifier
from src.custom_program import LocalStructuredProgram as LLMTextCompletionProgram
from src.ingestion.graph_schemas import MoleculeType
from src.ingestion.semantic_projector import SemanticProjector
from src.ingestion.graph_builder import GraphBuilder
from src.ingestion.resolver import EntityResolver
from src.ingestion.schemas import ExtractedRelationship, ExtractionBatch
from src.registries.all_registries import (ATOMS, EVENTS, TOPOLOGIES, VERBS, ROLES, ARCS)

class IngestionEngine:
    """
    Основной пайплайн ETL для реализации data-as-code движка

    """
    def __init__(self, options: PipelineOptions = PipelineOptions()):
        self.options = options
        
        # 1. AI Models
        # self.llm = OpenAILike(
        #     model=config.llm.model_name,
        #     api_key=config.llm.api_key,
        #     api_base=config.llm.base_url,
        #     temperature=0.1
        # )
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
        self.synthesizer = EntitySynthesizer(self.llm)
        self.projector = SemanticProjector(self.embedder)
        
        # 2. Infrastructure
        self.qdrant = QdrantClient(url=config.qdrant.url)
        self._init_qdrant_collections()
        
        # Инициализируем компоненты
        # GraphBuilder теперь сам внутри себя имеет Neo4jConnector и логику Loop
        self.graph_builder = GraphBuilder(synthesizer=self.synthesizer) 
        #self.resolver = EntityResolver(self.qdrant, self.embedder, self.llm)

        # 4. Tokenizer & Splitter (инициализируем внутри, чтобы избежать проблем с import)
        # Укажи "gpt-4" или путь к локальной модели
        self.tokenizer = AutoTokenizer.from_pretrained("google/gemma-3-1b-it").encode 
        
        # 5. Micro-Pass Program
        prompt_templ = PromptTemplate(
            "Analyze the text chunk as a Game Engine Parser.\n"
            "Extract distinct entities and system interactions based on the following Ontology:\n\n"
            
            "1. MOLECULES (Entities):\n"
            "- AGENT: Beings with Will (Characters, Monsters).\n"
            "- GROUP: Factions or Squads.\n"
            "- ASSET: Objects. Distinguish between 'ARTIFACT' (Unique/Named) and 'COMMODITY' (Gold, Food, Ammo).\n"
            "- CONSTRUCT: Spells, Skills, or Phenomena (e.g. 'Fireball', 'Curse'). NOT verbs.\n"
            "- LORE: Information, secrets, codes.\n\n"
            "   - **CRITICAL RULE**: The 'Description' MUST be a DIEGETIC FACT derived from THIS text chunk.\n"
            "     - GOOD: 'Holding a golden key', 'Falling slowly', 'Argues with the Queen'.\n"
            "     - BAD: 'Main character', 'A being with will', 'Entity in the story'.\n"
            "   - If an entity is present but does nothing significant, SKIP IT.\n\n"
            
            "2. INTERACTIONS (Verbs & Actions):\n"
            "- EXTRACT significant actions.\n"
            "- IF it involves skill checks/combat/resources -> Label as MECHANIC.\n"
            "- IF it is purely narrative (movement, atmosphere, emotion) -> Label as FLAVOR.\n"
            "- Example Mechanic: 'Attack', 'Cast Spell', 'Pick Lock'.\n"
            "- Example Flavor: 'The beast's eyes flamed', 'Alice stood in thought'.\n\n"
            
            "3. RELATIONSHIPS:\n"
            "- Connect entities logically (e.g. 'Alice' POSSESSES 'Key').\n\n"
            "- **RELATIONSHIP TYPES (Strict Taxonomy)**:\n"
            "   -- PHYSICAL: 'LOCATED_AT' (entity is inside place), 'POSSESSES' (holding item).\n"
            "   -- SOCIAL: 'KNOWS', 'LOVES', 'HATES', 'SERVES', 'COMMANDS'.\n"
            "   -- MENTAL: 'RECALLS' (memories), 'THINKS_OF' (thoughts), 'IMAGINES'.\n"
            "   -- LOGICAL: 'PART_OF' (finger part of hand), 'CAUSED' (event caused event).\n"
            
            "- RULES:\n"
            "   -- If someone THINKS about a place, use MENTAL type (NOT 'LOCATED_AT').\n"
            "   -- If 'Alice is in the King's presence', use SOCIAL ('NEAR' or 'SERVES'), NOT PHYSICAL 'LOCATED_AT'.\n\n"
            
            "TEXT CHUNK:\n{text_chunk}\n\n"
        )
        self.extractor_program = LLMTextCompletionProgram(
            output_cls=ExtractionBatch,
            llm=self.llm,
            prompt=prompt_templ, 
            verbose=True,
            api_key=config.llm.api_key,
            base_url=config.llm.base_url
        )

        # 4. === RUNTIME CACHE ===
        # Кэш для глаголов: "VerbName|System" -> "PrimitiveID"
        # Позволяет не гонять классификатор на каждое слово "Attack"
        self._verb_cache: Dict[str, Optional[str]] = {}

    def reset_context(self):
        """
        Сбрасывает накопленное состояние (Synthesizer, Cache) перед обработкой нового источника.
        """
        print("🧹 Resetting Engine Context for new source...")
        
        # 1. Пересоздаем компоненты, которые хранят состояние в памяти
        # (EntitySynthesizer накапливает _dossiers, GraphBuilder накапливает связи)
        self.synthesizer = EntitySynthesizer(self.llm)
        self.graph_builder = GraphBuilder(synthesizer=self.synthesizer)
        
        # 2. Очищаем кэши
        self._verb_cache = {}
        
        # 3. (Опционально) Можно пересоздать Resolver, если он кэширует что-то
        #self.resolver = EntityResolver(self.qdrant, self.embedder, self.llm)

    def _init_qdrant_collections(self):
        v_size = config.v_size 
        
        # 1. STATIC ONTOLOGY (Реестры)
        # Все чертежи (Роли, Глаголы, Топологии, Архетипы) живут здесь.
        if not self.qdrant.collection_exists("ontology_static"):
            self.qdrant.create_collection(
                collection_name="ontology_static",
                vectors_config=VectorParams(size=v_size, distance=Distance.COSINE),
                shard_number=1  # Оптимизация памяти
            )
        
        # 2. DYNAMIC WORLD STATE (Инстансы)
        # Сюда пишет _index_batch. Эти коллекции растут по мере игры/чтения.
        # molecules - конкретные NPC и предметы
        # verbs - конкретные действия в сцене (не определения!)
        # vibes - атмосфера конкретных кусков текста
        dynamic_collections = [
            "molecules", "verbs", "vibes", 
            "chronicle", "narrative_instances",
            "skeleton_locations"
        ]
        
        for name in dynamic_collections:
            if not self.qdrant.collection_exists(name):
                self.qdrant.create_collection(
                    collection_name=name,
                    vectors_config=VectorParams(size=v_size, distance=Distance.COSINE),
                    shard_number=1
                )

    def _index_roles(self, source_id: str):
        print("   🎭 Indexing Roles...")
        points = []
        for role in ROLES.all():
            # Мягкий поиск по описанию
            txt_vec = self._get_embedding(f"{role.id}. {role.description}")
            # Жесткие статы для логики
            stats = role.query_vector.model_dump()

            points.append(PointStruct(
                id=role.id, 
                vector=txt_vec,
                payload={
                    "doc_type": "role",     # <--- Фильтр типа
                    "source": source_id,    # <--- Источник
                    "description": role.description,
                    "required_tags": role.required_tags,
                    "stats": stats 
                }
            ))
        if points:
            self.qdrant.upsert("ontology_static", points)

    def _index_verbs(self, source_id: str):
        print("   ⚔️ Indexing Verbs...")
        points = []
        for verb in VERBS.all():
            txt_vec = self._get_embedding(f"{verb.name} {verb.description}")
            stats = verb.vector.model_dump()
            
            points.append(PointStruct(
                id=verb.id,
                vector=txt_vec,
                payload={
                    "doc_type": "verb",
                    "source": source_id,
                    "name": verb.name,
                    "sphere": verb.sphere,
                    "stats": stats
                }
            ))
        if points:
            self.qdrant.upsert("ontology_static", points)

    def _index_topologies(self, source_id: str):
        print("   🗺️ Indexing Topologies...")
        points = []
        for topo in TOPOLOGIES.all():
            txt_vec = self._get_embedding(f"{topo.name}. {topo.description}")
            stats = topo.query_vector.model_dump() # Внимание: в модели поле query_vector
            
            points.append(PointStruct(
                id=topo.id,
                vector=txt_vec,
                payload={
                    "doc_type": "topology",
                    "source": source_id,
                    "name": topo.name,
                    "layout_type": topo.layout_type,
                    "stats": stats
                }
            ))
        if points:
            self.qdrant.upsert("ontology_static", points)

    def _index_event_archetypes(self, source_id: str):
        print("   🎬 Indexing Event Archetypes...")
        points = []
        for evt in EVENTS.all(): 
            txt_vec = self._get_embedding(f"{evt.name}. {evt.description}")
            # Предполагаем наличие vector в модели, если нет - используем заглушку или SemanticVector()
            stats = getattr(evt, 'vector', None)
            stats_dump = stats.model_dump() if stats else {}
            
            points.append(PointStruct(
                id=evt.id,
                vector=txt_vec,
                payload={
                    "doc_type": "event_archetype",
                    "source": source_id,
                    "name": evt.name,
                    "consequences": evt.primary_consequence_tags,
                    "stats": stats_dump
                }
            ))
        if points:
            self.qdrant.upsert("ontology_static", points)

    def _index_arc_templates(self, source_id: str):
        print("   📚 Indexing Narrative Arc Templates...")
        points = []
        for template in ARCS.all():
            embedding = self._get_embedding(template.description)
            stats_dict = template.global_vector.model_dump() 
            
            points.append(PointStruct(
                id=template.id,
                vector=embedding,
                payload={
                    "doc_type": "arc_template",
                    "source": source_id,
                    "name": template.name,
                    "description": template.description,
                    "stats": stats_dict
                }
            ))
            
        if points:
            self.qdrant.upsert("ontology_static", points)

    def _get_embedding(self, text: str) -> List[float]:
        return self.embedder.get_text_embedding(text)
    
    def index_registries(self, source_id: str = "core"):
        """
        Публичный метод для обновления всех статических индексов.
        Args:
            source_id: метка источника (например: "core", "dlc_vampires", "mod_user123")
        """
        print(f"📚 Starting Registry Indexing (Source: {source_id})...")
        self._index_arc_templates(source_id)
        self._index_roles(source_id)
        self._index_verbs(source_id)
        self._index_topologies(source_id)
        self._index_event_archetypes(source_id)
        print("✅ Registry Indexing Complete.")

    def process_directory(self, input_dir: str, source_id: str):
        """
        Args:
            input_dir: путь к папке с текстом
            source_id: уникальный ID мира/книги (например: 'alice_wonderland', 'dune_1')
                       Этот ID будет записан в payload каждого вектора.
        """
        reader = SimpleDirectoryReader(input_dir)
        documents = reader.load_data()
        
        print(f"🚀 Processing Source '{source_id}' ({len(documents)} docs)...")

        for doc in documents:
            source_ref = doc.doc_id 
            print(f"\n📄 Processing Document: {source_ref}")

            # PHASE 1
            scene_ranges, entity_registry = self.graph_builder.build_world_skeleton(doc.text, source_ref)
            
            # PHASE 2: Пробрасываем source_id внутрь
            self._process_micro_chunks(doc, source_ref, scene_ranges, entity_registry, source_id)

    def _process_micro_chunks(self, document: Document, source_ref: str, 
                              scene_ranges: List[tuple], 
                              entity_registry: Dict[str, str],
                              source_id: str
        ):
        
        print(f"   🔍 Micro-pass (Adaptive Semantic with Cursor)...")
        
        # 1. Инициализация Сплиттера
        micro_parser = AdaptiveMicroSplitter(
            embedder=self.embedder,
            tokenizer=self.tokenizer, 
            min_tokens=500,
            max_tokens=2000,
            base_threshold=0.35
        )
        
        # 2. Нарезка с сохранением координат
        nodes = micro_parser.get_nodes_from_documents([document])
        
        for i, node in enumerate(nodes):
            # Получаем текст чанка
            node_text = node.get_content(metadata_mode=MetadataMode.NONE)
            
            # === ГЛАВНОЕ ИЗМЕНЕНИЕ ===
            # Берем точные координаты из метаданных сплиттера
            start_idx = node.metadata.get("start_char_idx", 0)
            end_idx = node.metadata.get("end_char_idx", len(node_text))
            
            # Вычисляем центр чанка (абсолютное смещение в документе)
            chunk_center = start_idx + (end_idx - start_idx) // 2
            
            # 3. Поиск Макро-Контекста (Сцена, Локация)
            # Передаем точный центр чанка
            loc_id, context_data = self._find_location_for_offset(chunk_center, scene_ranges)
            
            # 4. Инъекция контекста (Context Injection)
            # Если сцена ментальная, предупреждаем экстрактор
            context_prefix = ""
            if context_data:
                label = context_data.get('label', 'Unknown Context')
                sc_type = context_data.get('type', 'PHYSICAL')
                
                if sc_type != "PHYSICAL":
                    context_prefix = (
                        f"[SCENE TYPE: {sc_type} | CONTEXT: {label}]\n"
                        "NOTE: Entities here are likely MEMORIES or THOUGHTS. "
                        "Mark relationships as 'MENTAL' or 'REFERENCE' where appropriate.\n\n"
                    )
                else:
                    # Даже для физических сцен полезно знать заголовок ("Alice falls down")
                    context_prefix = f"[SCENE: {label}]\n"
            
            final_chunk_text = context_prefix + node_text
            
            # 5. Вызов Экстрактора
            # Передаем current_tick как порядковый номер чанка (или можно рассчитать из токенов)
            current_tick = i 
            
            try:
                data: ExtractionBatch = self.extractor_program(text_chunk=final_chunk_text)
                
                # Индексация (передаем точные координаты и найденный loc_id)
                self._index_batch(data, source_ref, loc_id, entity_registry, source_id, current_tick=current_tick)
                
            except Exception as e:
                logging.error(f"Error extracting from micro-chunk {i}: {e}")
    
    def _find_location_for_offset(self, offset: int, ranges: List[tuple]) -> Tuple[Optional[str], Optional[dict]]:
        """
        Ищет, в какой сцене находится точка offset.
        ranges = [(0, 5000, 'uuid1'), (5000, 10000, 'uuid2')...]
        """
        for start, end, loc_uuid, context_data in ranges: # <--- 4 args
            if start <= offset < end:
                return loc_uuid, context_data # <--- Возвращаем и контекст!
        return None, None

    def _index_batch(self, batch: ExtractionBatch, source_ref: str, 
                     loc_id: str, entity_registry: Dict[str, str], 
                     source_id: str,
                     current_tick: int = -1):
        
        points = {"molecules": [], "verbs": [], "vibes": []}

        # 1. MOLECULES (Accumulation Phase)
        for m in batch.molecules:
            clean_name = m.name.lower().strip()
            
            # А. [cite_start]ID RESOLUTION (Deterministic) [cite: 1]
            if clean_name in entity_registry:
                mol_id = entity_registry[clean_name]
                is_canonical = True
            else:
                # Если это локальный предмет, генерируем ID от имени
                mol_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, clean_name))
                is_canonical = False

            # Б. COLLECT OBSERVATION (Вместо финального расчета)
            # Мы просто складываем описание в папку.
            self.synthesizer.collect(
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

            # В. CREATE STUB NODE (Заглушка в Neo4j)
            # Нам нужен узел прямо сейчас, чтобы привязать к нему связи (Links).
            # Статы пока по нулям. Мы обновим их в пост-процессинге.
            self.graph_builder.neo4j.upsert_molecule(
                mol_id, m.name, m.category, 
                semantic_stats=None # Пока пусто
            )
            
            if loc_id:
                self.graph_builder.neo4j.link_molecule_to_location(mol_id, loc_id)

            # Мы НЕ пишем в Qdrant здесь молекулу целиком, потому что вектор будет "мусорным".
            # Но если нужно для поиска в process_relationships, можно записать черновик.
            # Давайте запишем черновик, чтобы Resolver работал.
            embedding = self._get_embedding(f"{m.name} {m.description}")
            points["molecules"].append(PointStruct(
                id=mol_id, vector=embedding, payload={
                    "name": m.name, "type": "molecule", "is_draft": True,
                    "source_id": source_id
                }
            ))

        # =========================================================================
        # 2. VERBS (System Mechanics)
        # =========================================================================
        for v in batch.verbs:
            # 1. СТОП-СЛОВА (Мусорный фильтр)
            # Если действие слишком абстрактное, сразу отправляем в Flavor, минуя классификатор.
            GARBAGE_VERBS = ["did", "do", "does", "be", "is", "was", "went", "go", "said", "look", "saw"]
            clean_name = v.name.lower().strip()
            
            is_garbage = clean_name in GARBAGE_VERBS
            # Если описание "did so carefully" — это мусор для механики.
            if len(clean_name) < 3 or is_garbage:
                if loc_id:
                     # Просто сохраняем в досье сцены как текст
                     self.synthesizer.collect_scene_beat(loc_id, f"{v.name}: {v.context_usage}", tick=current_tick)
                continue

            # 2. CACHE & CLASSIFY
            cache_key = f"{v.name.lower()}|{v.implied_system}"
            primitive_id = None
            
            if cache_key in self._verb_cache:
                primitive_id = self._verb_cache[cache_key]
            else:
                # [cite_start]Если LLM сама пометила это как FLAVOR, даже не пытаемся искать механику [cite: 5]
                if v.implied_system == "FLAVOR" or "narrative" in v.implied_system.lower():
                    primitive_id = None
                else:
                    # Строгий классификатор
                    query_text = f"{v.name}. {v.context_usage}. System: {v.implied_system}"
                    if self.options.project_verbs:
                        primitive_id = self.classifier.classify(
                            query_text=query_text,
                            registry=VERBS,
                            threshold_high=0.88, # Очень строгий порог для прямого матча
                            threshold_low=0.65,  # Подняли нижний порог (было 0.55/0.60)
                            top_k=3
                        )
                self._verb_cache[cache_key] = primitive_id

            # 3. BRANCHING (Mechanic vs Flavor)
            if primitive_id:
                # === MECHANIC ===
                # Это реальная игровая механика (Attack, Cast)
                
                # Считаем "Умные Статы" через GameMath
                emb = self._get_embedding(f"{v.name} {v.force_desc}")
                raw_stats = self.projector.project(emb)
                # [cite_start]Применяем маску системы (Combat/Magic) [cite: 3]
                final_stats = GameMath.calculate_action_stats(raw_stats, v.implied_system)

                # Upsert Verb Point
                verb_id = str(uuid.uuid4())
                points["verbs"].append(PointStruct(
                    id=verb_id, vector=emb, payload={
                        "name": v.name,
                        "system": v.implied_system,
                        "primitive_id": primitive_id,
                        "stats": final_stats, # Уже не 0.5!
                        "location_id": loc_id,
                        "source_id": source_id
                    }
                ))
                
                # Добавляем в сцену с пометкой [Mechanic]
                if loc_id:
                    self.synthesizer.collect_scene_beat(loc_id, f"[Mechanic] {v.name}", tick=current_tick)

            else:
                # === FLAVOR ===
                # "Alice danced", "Knave did so carefully"
                # Мы НЕ сохраняем это в коллекцию 'verbs' в Qdrant (чтобы не мусорить поиск механик).
                # Мы сохраняем это ТОЛЬКО в досье сцены для суммаризации.
                
                if loc_id:
                    self.synthesizer.collect_scene_beat(loc_id, f"{v.name}: {v.context_usage}", tick=current_tick)

        # =========================================================================
        # 3. VIBES (Atmosphere)
        # =========================================================================
        batch_vibe_stats = {"material": [], "vitality": [], "social": [], "cognitive": []}

        for vb in batch.vibes:
            # Фильтр совсем мусора
            if len(vb.snippet) < 5: continue

            vibe_id = str(uuid.uuid4())
            emb = self._get_embedding(vb.snippet)
            raw_stats = self.projector.project(emb)
            
            # === ПРИМЕНЯЕМ GAME MATH ===
            # Это раздвинет значения 0.5 -> 0.1/0.9 в зависимости от тегов
            final_stats = GameMath.calculate_vibe_stats(raw_stats, vb.tags)
            
            # Собираем для агрегации локации
            for k, v in final_stats.items():
                if k in batch_vibe_stats:
                    batch_vibe_stats[k].append(v)
            
            # Сохраняем (только если нужно для цитирования)
            # Если вайб помечен как FLAVOR/LORE, он полезен для RAG, но не для механики.
            points["vibes"].append(PointStruct(
                id=vibe_id, vector=emb, payload={
                    "snippet": vb.snippet,
                    "tags": vb.tags,
                    "stats": final_stats, # Исправленные статы
                    "location_id": loc_id,
                    "source_id": source_id
                }
            ))

        # --- AGGREGATION ---
        if loc_id and any(batch_vibe_stats.values()):
            avg_stats = {}
            for axis, values in batch_vibe_stats.items():
                if values:
                    # Среднее по уже "смещенным" значениям даст сильный вектор
                    avg_stats[axis] = sum(values) / len(values)
                else:
                    avg_stats[axis] = 0.0
            
            # Обновляем атмосферу в графе
            self.graph_builder.neo4j.update_location_atmosphere(loc_id, avg_stats, weight=0.3)
            
            print(f"   🎨 Painted Atmosphere for Location {loc_id}: {avg_stats}")

        # =========================================================================
        # 4. FINAL UPSERT & RELATIONS
        # =========================================================================
        
        # Upsert всех точек
        for col_name, pts in points.items():
            if pts:
                self.qdrant.upsert(collection_name=col_name, points=pts)
        
        # --- RELATIONSHIPS PROCESSING ---

        mol_points = points["molecules"]
        if mol_points:
            # Создаем маппинг "Имя из текста" -> "Сгенерированный UUID" для текущего батча
            local_name_map = {m.name: mol_points[i].id for i, m in enumerate(batch.molecules)}
            
            # Объединяем с глобальным реестром
            full_name_map = {**entity_registry, **local_name_map}
            
            # Обрабатываем связи
            self._process_relationships(batch.relationships, full_name_map, loc_id)


    def run_post_processing(self, source_id: str):
        print("\n⚙️ Starting Post-Processing...")

        # Определяем маски (BIAS)
        # Значения > 1.0 усиливают сигнал, < 1.0 подавляют шум.
        TYPE_BIAS = {
            "AGENT":     {"mat": 0.5, "vit": 1.2, "soc": 1.2, "cog": 1.2},
            "GROUP":     {"mat": 0.2, "vit": 0.8, "soc": 2.0, "cog": 1.0},
            "ASSET":     {"mat": 1.5, "vit": 0.5, "soc": 0.1, "cog": 0.3},
            "LOCATION":  {"mat": 1.2, "vit": 1.0, "soc": 0.5, "cog": 0.5},
            "CONSTRUCT": {"mat": 0.1, "vit": 0.5, "soc": 0.8, "cog": 1.5},
            "LORE":      {"mat": 0.0, "vit": 0.0, "soc": 0.5, "cog": 2.0},
            # Fallback
            "UNKNOWN":   {"mat": 1.0, "vit": 1.0, "soc": 1.0, "cog": 1.0}
        }

        # 1. CONSOLIDATION (Склейка дублей)
        self.synthesizer.consolidate_dossiers()
        self.synthesizer.consolidate_locations()

        # ---------------------------------------------------------------------
        # STEP 2: LOCATION BLUEPRINT (Строим мир первым, чтобы сущностям было где жить)
        # ---------------------------------------------------------------------
        print("🏰 Synthesizing Location Blueprints & Physics...")
        
        loc_uids = list(self.synthesizer._location_dossiers.keys())
        
        # Маска для физики локаций (Локации стабильны и материальны)
        LOCATION_BIAS = {"mat": 1.2, "vit": 1.0, "soc": 0.5, "cog": 0.5}

        for loc_id in loc_uids:
            # 1. Пропускаем склеенные (дубли)
            if loc_id in self.synthesizer._redirect_map:
                continue

            # 2. СИНТЕЗ (Blueprint)
            # Генерируем описание геометрии, материалов и выходов
            loc_data = self.synthesizer.synthesize_location(loc_id)
            if not loc_data:
                continue

            # 3. ФИЗИКА (Physics Projection)
            # Векторизуем ТОЛЬКО структурную часть ("Stone walls, narrow corridor")
            # Мы специально игнорируем вайбы (страх, темноту), чтобы получить чистую физику.
            physics_text = f"{loc_data.canonical_name}. {' '.join(loc_data.geometry_tags)} {' '.join(loc_data.material_tags)}. {loc_data.summary}"
            
            embedding = self._get_embedding(physics_text)
            raw_stats = self.projector.project(embedding)
            
            # Применяем Bias
            final_physics = {
                k: v * LOCATION_BIAS.get(k[:3], 1.0) 
                for k, v in raw_stats.items()
            }

            # 4. UPSERT GRAPH (Обновляем Скелет)
            # Записываем статы в val_*, описание и теги
            self.graph_builder.neo4j.update_location_physics(
                loc_id, 
                name=loc_data.canonical_name,
                description=loc_data.summary,
                physics_stats=final_physics,
                geometry_tags=loc_data.geometry_tags
            )

            # 5. UPSERT QDRANT (Skeleton Collection)
            # Это нужно для RAG: "Где находится каменный зал?"
            self.qdrant.upsert("skeleton_locations", [PointStruct(
                id=loc_id,
                vector=embedding,
                payload={
                    "name": loc_data.canonical_name,
                    "description": loc_data.summary,
                    "exits": loc_data.detected_exits,
                    "physics": final_physics,
                    "type": "location",
                    "importance": loc_data.importance_score
                }
            )])

        print("✅ Locations processed.")

        # ---------------------------------------------------------------------
        # STEP 3: CLEANUP LOCATIONS
        # ---------------------------------------------------------------------
        print("🧹 Cleaning up merged locations...")
        for old_id, new_id in self.synthesizer._redirect_map.items():
            # Если это редирект локации (проверяем по dossiers)
            if old_id in self.synthesizer._location_dossiers:
                # В Neo4j надо бы перекинуть связи CONNECTED_TO, но это сложно без APOC.
                # Для упрощения: удаляем дубль. Основной узел остался.
                # (В идеале Pass 1 строит связи по именам, так что основной узел уже имеет связи)
                self.graph_builder.neo4j.delete_location(old_id)
                self.qdrant.delete("skeleton_locations", points_selector=[old_id])

        # ---------------------------------------------------------------------
        # STEP 4: ENTITY SYNTHESIS 
        # ---------------------------------------------------------------------
        print("🧪 Synthesizing Entities...")
        
        valid_uids = set()
        all_uids = list(self.synthesizer._dossiers.keys())
        
        for uid in all_uids:
            # А. СИНТЕЗ (LLM создает чистовой профиль)
            result = self.synthesizer.synthesize_profile(uid)
            if not result:
                continue
                
            profile, final_uid = result
            valid_uids.add(final_uid)
            
            # Получаем метаданные
            meta = self.synthesizer._metadata[final_uid]
            meta['name'] = profile.canonical_name 
            category = meta.get('category', 'UNKNOWN')
            
            # Получаем историю наблюдений (для сохранения в БД)
            raw_observations = self.synthesizer.get_raw_observations(final_uid)

            # -----------------------------------------------------------------
            # Б. PROJECTION (МАТЕМАТИКА СТАТОВ И АТОМОВ)
            # -----------------------------------------------------------------
            
            # 1. Базовый вектор по чистовому описанию
            # Добавляем inferred_atoms в текст для точности
            rich_text = f"{profile.canonical_name}. {profile.summary} Traits: {', '.join(profile.personality_traits)}."
            embedding = self._get_embedding(rich_text)
            
            # Базовая проекция (чистый текст)
            raw_stats = self.projector.project(embedding)
            
            # 2. Поиск Атомов и расчет влияния
            component_ids = []
            atom_influence = {"material": [], "vitality": [], "social": [], "cognitive": []}
            
            if self.options.project_atoms:
                # Формируем запрос: Категория + Текст + Предполагаемые атомы от LLM
                atom_query_text = f"{category}: {rich_text}"
                threshold = 0.65 if category == "LORE" else 0.55
                
                # Поиск по реестру
                found_atoms = ATOMS.classify(atom_query_text, threshold=threshold, top_k=6)
                
                if found_atoms:
                    for atom_obj, score in found_atoms:
                        component_ids.append(atom_obj.id)
                        
                        # Извлекаем вектор атома (из кэша/модели или проецируем)
                        if hasattr(atom_obj, 'vector') and atom_obj.vector:
                             # Если это Pydantic модель
                            if hasattr(atom_obj.vector, 'model_dump'):
                                atom_stats = atom_obj.vector.model_dump()
                            else:
                                atom_stats = atom_obj.vector # Если уже dict
                        else:
                            # Fallback: проекция описания атома
                            atom_vec_text = f"{atom_obj.name} {atom_obj.description}"
                            atom_stats = self.projector.project(self._get_embedding(atom_vec_text))

                        # Накапливаем влияние (взвешенное на score совпадения)
                        for axis, val in atom_stats.items():
                            if axis in atom_influence:
                                atom_influence[axis].append(val * score)

            # 3. Слияние (Blending) и Маски (Bias)
            ATOM_WEIGHT = 0.3
            final_stats = {}
            
            # Маска для текущего типа сущности
            bias = TYPE_BIAS.get(category, TYPE_BIAS["UNKNOWN"])

            for axis, base_val in raw_stats.items():
                # а) Смешиваем базу с атомами
                atoms_vals = atom_influence.get(axis, [])
                if atoms_vals:
                    atom_avg = sum(atoms_vals) / len(atoms_vals)
                    merged_val = (base_val * (1.0 - ATOM_WEIGHT)) + (atom_avg * ATOM_WEIGHT)
                else:
                    merged_val = base_val
                
                # б) Применяем BIAS
                # (axis[:3] берет "mat" из "material")
                short_key = axis[:3]
                final_stats[axis] = merged_val * bias.get(short_key, 1.0)
            
            # -----------------------------------------------------------------
            # В. РОЛИ (Для агентов)
            # -----------------------------------------------------------------
            role_id = None
            if category in ["AGENT", "GROUP"] and self.options.project_roles:
                role_id = self.classifier.classify(rich_text, ROLES, top_k=3)

            # -----------------------------------------------------------------
            # Г. СОХРАНЕНИЕ (FINAL UPSERT)
            # -----------------------------------------------------------------
            
            # Neo4j: обновляем заглушку полноценными данными
            self.graph_builder.neo4j.upsert_molecule(
                final_uid, 
                meta['name'], 
                category,
                role_id=role_id,
                component_ids=component_ids,
                semantic_stats=final_stats
            )
            
            # Qdrant: полный пейлоад
            payload = {
                **meta,
                "description": profile.summary,
                "visuals": profile.visual_traits,
                "psychology": profile.personality_traits,
                "role_desc": profile.narrative_role_desc,
                "importance": profile.importance_score,
                "raw_observations": raw_observations,
                "stats": final_stats, # <--- Финальные статы
                "component_ids": component_ids,
                "source_id": source_id,
                "is_draft": False
            }
            
            # upsert вызывает валидацию PointStruct, поэтому embedding обязателен
            self.qdrant.upsert("molecules", [PointStruct(
                id=final_uid, vector=embedding, payload=payload
            )])
            
        print("✅ Entity Synthesis & Projection Complete.")

        # 3. CLEANUP (Удаление мусора из Графа)
        print("🧹 Cleaning up temporary nodes...")
        # Удаляем дубликаты (merged)
        for old_id in self.synthesizer._redirect_map.keys():
            self.graph_builder.neo4j.delete_molecule(old_id)
            self.qdrant.delete(collection_name="molecules", points_selector=[old_id])
            
        # Удаляем отфильтрованный мусор (low importance)
        for uid in all_uids:
            if uid not in valid_uids and uid not in self.synthesizer._redirect_map:
                self.graph_builder.neo4j.delete_molecule(uid)
                self.qdrant.delete(collection_name="molecules", points_selector=[uid])

        # ---------------------------------------------------------------------
        # STEP 5: EPISODE SYNTHESIS (Летопись)
        # ---------------------------------------------------------------------
        print("📜 Synthesizing Chronicles...")
        for loc_id in self.synthesizer._scene_dossiers:
            
            # 1. СИНТЕЗ (LLM пишет хронику и выбирает Архетип)
            generated_episodes = self.synthesizer.synthesize_episodes_for_loc(loc_id)
            
            for ep_data in generated_episodes:
                # Фильтр шума
                if ep_data.significance_score < 3:
                    continue

                # 2. РАСЧЕТ ИГРОВОЙ МАТЕМАТИКИ (GameMath)
                
                # А. Базовая проекция текста
                # "The Battle of the Dark Hall..."
                full_text = f"{ep_data.title}. {ep_data.summary}"
                embedding = self._get_embedding(full_text)
                raw_vector_stats = self.projector.project(embedding)
                
                # Б. Поиск Атомов (Событийный состав)
                # Пожар = Atom(Fire). Битва на мосту = Atom(Stone), Atom(Void).
                # Это добавит нюансов в вектор.
                atom_influence = {"material": [], "vitality": [], "social": [], "cognitive": []}
                
                if self.options.project_atoms:
                    # Ищем атомы в описании события
                    atom_query = f"EVENT: {full_text}"
                    found_atoms = ATOMS.classify(atom_query, threshold=0.6, top_k=3)
                    
                    if found_atoms:
                        for atom_obj, score in found_atoms:
                            # Получаем вектор атома (из кэша или проекции)
                            if hasattr(atom_obj, 'vector') and atom_obj.vector:
                                if hasattr(atom_obj.vector, 'model_dump'):
                                    a_stats = atom_obj.vector.model_dump()
                                else:
                                    a_stats = atom_obj.vector
                            else:
                                # Fallback projection
                                a_stats = self.projector.project(
                                    self._get_embedding(f"{atom_obj.name} {atom_obj.description}")
                                )

                            # Взвешиваем влияние
                            for axis, val in a_stats.items():
                                if axis in atom_influence:
                                    atom_influence[axis].append(val * score)

                # В. FINAL MATH (Blending + Archetype Bias)
                # Передаем archetype (например, 'conflict_physical') в GameMath
                final_stats = GameMath.calculate_stats(
                    base_vector_stats=raw_vector_stats,
                    atom_influence=atom_influence,
                    category=ep_data.archetype, # <--- Ключевой момент! Применяем маску
                    is_event=True 
                )
                
                # Логирование для проверки (увидим, как вектора "разъезжаются" от 0.5)
                print(f"      📊 Event '{ep_data.title}' ({ep_data.archetype}): {final_stats}")

                # 3. LINKING TO NEO4J (Upsert)
                # Логика поиска существующего эпизода по времени (start_tick)
                tick_window = 10 
                find_query = """
                MATCH (e:Episode)-[:HAPPENED_AT]->(l:Location {id: $lid})
                WHERE abs(e.start_tick - $my_tick) < $window
                RETURN e.id AS id
                LIMIT 1
                """
                
                existing_ep_id = None
                with self.graph_builder.neo4j.driver.session() as session:
                    res = session.run(find_query, lid=loc_id, my_tick=ep_data.start_tick, window=tick_window).single()
                    if res: existing_ep_id = res["id"]

                target_id = existing_ep_id if existing_ep_id else str(uuid.uuid4())
                
                # Обновляем Neo4j
                # ВАЖНО: Мы сохраняем final_stats в Neo4j тоже, если схема позволяет (semantic_stats)
                if existing_ep_id:
                    self.graph_builder.neo4j.driver.execute_query(
                        """
                        MATCH (e:Episode {id: $eid}) 
                        SET e.summary = $sum, e.name = $tit, 
                            e.archetype = $arch, e.semantic_stats = $stats
                        """,
                        eid=target_id, sum=ep_data.summary, tit=ep_data.title, 
                        arch=ep_data.archetype, stats=final_stats
                    )
                else:
                    self.graph_builder.neo4j.upsert_episode(
                        uid=target_id,
                        name=ep_data.title,
                        summary=ep_data.summary,
                        start_tick=ep_data.start_tick,
                        location_id=loc_id
                    )
                    # Дописываем статы и тип отдельным запросом (если upsert_episode простенький)
                    self.graph_builder.neo4j.driver.execute_query(
                        "MATCH (e:Episode {id: $eid}) SET e.archetype = $arch, e.semantic_stats = $stats",
                        eid=target_id, arch=ep_data.archetype.value, stats=final_stats
                    )

                # 4. INDEXING QDRANT
                payload = {
                    "name": ep_data.title,
                    "description": ep_data.summary,
                    "type": "episode",
                    "archetype": ep_data.archetype, # Важно для фильтрации
                    "tags": ep_data.dominant_tags,
                    "participants": ep_data.key_participants,
                    "significance": ep_data.significance_score,
                    "source_loc_id": loc_id,
                    "source_id": source_id,
                    "stats": final_stats # <--- Математически точный вектор
                }
                
                self.qdrant.upsert("chronicle", [PointStruct(
                    id=target_id,
                    vector=embedding,
                    payload=payload
                )])

        print("✅ Chronicles synthesized and projected.")

        # 4. GLOBAL NORMALIZATION (Выравнивание)
        if self.options.project_atoms:
             self._normalize_global_stats()

        # 2. NARRATIVE ARC DETECTION
        if not self.options.detect_arcs:
            return

        print("🕵️‍♂️ Running Narrative Arc Detection (Hybrid)...")
        
        # А. Собираем контекст (последние 5-10 эпизодов)
        recent_episodes = self._fetch_recent_chronicle_events(limit=6)
        
        if not recent_episodes:
            print("   ⚠️ Not enough data for arc detection.")
            return

        # Б. Формируем "Историю" для анализа
        story_text = self._compose_safe_context(recent_episodes, max_tokens=2500)
        
        # В. Гибридная классификация
        # 1. Векторный поиск находит Top-K похожих шаблонов (ARCS).
        # 2. LLM получает список кандидатов (только Имя + Описание) и выбирает лучший.
        # Это экономит токены и дает точность выше, чем просто порог 0.65.
        
        detected_arc_id = self.classifier.classify(
            query_text=story_text,
            registry=ARCS,       # Реестр сюжетных арок
            threshold_high=0.65, # Если вектор уверен на 85% — верим сразу
            threshold_low=0.35,  # Если сомнения (0.35-0.85) — спрашиваем LLM
            top_k=3              # Рассматриваем топ-3 кандидата
        )

        if detected_arc_id:
            # Получаем имя шаблона из реестра для красивого лога
            arc_template = ARCS.get(detected_arc_id)
            arc_name = arc_template.name if arc_template else "Unknown Arc"
            
            print(f"   🎭 DETECTED NARRATIVE ARC: '{arc_name}' (ID: {detected_arc_id})")
            
            # Г. Сохраняем Инстанс Арки в Граф
            instance_id = str(uuid.uuid4())
            self.graph_builder.neo4j.upsert_narrative_instance(
                instance_id, 
                detected_arc_id, 
                f"{arc_name} (Auto-detected)"
            )

            # Д. Сохраняем в Qdrant
            arc_vec = self._get_embedding(story_text) # Вектор истории, по которой нашли арку
            
            self.qdrant.upsert("narrative_instances", [PointStruct(
                id=instance_id,
                vector=arc_vec,
                payload={
                    "name": f"{arc_name} Instance",
                    "template_id": detected_arc_id,
                    "description": "Auto-detected narrative arc based on recent events.",
                    "tick": recent_episodes[-1]['tick'] if recent_episodes else 0,
                    "involved_episodes": [ep['id'] for ep in recent_episodes]
                }
            )])
            print(f"      💾 Saved Arc Instance to Qdrant.")

            # Е. Линкуем Эпизоды к этой Арке
            count = 0
            for ep in recent_episodes:
                self.graph_builder.neo4j.link_event_to_arc(ep['id'], instance_id)
                count += 1
            
            print(f"      🔗 Linked {count} episodes to the arc.")
                
    def _normalize_global_stats(self):
        print("   ⚖️  Running Global Stat Normalization...")
        
        # 1. Выгружаем ВСЕ молекулы (через скроллинг или лимит)
        # Для одной книги 10k точек - это нормально для RAM.
        try:
            scroll_result = self.qdrant.scroll(
                collection_name="molecules",
                limit=10_000, 
                with_payload=True,
                with_vectors=True
            )
            points = scroll_result[0]
            if not points:
                return
        except Exception as e:
            logging.error(f"      ⚠️ Failed to fetch points for normalization: {e}", exc_info=True)
            return

        print(f"      📊 Analyzing {len(points)} entities...")

        # 2. Собираем значения по осям
        axes_data = {"material": [], "vitality": [], "social": [], "cognitive": []}
        
        for p in points:
            stats = p.payload.get("stats", {})
            for axis in axes_data:
                # Собираем все значения, если они есть
                val = stats.get(axis, 0.0)
                axes_data[axis].append(val)

        # 3. Вычисляем границы (Min/Max) для каждой оси
        bounds = {}
        for axis, values in axes_data.items():
            if not values: continue
            # Используем процентили (2% и 98%), чтобы игнорировать дикие выбросы
            v_min = np.percentile(values, 2)
            v_max = np.percentile(values, 98)
            bounds[axis] = (v_min, v_max)
            print(f"      Axis '{axis}': range [{v_min:.2f}, {v_max:.2f}]")

        # 4. Пересчитываем и обновляем
        updated_points = []
        
        for p in points:
            old_stats = p.payload.get("stats", {})
            new_stats = {}
            
            for axis, (v_min, v_max) in bounds.items():
                val = old_stats.get(axis, 0.0)
                
                if v_max - v_min < 0.01:
                    new_val = val # Избегаем деления на ноль, если все равны
                else:
                    # Min-Max Scaling
                    scaled = (val - v_min) / (v_max - v_min)
                    # Clip (0.05 - 0.95) для красоты
                    new_val = 0.05 + (scaled * 0.9)
                    new_val = float(np.clip(new_val, 0.0, 1.0))
                
                new_stats[axis] = round(new_val, 3)
            
            # Обновляем payload
            p.payload["stats"] = new_stats
            
            # Дублируем статы в Neo4j (это медленно, но нужно для синхронизации)
            # TODO: Если база большая, лучше делать batch update в Neo4j отдельно.
            # Для "Алисы" пойдет и так.
            self.graph_builder.neo4j.upsert_molecule(
                p.id, 
                p.payload["name"], 
                p.payload.get("type", 'undefined'), 
                semantic_stats=new_stats
            )
            
            # Подготовка для Qdrant batch update
            updated_points.append(PointStruct(
                id=p.id, 
                vector=p.vector, # Вектор не меняется, но Qdrant требует (или используйте set_payload)
                payload=p.payload
            ))

        # 5. Batch Update Qdrant
        # Метод set_payload эффективнее upsert, если вектора не меняются, 
        # но upsert проще в реализации.
        if updated_points:
             # Чтобы не гонять вектора туда-сюда, лучше использовать client.set_payload
             # Но для простоты:
             # self.qdrant.upsert("molecules", updated_points) 
             
             # ОПТИМИЗАЦИЯ: используем overwrite_payload
             for p in points:
                 self.qdrant.overwrite_payload(
                     collection_name="molecules",
                     payload=p.payload,
                     points=[p.id]
                 )
             print(f"      ✅ Normalized {len(points)} entities globally.")

    def _compose_safe_context(self, events: List[dict], max_tokens: int = 1500) -> str:
        """
        Собирает историю, группируя Beats в Сцены.
        Формат:
        [SCENE: The Rabbit Hole]
        - Alice falls down (Event)
        - She sees maps and jars (Event)
        ...
        """
        grouped_lines = []
        current_loc = None
        
        # Формируем текст от Старого к Новому
        for evt in events:
            loc_name = evt.get('loc_name', 'Unknown Place')
            
            # Если локация сменилась, добавляем заголовок сцены
            if loc_name != current_loc:
                grouped_lines.append(f"\n[SCENE: {loc_name}]")
                current_loc = loc_name
            
            # Формируем строку события
            # Если есть архетип, добавляем его как тег [ATTACK], [MOVE]
            tag = f"[{evt['archetype']}] " if evt.get('archetype') else ""
            line = f"- {tag}{evt['name']}: {evt['description']}"
            
            grouped_lines.append(line)

        # Теперь обрезаем с конца (чтобы оставить свежие события), если вылезли за лимит
        # Но так как мы формировали список linear, нам нужно хитро обрезать начало.
        
        final_text = ""
        # Собираем с конца, пока влазит
        buffer = []
        current_tokens = 0
        
        for line in reversed(grouped_lines):
            tokens = len(self.tokenizer(line)) + 1
            if current_tokens + tokens > max_tokens:
                break
            buffer.append(line)
            current_tokens += tokens
            
        # Разворачиваем обратно в нормальный порядок
        return "\n".join(reversed(buffer))

    # TODO: все запросы должны быть в репозитории БД
    def _fetch_recent_chronicle_events(self, limit: int = 5):
        """
        Запрашивает последние Эпизоды для анализа сюжета.
        ВАЖНО: Возвращает ID, чтобы можно было создать связи в графе.
        """
        query = """
        MATCH (e:Episode)
        RETURN e.id AS id, e.name AS name, e.summary AS description, e.start_tick AS tick
        ORDER BY e.start_tick DESC
        LIMIT $limit
        """
        events = []
        with self.graph_builder.neo4j.driver.session() as session:
            result = session.run(query, limit=limit)
            for record in result:
                data = record.data()
                # Хак для форматтера контекста (он ищет 'loc_name', но для Эпизода имя и есть локация)
                data['loc_name'] = data['name'] 
                events.append(data)
        
        # Разворачиваем [Old -> New] для корректного чтения LLM
        return events[::-1]

    def _process_relationships(self, relationships: List[ExtractedRelationship], 
                               full_registry: Dict[str, str], 
                               current_loc_id: str):
        
        print(f"   🔗 Processing {len(relationships)} raw links...")
        
        last_subject_id = None
        
        for rel in relationships:
            try:
                # 1. Resolve IDs (как и раньше)
                subj_id = self._resolve_entity_id(rel.subject_name, full_registry, current_loc_id, last_subject_id)
                if subj_id: last_subject_id = subj_id
                
                obj_id = self._resolve_entity_id(rel.target_name, full_registry, current_loc_id, last_subject_id)
                
                if not subj_id or not obj_id:
                    continue

                # === НОВАЯ ЛОГИКА: SANITY CHECK ===
                
                # Получаем типы сущностей из метаданных синтезатора
                # (GraphBuilder наполнил self.synthesizer._metadata на Pass 2)
                subj_meta = self.synthesizer._metadata.get(subj_id, {})
                obj_meta = self.synthesizer._metadata.get(obj_id, {})
                
                subj_type = subj_meta.get('category', 'UNKNOWN')
                obj_type = obj_meta.get('category', 'UNKNOWN')
                
                # Определяем сырой тип связи (через маппер или LLM output)
                # Допустим, LLM вернула category="PHYSICAL" description="inside"
                from src.ingestion.mappers import RELATIONS
                raw_rel_type = RELATIONS.map_container(rel.description) or "RELATED_TO"
                
                # Если LLM уже пометила это как MENTAL в промпте
                if rel.category == "MENTAL":
                    raw_rel_type = "THINKS_OF"

                # ЗАПУСКАЕМ САНИТАЙЗЕР
                final_rel_type = RelationshipSanitizer.validate_and_fix(
                    subj_type, obj_type, raw_rel_type, rel.description
                )
                
                print(f"      Link: {subj_meta.get('name')} ({subj_type}) -[{final_rel_type}]-> {obj_meta.get('name')} ({obj_type})")

                # === СОХРАНЕНИЕ В NEO4J ===
                
                if final_rel_type == "LOCATED_AT":
                    # Физическое присутствие
                    self.graph_builder.neo4j.link_possession(item_id=subj_id, owner_id=obj_id, rel_type="LOCATED_AT")
                    
                elif final_rel_type == "POSSESSES":
                    self.graph_builder.neo4j.link_possession(item_id=obj_id, owner_id=subj_id, rel_type="EQUIPPED")
                    
                elif final_rel_type == "NEAR":
                    self.graph_builder.neo4j.link_social(subj_id, obj_id, "NEAR", 1.0)
                    
                elif final_rel_type in ["THINKS_OF", "RECALLS", "MENTIONED_BY"]:
                    # Это ментальная связь, она НЕ двигает фигурки на карте
                    self.graph_builder.neo4j.driver.execute_query(
                        "MATCH (a {id: $aid}), (b {id: $bid}) MERGE (a)-[:THINKS_OF]->(b)",
                        aid=subj_id, bid=obj_id
                    )

                # B. SOCIAL (Эмоции, Иерархия)
                elif final_rel_type == "SOCIAL":
                    # "hates", "loves", "serves"
                    rel_type = RELATIONS.map_social(rel.description) or "NEUTRAL"
                    # Тут можно добавить анализ тональности для intensity (пока 1.0)
                    self.graph_builder.neo4j.link_social(subj_id, obj_id, rel_type, intensity=1.0)

                # C. SPATIAL (Пространство)
                elif final_rel_type == "SPATIAL":
                    # Два варианта:
                    # 1. "Сундук стоит НА столе" (Containment)
                    # 2. "Дверь ведет В коридор" (Topology)
                    
                    # Пробуем понять, это Containment? ("on", "in", "under")
                    cont_type = RELATIONS.map_container(rel.description)
                    
                    if cont_type in ["LOCATED_AT", "IS_INSIDE"]:
                         # (Object)-[:LOCATED_AT]->(Subject) "Chest on Table" -> Table is parent
                         # Тут аккуратно с направлением: "X is on Y". X is item, Y is container.
                         # Subject (X) -> Target (Y)
                         self.graph_builder.neo4j.link_possession(item_id=subj_id, owner_id=obj_id, rel_type=cont_type)
                    else:
                        # Возможно, это топологическая связь (проход)?
                        edge_type = RELATIONS.map_edge(rel.description)
                        if edge_type:
                             self.graph_builder.neo4j.link_locations(subj_id, obj_id, edge_type)

                # D. KNOWLEDGE (Секреты)
                elif final_rel_type == "KNOWLEDGE":
                    # "Knows about the murder"
                    # Здесь obj_id может быть Event или Secret. 
                    # Проверяем, мапится ли описание на KNOWS_SECRET
                    rel_type = RELATIONS.map_container(rel.description)
                    if rel_type == "KNOWS_SECRET":
                         self.graph_builder.neo4j.link_knowledge(subj_id, obj_id)

            except Exception as e:
                logging.error(f"      ❌ Link Error '{rel.subject_name}' -> '{rel.target_name}': {e}", exc_info=True)

    def _resolve_entity_id(self, name_query: str, 
                           registry: Dict[str, str], 
                           current_loc_id: str,
                           context_agent_id: Optional[str] = None) -> Optional[str]:
        
        clean = name_query.lower().strip()
        
        # 1. PRONOUNS (Местоимения)
        if clean in ["he", "she", "they", "it", "him", "her"]:
            if context_agent_id:
                # print(f"      🔄 Resolved Pronoun '{clean}' -> {context_agent_id}")
                return context_agent_id
            return None # Не знаем, о ком речь

        # 2. CONTEXT (Место)
        if clean in ["here", "this place", "room", "area", "ground"]:
            return current_loc_id
            
        # 3. DIRECT LOOKUP (Реестр)
        # Ищем точное совпадение ("Alice")
        if clean in registry:
            return registry[clean]
            
        # 4. PARTIAL LOOKUP (Если в тексте "The Key", а в реестре "Golden Key")
        # Этого не было, но это важно!
        for reg_name, uuid_val in registry.items():
            if clean in reg_name or reg_name in clean:
                # Опасно для коротких слов, но для "key" -> "golden key" сработает
                if len(clean) > 3: 
                    return uuid_val

        # 5. FUZZY DB SEARCH (Последний рубеж)
        # Если это совсем новая сущность, которую Macro-Pass пропустил
        fuzzy = self.graph_builder.neo4j.fuzzy_search_molecule(name_query) 
        if fuzzy:
            return fuzzy
            
        return None

