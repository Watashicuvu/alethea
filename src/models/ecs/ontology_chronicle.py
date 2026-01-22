from enum import Enum
from typing import List, Dict, Optional, Any, Set
from pydantic import BaseModel, Field
from src.models.ecs.ontology_schemas import SemanticVector
from src.models.ecs.ontology_verbs import PacingState

class CausalType(str, Enum):
    DIRECT = "direct"       # А вызвало Б (Физика)
    MOTIVATION = "motivation" # А стало причиной мотивации для Б (Психология)
    ENABLE = "enable"       # А сделало возможным Б (открыло дверь)

class WorldDelta(BaseModel):
    """
    Атомарное изменение мира.
    Используется для пересчета состояния (Fact-Checking).
    """
    entity_id: str
    
    # Что изменилось?
    component_changes: Dict[str, Any] = Field(default_factory=dict) # {hp: -10}
    vector_shift: Optional[SemanticVector] = None
    
    # Изменения тегов/статусов
    added_tags: Set[str] = Field(default_factory=set)
    removed_tags: Set[str] = Field(default_factory=set)

class ChronicleEvent(BaseModel):
    id: str
    tick: int               # Абсолютное время (или None, если событие "плавающее")
    
    name: str               # "Death of King Harlaus"
    description: str        # Для RAG и LLM
    
    # Semantic Search Index
    vector: SemanticVector  # Вектор события (Война, Трагедия)
    
    # === CAUSALITY GRAPH ===
    # Ссылки на события-причины. 
    # Если родитель исчезнет, это событие станет невалидным.
    parent_event_ids: List[str] = Field(default_factory=list)
    
    # === STATE CHANGE ===
    # Как это событие изменило мир?
    deltas: List[WorldDelta]
    
    # === BRANCHING ===
    # К какой временной линии относится (для мультивселенной)
    timeline_id: str = "main" 
    is_invalidated: bool = False # Флаг "Реткона"
    # При генерации мира "с нуля" оно вычисляется в рантайме.
    # При чтении книг (Ingestion) мы пытаемся его предсказать LLM'кой и сохранить.
    pacing: Optional[PacingState] = None
    
# ========  СЛОИ ОРКЕСТРАЦИИ  ========

# 1. СЛОТ РОЛИ (Кого нам нужно найти в мире, чтобы сыграть эту пьесу?)
class NarrativeRole(BaseModel):
    id: str                 # "role_aggressor", "role_victim", "role_peacemaker"
    description: str        # "A powerful faction leader seeking expansion"
    
    # Вектор для поиска кандидата в Qdrant
    query_vector: SemanticVector 
    
    # Ограничения (например, должен быть живым и иметь компонент "Король")
    required_tags: List[str] = Field(default_factory=list)

# 2. ШАБЛОН СОБЫТИЯ (Абстрактный узел сюжета)
class EventNodeTemplate(BaseModel):
    name: str               # человекочитаемое
    id: str                 # "evt_secret_meeting"
    description: str        # "Leaders meet in secret to discuss partition"
    #archetype_id: str       # один из шаблонов
    # Какие роли участвуют в этом конкретном шаге?
    participating_role_ids: List[str] 
    
    # Вектор эмоционального окраса шага
    step_vector: SemanticVector 
    
    # Потенциально:
    # Словарь: { "ID роли в архетипе события" : "ID роли в текущей арке" }
    # Это инструкция для движка: "На роль Агрессора возьми того, кто у нас тут Герой"
    #role_mapping: Dict[str, str]

# 3. НАРРАТИВНАЯ АРКА (Сценарий "Ялты" или "Ромео и Джульетты")
class NarrativeArcTemplate(BaseModel):
    id: str                 # "arc_political_summit", "arc_star_crossed_lovers"
    name: str
    description: str        # Полное описание сюжета для LLM
    
    # Глобальный вектор сюжета (для поиска "Похожее на Ромео и Джульетту")
    global_vector: SemanticVector 
    
    # Кого нужно найти в мире, чтобы запустить этот сюжет?
    cast: List[NarrativeRole]
    
    # Граф последовательности (можно упростить до списка для начала)
    sequence: List[EventNodeTemplate]
