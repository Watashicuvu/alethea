from __future__ import annotations
import uuid
import logging
from typing import TYPE_CHECKING, Dict, List
from llama_index.core import PromptTemplate
from qdrant_client.models import PointStruct

from src.config import config
from src.ingestion.graph_schemas import EntityBatch, DetectedEntity
from src.ingestion.game_math import GameMath
from src.custom_program import LocalStructuredProgram as LLMTextCompletionProgram

#from src.pipeline.context import PipelineContext

if TYPE_CHECKING:
    from src.pipeline.context import PipelineContext

class EntityRegistrar:
    """
    Worker 2: Entity Discovery.
    Цель: Найти всех персонажей и предметы, выдать им UUID и зарегистрировать в реестре.
    """
    def __init__(self, ctx: PipelineContext):
        self.ctx = ctx
        self.registry: Dict[str, str] = {} # Name -> UUID
        self._init_program()

    def _init_program(self):
        prompt = PromptTemplate(
            "Analyze the narrative text. Extract persistent 'Canonical Molecules'.\n"
            "Classify them: AGENT, GROUP, ASSET, LOCATION, CONSTRUCT, LORE.\n"
            "RULES: Ignore transient items. Merge synonyms.\n"
            "TEXT:\n{text}\n"
        )
        self.program = LLMTextCompletionProgram(
            output_cls=EntityBatch,
            llm=self.ctx.llm,
            prompt=prompt,
            verbose=True,
            api_key=config.llm.api_key,
            base_url=config.llm.base_url
        )

    def extract_and_register(self, chunks: List[str], source_doc: str, source_id: str):
        print(f"   🧬 Pass 2: Extracting Canonical Molecules...")
        
        # Для оптимизации можно сканировать не все чанки, а каждый второй,
        # или использовать макро-саммари. Но пока идем по всем.
        for i, chunk in enumerate(chunks):
            try:
                res: EntityBatch = self.program(text=chunk)
                for ent in res.entities:
                    if ent.category == "LOCATION":
                        # Локации обрабатывает TopologyMapper, пропускаем
                        continue
                    
                    self._register_molecule(ent, source_doc, source_id)
            except Exception as e:
                logging.error(f"Entity pass error chunk {i}: {e}")

    def _register_molecule(self, entity: DetectedEntity, source_doc: str, source_id: str):
        key = entity.name.lower().strip()
        if key in self.registry:
            return # Уже знаем

        # Генерируем ID
        uid = str(uuid.uuid5(uuid.NAMESPACE_DNS, key))
        self.registry[key] = uid

        print(f"      🧬 New Molecule: [{entity.category}] {entity.name}")

        # 1. Calc Stats (GameMath)
        vec_text = f"{entity.name}. {entity.description}"
        emb = self.ctx.embedder.get_text_embedding(vec_text)
        raw_stats = self.ctx.projector.project(emb)
        
        # Применяем маску типа (например, ASSET более материален)
        final_stats = GameMath.calculate_stats(
            base_vector_stats=raw_stats,
            atom_influence={}, 
            category=entity.category.value
        )

        # 2. Neo4j Stub
        self.ctx.repos.entities.upsert_molecule(
            uid=uid, name=entity.name, category=entity.category.value,
            stats=final_stats
        )

        # 3. Qdrant Draft
        payload = {
            "name": entity.name,
            "type": entity.category.value,
            "subtype": entity.subtype.value if entity.subtype else None,
            "description": entity.description,
            "source_id": source_id,
            "stats": final_stats,
            "is_draft": True
        }
        self.ctx.qdrant.upsert("molecules", [PointStruct(id=uid, vector=emb, payload=payload)])

        # 4. Collect for Synthesis
        # (Опционально: можно сразу добавить в память синтезатора, чтобы он знал о сущности)
        self.ctx.synthesizer.collect(
            uid=uid, 
            observation=f"[MACRO-REGISTRY] {entity.description}",
            metadata={"name": entity.name, "category": entity.category.value, "world_id": source_id}
        )

    def get_registry(self) -> Dict[str, str]:
        return self.registry
    