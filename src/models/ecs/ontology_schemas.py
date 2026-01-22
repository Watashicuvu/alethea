# src/models/ecs/ontology_schemas.py
import uuid
import math
from enum import Enum
from typing import List, Dict, Optional, Any, Set, Literal
from pydantic import BaseModel, Field

# ==============================================================================
# 1. FUNDAMENTAL DIMENSIONS (Сферы Бытия)
# ==============================================================================

class Sphere(str, Enum):
    MATERIAL = "material"     # Физика, Ресурсы
    VITALITY = "vitality"     # Биология, Выживание
    SOCIAL = "social"         # Иерархия, Связи
    COGNITIVE = "cognitive"   # Разум, Магия, Идеи

# === УРОВЕНЬ 2: МОЛЕКУЛЫ (Prototypes) ===
class SlotDefinition(BaseModel):
    name: str               # "Core Weapon"
    required_sphere: Sphere # "material"
    
    # Текстовое описание того, что искать (для генератора)
    # Напр: "Something sharp and metallic used for attacking"
    search_query_text: str 
    
    # Вектор, сгенерированный из search_query_text.
    # В рантайме мы ищем атомы, близкие к этому вектору.
    search_query_vector: List[float] 
    
    threshold: float = 0.6 # Насколько точным должен быть поиск

class MoleculePrototype(BaseModel):
    id: str
    name: str
    description: str
    
    # Вектор самой молекулы (для поиска "Create Monster")
    vector: List[float]
    
    # Топология: список слотов, которые нужно заполнить атомами
    slots: List[SlotDefinition]

# ==============================================================================
# 2. SEMANTIC MATH (Векторы)
# ==============================================================================

class SemanticVector(BaseModel):
    """
    Математическое представление 'Смысла'.
    """
    material: float = 0.0
    vitality: float = 0.0
    social: float = 0.0
    cognitive: float = 0.0
    
    # Реальный эмбеддинг (SBERT) для поиска по базе знаний
    #embedding: Optional[List[float]] = Field(default=None, repr=False)

    def distance_to(self, other: 'SemanticVector') -> float:
        return math.sqrt(
            (self.material - other.material)**2 +
            (self.vitality - other.vitality)**2 +
            (self.social - other.social)**2 +
            (self.cognitive - other.cognitive)**2
        )

    def merge(self, other: 'SemanticVector', weight: float = 1.0) -> 'SemanticVector':
        return SemanticVector(
            material=self.material + (other.material * weight),
            vitality=self.vitality + (other.vitality * weight),
            social=self.social + (other.social * weight),
            cognitive=self.cognitive + (other.cognitive * weight)
        )

# ==============================================================================
# 3. NARRATIVE DEPTH (Секреты и Айсберг) — NEW!
# ==============================================================================

class SecretType(str, Enum):
    IDENTITY = "identity"       # Скрытая роль (Король в изгнании, Шпион)
    CONNECTION = "connection"   # Скрытая связь (Любовник врага, Должник мафии)
    OBJECT = "object"           # Скрытый предмет (Карта сокровищ в сапоге)
    HISTORY = "history"         # Скрытое прошлое (Дезертир, Убийца)

class SecretDefinition(BaseModel):
    """
    То, что скрыто 'под водой'.
    """
    id: str
    type: SecretType
    description: str # Текстовое описание для LLM/Director ("Is a spy for the Crimson King")
    
    # Базовая сложность обнаружения (0.0 - 1.0)
    # DirectorSystem может менять это значение в зависимости от Pacing игрока
    base_discovery_threshold: float = 0.5
    
    # Векторная связь с Глобальным Сюжетом
    # Позволяет Режиссеру найти секрет, релевантный текущей Войне или Революции
    linked_global_event_vector: List[float] = Field(default_factory=list)
    
    # Триггер раскрытия: ID квеста, диалога или катсцены, 
    # который запускается, когда игрок раскрывает секрет.
    reveal_trigger_id: Optional[str] = None
    
    # Метаданные (например, улики, которые ведут к секрету)
    clues: List[str] = Field(default_factory=list)

# ==============================================================================
# 4. COMPONENT DEFINITION (Чертежи ECS)
# ==============================================================================

class LatentPotentialRule(BaseModel):
    """Правило для Emergent Gameplay (напр. съесть чешую)"""
    trigger_context: str
    result_component_id: str
    probability: float = 1.0
    modifiers: Dict[str, Any] = Field(default_factory=dict)

class EvolutionRule(BaseModel):
    """Пассивное изменение (гниение, ржавчина)"""
    condition_axis: str
    operator: Literal["gt", "lt"] = "lt"
    threshold: float
    effect_delta: Dict[str, float]

class TopologyRef(BaseModel):
    """Ссылка на шаблон топологии (Граф)"""
    template_id: str        # ID шаблона (напр. "topo_dungeon_halls")
    is_generated: bool = False # Был ли уже сгенерирован внутренний мир?

