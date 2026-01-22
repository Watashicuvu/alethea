from qdrant_client.models import PointStruct, VectorParams, Distance

from src.pipeline.context import PipelineContext
from src.config import config
from src.registries.all_registries import (
    ROLES, VERBS, TOPOLOGIES, EVENTS, ARCS, ATOMS
)

class OntologyLoader:
    """
    Stage 0: Static Ontology Loading.
    Загружает 'чертежи' (Blueprints) игрового мира в Qdrant.
    Это не данные из книг, а мета-правила: какие бывают роли, типы событий,
    шаблоны локаций.
    """

    def __init__(self, ctx: PipelineContext):
        self.ctx = ctx
        self._init_collection()

    def _init_collection(self):
        """Создает коллекцию для статики, если её нет."""
        if not self.ctx.qdrant.collection_exists("ontology_static"):
            self.ctx.qdrant.create_collection(
                collection_name="ontology_static",
                vectors_config=VectorParams(size=config.v_size, distance=Distance.COSINE),
                shard_number=1
            )

    def run(self, source_id: str = "core"):
        """
        Запускает индексацию всех реестров.
        source_id: метка версии правил (например 'core_v1', 'dlc_magic')
        """
        print(f"📚 Indexing Ontology (Source: {source_id})...")
        
        self._index_registry(ATOMS, "atoms", source_id)
        self._index_registry(ROLES, "role", source_id)
        self._index_registry(VERBS, "verb", source_id)
        self._index_registry(TOPOLOGIES, "topology", source_id)
        self._index_registry(EVENTS, "event_archetype", source_id)
        self._index_registry(ARCS, "arc_template", source_id)
        
        print("✅ Registry Indexing Complete.")

    def _index_registry(self, registry, doc_type: str, source_id: str):
        """
        Универсальный метод индексации любого реестра (Adapter Pattern).
        """
        points = []
        print(f"   ↳ Indexing {doc_type}s...")
        
        for item in registry.all():
            # 1. Готовим текст для вектора
            # Пытаемся найти описание. У разных объектов поля могут отличаться.
            desc = getattr(item, 'description', '')
            name = getattr(item, 'name', getattr(item, 'id', 'Unknown'))
            text_for_vec = f"{name}. {desc}"
            
            embedding = self.ctx.embedder.get_text_embedding(text_for_vec)
            
            # 2. Готовим Stats (для игровой логики)
            # Ищем поле vector, query_vector или global_vector
            stats = {}
            for field in ['vector', 'query_vector', 'global_vector']:
                val = getattr(item, field, None)
                if val:
                    # Если это Pydantic модель
                    if hasattr(val, 'model_dump'):
                        stats = val.model_dump()
                    elif isinstance(val, dict):
                        stats = val
                    break
            
            # 3. Готовим Payload
            payload = {
                "doc_type": doc_type,
                "source": source_id,
                "name": name,
                "description": desc,
                "stats": stats
            }
            
            # Добавляем специфичные поля, если они есть
            if hasattr(item, 'required_tags'): payload["required_tags"] = item.required_tags
            if hasattr(item, 'sphere'): payload["sphere"] = item.sphere
            if hasattr(item, 'layout_type'): payload["layout_type"] = item.layout_type
            
            points.append(PointStruct(
                id=item.id,
                vector=embedding,
                payload=payload
            ))
            
        if points:
            self.ctx.qdrant.upsert("ontology_static", points)
