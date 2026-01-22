# ontology_topology.py
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
from src.models.ecs.ontology_schemas import SemanticVector, Sphere

# === 1. ПРИМИТИВ СВЯЗИ (Edge Definition) ===
class EdgeType(str, Enum):
    PHYSICAL_PATH = "path"      # Можно пройти ногами
    VISUAL_LOS = "line_of_sight" # Видно, но нельзя пройти (пропасть)
    HIDDEN_SECRET = "secret"    # Нужен Perception check
    PORTAL = "portal"           # Телепорт/Переход в другую локацию

class GraphEdge(BaseModel):
    """
    Описание связи между двумя узлами в шаблоне.
    """
    from_slot_index: int        # Индекс слота в списке шаблона
    to_slot_index: int
    type: EdgeType = EdgeType.PHYSICAL_PATH
    
    # Вектор "сложности" перехода (Cost)
    # {material: 0.8} -> Трудно пройти (Гора)
    # {cognitive: 0.5} -> Нужен пароль/магия
    traversal_cost: SemanticVector = Field(default_factory=SemanticVector)
    
    # Теги для генератора (например, "bridge", "ladder")
    # Чтобы LLM мог описать этот переход ("Скрипучий мост")
    tags: List[str] = Field(default_factory=list)

# === 2. АБСТРАКТНЫЙ УЗЕЛ (Slot) ===
class NodeSlot(BaseModel):
    """
    Место под локацию или сущность.
    Это 'дырка' в шаблоне, которую надо заполнить Молекулой.
    """
    id: str                 # "slot_entrance", "slot_boss_room"
    
    # Векторный запрос для заполнения (Search Query)
    # "Найди мне что-то тесное, темное и опасное"
    query_vector: SemanticVector = Field(default_factory=SemanticVector)
    
    # Ограничения (Constraints)
    required_sphere: Optional[Sphere] = None
    
    # Min/Max количество сущностей, генерируемых в этом слоте
    # (Например, в слоте "Лес" можно сгенерить 5-10 деревьев)
    min_instances: int = 1
    max_instances: int = 1

# === 3. ШАБЛОН ТОПОЛОГИИ (The Map Blueprint) ===
class TopologyTemplate(BaseModel):
    id: str
    name: str               # "Hub and Spoke", "Linear Dungeon", "Grid City"
    description: str        # Для LLM/Generator
    
    # Вектор стиля топологии (для поиска)
    # {Social: 1.0} -> Иерархическая структура (Замок)
    # {Social: -1.0} -> Хаотичная структура (Трущобы/Лабиринт)
    query_vector: SemanticVector = Field(default_factory=SemanticVector)
    
    # Структура
    slots: List[NodeSlot]
    edges: List[GraphEdge]
    
    # Метаданные для рендеринга (опционально)
    # layout_hint: "circular" | "tree" | "grid"
    layout_type: str = "organic"
    