class ComponentDefinition(BaseModel):
    """Статическое описание компонента"""
    id: str
    name: str
    sphere: Sphere
    description: str = ""
    base_vector: SemanticVector = Field(default_factory=SemanticVector)
    affordances: Set[str] = Field(default_factory=set)
    latent_potential: List[LatentPotentialRule] = Field(default_factory=list)
    evolution_rules: List[EvolutionRule] = Field(default_factory=list)
    topology_ref: Optional[TopologyRef] = None
    default_data: Dict[str, Any] = Field(default_factory=dict)

# ==============================================================================
# 5. RUNTIME ENTITIES (Живые объекты)
# ==============================================================================

class ComponentInstance(BaseModel):
    definition_id: str
    data: Dict[str, Any] = Field(default_factory=dict)
    vector_modifier: SemanticVector = Field(default_factory=SemanticVector)

class WorldEntity(BaseModel):
    """
    Универсальная сущность с поддержкой ECS и Narrative Layers.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str
    parent_id: Optional[str] = None 
    
    # Слой 1: Явные компоненты (Физика, Экономика)
    components: Dict[str, ComponentInstance] = Field(default_factory=dict)
    
    # Слой 2: Скрытые секреты (Драматургия)
    # Сущность может иметь несколько слоев глубины
    secrets: List[SecretDefinition] = Field(default_factory=list)
    
    # Кэшированный вектор (сумма явных компонентов)
    cached_vector: SemanticVector = Field(default_factory=SemanticVector)

    # СЛОИ КОНСИСТЕНТНОСТИ
    # Формат: "/entity_id_country/entity_id_city/entity_id_house/"
    hierarchy_path: str = Field(default="")
    
    # NEW: Уровень абстракции (Tier)
    # 0 = World, 1 = Region, 2 = Settlement, 3 = Organization, 4 = Character, 5 = Item
    hierarchy_tier: int = 0

    # NEW: Aggregate Vector
    # Вектор, описывающий "совокупную мощь" детей, отдельно от личного вектора сущности.
    # Это позволит искать "Богатые города" (aggregate_vector.material is High),
    # отличая их от "Городов из золота" (base_vector.material is High).
    aggregate_vector: SemanticVector = Field(default_factory=SemanticVector)

    def get_component(self, comp_id: str) -> Optional[ComponentInstance]:
        return self.components.get(comp_id)
    
    def has_affordance(self, action_tag: str, definitions_db: Dict[str, ComponentDefinition]) -> bool:
        """
        Проверяет, можно ли совершить действие, сканируя определения компонентов.
        """
        for comp_inst in self.components.values():
            defn = definitions_db.get(comp_inst.definition_id)
            if defn and action_tag in defn.affordances:
                return True
        return False
    
    def recalculate_vector(self, definitions_db: Dict[str, ComponentDefinition]):
        new_vec = SemanticVector()
        for comp in self.components.values():
            defn = definitions_db.get(comp.definition_id)
            if defn:
                new_vec = new_vec.merge(defn.base_vector)
                new_vec = new_vec.merge(comp.vector_modifier)
        self.cached_vector = new_vec
        
# ======   УДОБНЫЕ МОДЕЛИ ДЛЯ КОНТРОЛЯ   ========

class GlobalModifier(BaseModel):
    """
    Глобальное правило, меняющее физику или логику мира.
    Например: "Во время чумы лечение ослаблено на 50%".
    """
    id: str  # "plague_debuff", "full_moon_magic_boost"
    name: str
    
    # На какую сферу влияет?
    target_sphere: Sphere  # Sphere.VITALITY
    
    # Множитель для проверок сложности (Difficulty Check)
    difficulty_multiplier: float = 1.0 
    
    # Множитель для эффективности действий (Effect Magnitude)
    effect_multiplier: float = 1.0
    
    # Векторное смещение (все события становятся чуть более "мрачными")
    vector_shift: SemanticVector = Field(default_factory=SemanticVector)

class WorldStateSnapshot(BaseModel):
    """
    Слепок глобального состояния мира в конкретный тик времени.
    """
    tick: int = 0
    current_date_str: str = "Year 1, Day 1" # Human-readable дата
    
    # 1. Глобальный Вектор Атмосферы (Zeitgeist)
    # Определяет общее настроение: "Эпоха Просвещения" или "Темные Века".
    # Влияет на генерацию новых сущностей (Vibe-driven generation).
    global_atmosphere: SemanticVector = Field(default_factory=SemanticVector)
    
    # 2. Активные Глобальные Модификаторы
    # Список действующих правил (Законы физики/магии/короля)
    active_modifiers: List[GlobalModifier] = Field(default_factory=list)
    
    # 3. Глобальные Счетчики (Economy & Metadata)
    # { "mana_density": 0.8, "gold_inflation": 1.2, "chaos_level": 5 }
    global_variables: Dict[str, float] = Field(default_factory=dict)
    
    # 4. Ссылки на активные Нарративные Арки (Сюжеты)
    # Какие глобальные сценарии сейчас разыгрываются? (Война, Праздник)
    active_arc_ids: List[str] = Field(default_factory=list)

    def get_difficulty_mod(self, sphere: Sphere) -> float:
        """Считает итоговую сложность действий в заданной сфере"""
        mod = 1.0
        for m in self.active_modifiers:
            if m.target_sphere == sphere:
                mod *= m.difficulty_multiplier
        return mod
    