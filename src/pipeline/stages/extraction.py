import logging
from typing import List, Dict, Tuple, Optional
from llama_index.core import SimpleDirectoryReader, Document, PromptTemplate
from llama_index.core.schema import MetadataMode

from src.config import config
from src.pipeline.context import PipelineContext
from src.pipeline.stages.ingestion import BatchIngestor
from src.ingestion.scene_splitter import AdaptiveMicroSplitter
from src.ingestion.schemas import ExtractionBatch
from src.custom_program import LocalStructuredProgram as LLMTextCompletionProgram

class DocumentExtractor:
    """
    Stage 1: Text Processing & Extraction.
    Отвечает за:
    1. Чтение файлов.
    2. Macro-Pass (построение скелета через GraphBuilder).
    3. Micro-Pass (умная нарезка и извлечение сущностей/связей).
    4. Передачу данных в BatchIngestor.
    """

    def __init__(self, ctx: PipelineContext):
        self.ctx = ctx
        
        # Инициализируем консьюмера (он будет сохранять данные)
        self.ingestor = BatchIngestor(ctx)
        
        # Инициализируем программу извлечения
        self._init_programs()

    def _init_programs(self):
        """
        Инициализация промптов и LLM программы. 
        Промпт вынесен сюда, чтобы не захламлять основной код.
        """
        prompt_templ = PromptTemplate(
            "Analyze the text chunk as a Game Engine Parser.\n"
            "Extract distinct entities and system interactions based on the following Ontology:\n\n"
            
            "1. MOLECULES (Entities):\n"
            "- AGENT: Beings with Will (Characters, Monsters).\n"
            "- GROUP: Factions or Squads.\n"
            "- ASSET: Objects. Distinguish between 'ARTIFACT' (Unique/Named) and 'COMMODITY' (Gold, Food, Ammo).\n"
            "- CONSTRUCT: Spells, Skills, or Phenomena. NOT verbs.\n"
            "- LORE: Information, secrets, codes.\n"
            "   - **CRITICAL**: The 'Description' MUST be a DIEGETIC FACT derived from THIS text chunk.\n"
            "   - If an entity is present but does nothing significant, SKIP IT.\n\n"
            
            "2. INTERACTIONS (Verbs & Actions):\n"
            "- EXTRACT significant actions.\n"
            "- IF it involves skill checks/combat/resources -> Label as MECHANIC.\n"
            "- IF it is purely narrative -> Label as FLAVOR.\n\n"
            
            "3. RELATIONSHIPS:\n"
            "- Connect entities logically (PHYSICAL, SOCIAL, MENTAL, LOGICAL).\n"
            "- Context Rules:\n"
            "   -- If context is 'MEMORY', prefer MENTAL links.\n"
            "   -- If context is 'PHYSICAL', use SPATIAL/LOCATED_AT links.\n\n"
            
            "TEXT CHUNK:\n{text_chunk}\n\n"
        )
        
        self.extractor_program = LLMTextCompletionProgram(
            output_cls=ExtractionBatch,
            llm=self.ctx.llm,
            prompt=prompt_templ, 
            verbose=True,
            # API ключи теперь берутся из LLM-клиента внутри ctx, 
            # но если LocalStructuredProgram требует явно:
            api_key=config.llm.api_key,
            base_url=config.llm.base_url
        )

    def process_directory(self, input_dir: str, source_id: str):
        """
        Главная точка входа для обработки папки.
        """
        reader = SimpleDirectoryReader(input_dir)
        documents = reader.load_data()
        
        print(f"🚀 Extractor: Found {len(documents)} documents in '{input_dir}' for source '{source_id}'.")

        for doc in documents:
            self._process_single_document(doc, source_id)

    def _process_single_document(self, doc: Document, source_id: str):
        source_ref = doc.doc_id
        print(f"\n📄 Processing Document: {source_ref}")

        # === PHASE 1: MACRO-PASS (SKELETON) ===
        # Делегируем GraphBuilder'у построение сцен и скелета.
        # Теперь GraphBuilder берется из контекста.
        scene_ranges, entity_registry = self.ctx.graph_builder.build_skeleton_v2(doc.text, source_ref, source_id)
        
        # === PHASE 2: MICRO-PASS (FLESH) ===
        self._process_micro_chunks(doc, source_ref, scene_ranges, entity_registry, source_id)

    def _process_micro_chunks(self, document: Document, source_ref: str, 
                              scene_ranges: List[tuple], 
                              entity_registry: Dict[str, str],
                              source_id: str):
        
        print(f"   🔍 Micro-pass (Adaptive Semantic with Context Injection)...")
        
        # 1. Инициализация Сплиттера (используем ресурсы из Context)
        micro_parser = AdaptiveMicroSplitter(
            embedder=self.ctx.embedder,
            tokenizer=self.ctx.tokenizer, 
            min_tokens=500,
            max_tokens=2000,
            base_threshold=0.35
        )
        
        # 2. Нарезка
        nodes = micro_parser.get_nodes_from_documents([document])
        
        for i, node in enumerate(nodes):
            # Получаем текст и координаты
            node_text = node.get_content(metadata_mode=MetadataMode.NONE)
            start_idx = node.metadata.get("start_char_idx", 0)
            end_idx = node.metadata.get("end_char_idx", len(node_text))
            
            # Вычисляем центр для поиска контекста
            chunk_center = start_idx + (end_idx - start_idx) // 2
            
            # 3. Context Injection (Связь Macro и Micro)
            loc_id, context_data = self._find_location_for_offset(chunk_center, scene_ranges)
            
            # Формируем префикс для LLM, чтобы она понимала, где происходит действие
            context_prefix = ""
            if context_data:
                label = context_data.get('label', 'Unknown Context')
                sc_type = context_data.get('type', 'PHYSICAL')
                
                if sc_type != "PHYSICAL":
                    context_prefix = (
                        f"[SCENE TYPE: {sc_type} | CONTEXT: {label}]\n"
                        "NOTE: Entities here are likely MEMORIES or THOUGHTS.\n\n"
                    )
                else:
                    context_prefix = f"[SCENE: {label}]\n"
            
            final_chunk_text = context_prefix + node_text
            
            # 4. Вызов LLM
            try:
                # Результат — это Pydantic объект ExtractionBatch
                data: ExtractionBatch = self.extractor_program(text_chunk=final_chunk_text)
                
                # 5. HANDOFF -> INGESTION STAGE
                # Мы не сохраняем ничего здесь. Мы передаем добытую руду на завод (Ingestor).
                self.ingestor.process(
                    batch=data,
                    source_ref=source_ref,
                    loc_id=loc_id,
                    entity_registry=entity_registry,
                    source_id=source_id,
                    current_tick=i
                )
                
            except Exception as e:
                logging.error(f"Error extracting from micro-chunk {i}: {e}", exc_info=True)

    def _find_location_for_offset(self, offset: int, ranges: List[tuple]) -> Tuple[Optional[str], Optional[dict]]:
        """
        Ищет, в какой сцене находится точка offset.
        ranges format: [(start, end, loc_uuid, context_data), ...]
        """
        for start, end, loc_uuid, context_data in ranges:
            if start <= offset < end:
                return loc_uuid, context_data
        return None, None
    