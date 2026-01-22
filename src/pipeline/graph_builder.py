# src/pipeline/graph_builder.py
from __future__ import annotations
from typing import Dict, List, Tuple, TYPE_CHECKING

# Импортируем воркеров. 
# ВАЖНО: Эти файлы НЕ должны импортировать PipelineContext в runtime!
from src.pipeline.workers.topology_mapper import TopologyMapper
from src.pipeline.workers.entity_registrar import EntityRegistrar
from src.pipeline.workers.chronicle_weaver import ChronicleWeaver

# Разрываем цикл: импортируем Context только для проверки типов IDE
if TYPE_CHECKING:
    from src.pipeline.context import PipelineContext

class GraphBuilder:
    """
    Main Orchestrator for Skeleton Construction.
    Facade for specialized workers.
    """
    def __init__(self, ctx: PipelineContext): 
        """
        Инициализация. Принимает готовый контекст.
        """
        self.ctx = ctx
        
        # Инициализируем воркеров, передавая им контекст
        self.mapper = TopologyMapper(ctx)
        self.registrar = EntityRegistrar(ctx)
        self.weaver = ChronicleWeaver(ctx)

    def build_skeleton_v2(self, full_text: str, source_doc: str, source_id: str):
        """
        Новый метод входа для построения скелета мира.
        """
        print(f"🏗️  Building Skeleton for: {source_doc} (World: {source_id})")
        
        # 1. Pass 1: Topology (Наводчик)
        # Определяет сцены и Cast (кто в них участвует)
        scene_ranges = self.mapper.map_scenes(full_text, source_doc, source_id)
        
        # 2. Pass 2: Entities (Перепись)
        # Находит все имена собственные и регистрирует UUID
        scene_texts = [full_text[s:e] for s, e, _, _ in scene_ranges]
        self.registrar.extract_and_register(scene_texts, source_doc, source_id)
        
        # Загружаем найденные имена в Резолвер, чтобы Pass 3 мог их использовать
        registry_data = self.registrar.get_registry()
        self.ctx.resolver.load_registry(registry_data)

        # 3. Pass 3: Chronicle (Летописец)
        # Создает события и связывает их
        self.weaver.weave(full_text, scene_ranges, source_doc, source_id)
        
        print("✅ Skeleton Build Complete.")
        return scene_ranges, registry_data
    