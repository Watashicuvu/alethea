from __future__ import annotations
import uuid
import logging
from typing import List, Tuple, Optional, Dict, TYPE_CHECKING
from llama_index.core import Document, PromptTemplate
from llama_index.core.schema import MetadataMode
from qdrant_client.models import PointStruct

from src.config import config
from src.ingestion.graph_schemas import SceneBatch
from src.ingestion.scene_splitter import SemanticSceneSplitter
from src.custom_program import LocalStructuredProgram as LLMTextCompletionProgram

#from src.pipeline.context import PipelineContext
if TYPE_CHECKING:
    from src.pipeline.context import PipelineContext

class TopologyMapper:
    """
    Worker 1: Topology & Scene Segmentation.
    Цель: Разбить текст на сцены и понять "Где мы находимся?".
    """
    def __init__(self, ctx: PipelineContext):
        self.ctx = ctx
        self._init_splitter()
        self._init_program()

    def _init_splitter(self):
        # Используем семантический сплиттер для крупных сцен
        self.splitter = SemanticSceneSplitter(
            llm=self.ctx.llm, 
            window_size=30_000
        )

    def _init_program(self):
        prompt = PromptTemplate(
            "Analyze the text chunk. Identify the PRIMARY physical location where the events occur.\n"
            "If the location changes, identify the dominant one.\n"
            "Provide a brief summary of the scene.\n\n"
            "TEXT:\n{text}\n"
        )
        self.program = LLMTextCompletionProgram(
            output_cls=SceneBatch,
            llm=self.ctx.llm,
            prompt=prompt,
            verbose=True,
            api_key=config.llm.api_key,
            base_url=config.llm.base_url
        )

    def map_scenes(self, full_text: str, source_doc: str, source_id: str) -> List[Tuple[int, int, str, dict]]:
        print(f"   🗺️  Pass 1: Mapping Scenes & Locations...")
        
        # 1. Нарезка (Macro Split)
        doc = Document(text=full_text)
        nodes = self.splitter.get_nodes_from_documents([doc])
        
        scene_ranges = []
        text_cursor = 0
        prev_loc_uuid = None

        for i, node in enumerate(nodes):
            node_text = node.get_content(metadata_mode=MetadataMode.NONE)
            
            # Метаданные от сплиттера
            scene_type = node.metadata.get("scene_type", "PHYSICAL")
            context_label = node.metadata.get("context_label", "")
            
            # Расчет координат
            start_idx = full_text.find(node_text, text_cursor)
            if start_idx == -1: start_idx = text_cursor
            end_idx = start_idx + len(node_text)
            text_cursor = end_idx

            context_data = {"type": scene_type, "label": context_label}
            
            try:
                # Определяем локацию
                current_loc_uuid = self._determine_location(
                    node_text, scene_type, context_label, 
                    prev_loc_uuid, source_doc, source_id
                )
                
                # Фиксируем диапазон
                if current_loc_uuid:
                    scene_ranges.append((start_idx, end_idx, current_loc_uuid, context_data))
                    
                    # Если перешли в новую физ. локацию — линкуем переход
                    if prev_loc_uuid and prev_loc_uuid != current_loc_uuid and scene_type == "PHYSICAL":
                        self.ctx.repos.locations.link_locations(prev_loc_uuid, current_loc_uuid, "TRANSITION")
                    
                    prev_loc_uuid = current_loc_uuid

            except Exception as e:
                logging.error(f"Error mapping scene {i}: {e}")

        return scene_ranges

    def _determine_location(self, text: str, scene_type: str, label: str, 
                            prev_uuid: str, source_doc: str, source_id: str) -> Optional[str]:
        """Решает, какой UUID присвоить текущему куску."""
        
        # A. Mental Scenes (Dreams/Memories) -> Остаемся на месте
        if scene_type in ["MEMORY", "DREAM", "THOUGHT"]:
            # Если мы не знаем, где стоим, создаем Unknown
            if not prev_uuid:
                return self._resolve_stub("Unknown Void", "Abstract space", source_doc, source_id)
            return prev_uuid

        # B. Physical Scenes -> Спрашиваем LLM
        aug_text = f"[SCENE CONTEXT: {label}]\n{text}"
        res: SceneBatch = self.program(text=aug_text)
        
        if not res.scenes:
            return prev_uuid

        scene_data = res.scenes[0]
        name = scene_data.location_name.strip()
        
        # Фильтр абстракций
        if len(name) < 3 or name.lower() in ["unknown", "none"]:
            return prev_uuid

        # Resolve ID
        return self._resolve_stub(name, scene_data.summary, source_doc, source_id)

    def _resolve_stub(self, name: str, summary: str, source_doc: str, source_id: str) -> str:
        """Ищет существующую локацию или создает новую (Stub)."""
        
        # 1. Fuzzy (Neo4j)
        fuzzy_id = self.ctx.repos.locations.fuzzy_search_location(name)
        if fuzzy_id: return fuzzy_id

        # 2. Semantic (Qdrant)
        vec_text = f"{name}. {summary}"
        vec = self.ctx.embedder.get_text_embedding(vec_text)
        
        result = self.ctx.qdrant.query_points(
            collection_name="skeleton_locations",
            query=vec,
            limit=1
        )
        hits = result.points
        
        if hits and hits[0].score > 0.93:
            return hits[0].id

        # 3. Create New Stub
        new_id = str(uuid.uuid4())
        
        # Сохраняем "скелет" в Neo4j
        self.ctx.repos.locations.upsert_stub(new_id, name, source_doc)
        
        # Сохраняем "черновик" в Qdrant (чтобы следующий чанк её нашел)
        # Нам нужны хоть какие-то статы, проецируем на лету
        loc_stats = self.ctx.projector.project(vec)
        self.ctx.qdrant.upsert("skeleton_locations", [PointStruct(
            id=new_id, vector=vec, payload={
                "name": name, "summary": summary, 
                "source_id": source_id, "stats": loc_stats
            }
        )])
        
        return new_id
    