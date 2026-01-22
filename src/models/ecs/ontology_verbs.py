# src/models/ecs/ontology_verbs.py
from enum import Enum
from typing import List, Dict, Any, Set
from pydantic import BaseModel, Field
from src.models.ecs.ontology_schemas import Sphere, SemanticVector

# === УРОВЕНЬ 1: ПРИМИТИВЫ ===
class PrimitiveType(str, Enum):
    MODIFY_VECTOR = "modify_vector"
    TRANSFORM = "transform"
    TRANSFER_ITEM = "transfer_item"
    MOVE_TO = "move_to"
    SPAWN_ENTITY = "spawn_entity"
    APPLY_TAG = "apply_tag"
    CREATE_RELATION = "create_relation"

class VerbPrimitive(BaseModel):
    type: PrimitiveType
    target_alias: str = "target" # enum! target | environment | ...
    params: Dict[str, Any] = Field(default_factory=dict)

# === УРОВЕНЬ 2: FLOW & PACING ===
class FlowPhase(str, Enum):
    OPENER = "opener"
    LINK = "link"
    FINISHER = "finisher"
    RECOVERY = "recovery"
    COUNTER = "counter"

class PacingState(BaseModel):
    """
    Динамические метаданные о драматургии события.
    """
    # Текущий уровень напряжения (0.0 - Chill, 1.0 - Climax/Death)
    tension_level: float = 0.0
    # Фаза ритма (Opener, Link, Climax, Recovery)
    phase: FlowPhase = FlowPhase.LINK
    # Насколько это событие изменило темп? 
    # (+0.5 = резкий скачок драмы, -0.3 = успокоение)
    momentum_delta: float = 0.0
    # True, если это событие "закрывает" сцену (Scene Finisher)
    is_scene_end: bool = False

class Synergies(BaseModel):
    requires_prev_tags: List[str] = Field(default_factory=list) # tags from taxonomy -> str
    bonus_vector: SemanticVector = Field(default_factory=SemanticVector)
    bonus_chance: float = 0.0

# === УРОВЕНЬ 3: ГЛАГОЛЫ ===
class VerbAtom(BaseModel):
    id: str
    name: str
    description: str
    
    # Вектор для резолвинга (Attack vs Defense)
    vector: SemanticVector = Field(default_factory=SemanticVector)
    sphere: Sphere 

    # Если здесь ["cut"], то глагол попадет в бакет "cut" в базе.
    required_affordances: Set[str] = Field(default_factory=set) 
    
    # Остальные проверки (мана, стамина, наличие ключей)
    requirements: Dict[str, Any] = Field(default_factory=dict)
    
    # Исполняемая часть
    effects_on_success: List[VerbPrimitive] = Field(default_factory=list)
    effects_on_failure: List[VerbPrimitive] = Field(default_factory=list)

    # Narrative Pacing
    flow_phase: FlowPhase = FlowPhase.LINK 
    style_tags: List[str] = Field(default_factory=list)
    combo_potential: Synergies = Field(default_factory=Synergies)
    momentum_delta: int = 0
    