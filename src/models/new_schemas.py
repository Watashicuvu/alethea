from typing import Set, Dict, List
from pydantic import BaseModel, Field
import uuid

from typing import List, Dict, Set, Optional, Tuple
from pydantic import BaseModel, Field
import uuid

# === 0. БАЗОВЫЕ СТРУКТУРЫ ===

class SemanticVector(BaseModel):
    """
    Вектор в 50-мерном пространстве атомов.
    """
    data: Dict[str, float] = {}

    def get(self, atom: str) -> float:
        return self.data.get(atom, 0.0)

    def add(self, atom: str, value: float):
        self.data[atom] = self.data.get(atom, 0.0) + value

    def merge(self, other: 'SemanticVector') -> 'SemanticVector':
        new_data = self.data.copy()
        for k, v in other.data.items():
            new_data[k] = new_data.get(k, 0.0) + v
        return SemanticVector(data=new_data)
    
    def sub(self, other: 'SemanticVector') -> 'SemanticVector':
        new_data = self.data.copy()
        for k, v in other.data.items():
            current = new_data.get(k, 0.0)
            # Вектор не может быть отрицательным в контексте импульса (но может в контексте дебаффа)
            new_data[k] = max(0.0, current - v) 
        return SemanticVector(data=new_data)

    def is_empty(self) -> bool:
        return all(v == 0 for v in self.data.values())

# === 1. МАТРИЦА ВЗАИМОДЕЙСТВИЙ (INTERACTION TENSOR) ===

class InteractionRule(BaseModel):
    source_atom: str      # Атом-Актор (Kinetics)
    target_atom: str      # Атом-Реципиент (Integrity)
    result_atom: str      # Атом-Результат (Damage/Effect)
    multiplier: float = 1.0 

# "Таблица умножения" вашего мира.
# В продакшене это грузится из конфига/CSV.
PHYSICS_LAWS = [
    # --- ФИЗИКА ---
    # Кинетика разрушает Целостность (Урон)
    InteractionRule(source_atom="kinetics", target_atom="mat_integrity", result_atom="structural_damage", multiplier=1.0),
    # Тепло разрушает Воду (Испарение)
    InteractionRule(source_atom="mat_thermal", target_atom="mat_water", result_atom="structural_damage", multiplier=2.0),
    
    # --- СОЦИУМ ---
    # Информация (Правда) разрушает Догматизм (Веру)
    InteractionRule(source_atom="cog_information", target_atom="cog_dogmatism", result_atom="structural_damage", multiplier=0.5),
    # Угроза (Агрессия) давит на Страх -> Подчинение
    InteractionRule(source_atom="soc_aggression", target_atom="vit_fear", result_atom="soc_submission", multiplier=1.0),
]

def resolve_tensor_interaction(source_vec: SemanticVector, target_vec: SemanticVector, conduct_axes: Set[str]) -> Tuple[float, SemanticVector]:
    """
    Алгебраическое вычисление реакции.
    Возвращает:
    1. structural_stress (насколько сильно пострадала структура цели)
    2. byproduct_vector (побочные эффекты, например, пар или страх)
    """
    total_stress = 0.0
    byproducts = SemanticVector()

    for rule in PHYSICS_LAWS:
        # Проверяем, проводит ли молекула этот атом (Conductance Check)
        if rule.source_atom not in conduct_axes:
            continue

        s_val = source_vec.get(rule.source_atom)
        t_val = target_vec.get(rule.target_atom) # Это значение из Stability Profile

        if s_val > 0 and t_val > 0:
            # F = A * B * k
            force = s_val * t_val * rule.multiplier
            
            if rule.result_atom == "structural_damage":
                total_stress += force
            else:
                byproducts.add(rule.result_atom, force)
    
    return total_stress, byproducts

# === КОНФИГУРАЦИЯ (ОПРЕДЕЛЕНИЕ ТИПА МОЛЕКУЛЫ) ===

class MolecularDefinition(BaseModel):
    """
    Конфигурация типа молекулы (Blueprint).
    """
    name_id: str
    
    # HITBOX: Какие атомы эта молекула ловит?
    conductance_axes: Set[str] 
    
    # HP: Какие атомы держат её структуру? (Эти значения берутся из vector самой молекулы)
    stability_axes: Set[str]
    
    # PAYLOAD: Что высвобождается при разрушении/активации?
    reactivity_axes: Set[str]

    # Коэффициент поглощения (1.0 = стена, 0.1 = туман)
    absorption_factor: float = 1.0


class Molecule(BaseModel):
    """
    Экземпляр молекулы.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    definition: MolecularDefinition # Ссылка на правила
    
    # Вектор состояния (содержит значения для stability_axes и reactivity_axes)
    vector: SemanticVector 
    
    # Текущее здоровье структуры (абстрактное, нормированное 0..1 или абсолютное)
    integrity: float = 100.0 
    
    # Флаг для парсинга: если True, вектор неточен и требует доопределения
    is_fuzzy: bool = False

    def process_impulse(self, input_impulse: SemanticVector) -> Tuple[SemanticVector, SemanticVector]:
        """
        Главная функция взаимодействия.
        Returns:
            passed_impulse: Вектор, прошедший сквозь (Residual).
            reaction_impulse: Вектор реакции (Explosion/Heal).
        """
        # 1. Разделяем импульс на поглощенный и прошедший
        absorbed = SemanticVector()
        passed = SemanticVector()
        
        for atom, value in input_impulse.data.items():
            if atom in self.definition.conductance_axes:
                absorbed.add(atom, value * self.definition.absorption_factor)
                passed.add(atom, value * (1.0 - self.definition.absorption_factor))
            else:
                # Если молекула не проводит этот атом, он пролетает насквозь целиком
                passed.add(atom, value)

        if absorbed.is_empty():
            return passed, SemanticVector()

        # 2. Вычисляем Тензорное Взаимодействие (Стресс)
        stress, side_effects = resolve_tensor_interaction(
            source_vec=absorbed,
            target_vec=self.vector, # Stability atoms берутся отсюда
            conduct_axes=self.definition.conductance_axes
        )

        # 3. Применяем урон
        self.integrity -= stress
        
        reaction = side_effects

        # 4. Проверка на Коллапс (Collapse)
        if self.integrity <= 0:
            # Высвобождаем Payload (Reactivity)
            payload = SemanticVector()
            for atom in self.definition.reactivity_axes:
                val = self.vector.get(atom)
                if val > 0:
                    payload.add(atom, val)
            
            reaction = reaction.merge(payload)
            # В идеале здесь можно добавить Overkill (остаточный урон), но пока опустим
            
        return passed, reaction
    
class PolymerAgent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    
    # Слои защиты/функционала. Порядок важен: Outer -> Inner
    layers: List[Molecule]
    
    # Накопленные состояния (Buffs/Debuffs)
    state_vector: SemanticVector = SemanticVector()

    def receive_interaction(self, input_vector: SemanticVector) -> List[str]:
        """
        Обработка входящего события.
        Возвращает лог событий (для нарратива).
        """
        current_impulse = input_vector
        log = []
        
        log.append(f"Incoming Impulse: {current_impulse.data}")

        for i, molecule in enumerate(self.layers):
            if molecule.integrity <= 0:
                continue # Пропускаем разрушенные слои

            passed, reaction = molecule.process_impulse(current_impulse)
            
            # Логирование (упрощенно)
            if current_impulse.data != passed.data:
                damage = molecule.integrity  # diff placeholder
                log.append(f"Layer {molecule.definition.name_id} absorbed impulse. Reaction: {reaction.data}")
            
            # Обработка реакции (если молекула взорвалась/сработала)
            if not reaction.is_empty():
                # Реакция может быть внутренней (лечение) или внешней (взрыв).
                # В этой модели считаем, что реакция идет "внутрь" агента (в state_vector)
                # или наносит урон следующим слоям (цепная реакция).
                self.state_vector = self.state_vector.merge(reaction)
            
            current_impulse = passed
            
            if current_impulse.is_empty():
                break
        
        if not current_impulse.is_empty():
            log.append(f"Impulse reached Core (unabsorbed): {current_impulse.data}")
            # Остаток уходит в глобальное состояние агента
            self.state_vector = self.state_vector.merge(current_impulse)

        return log
    
class ArchetypeRecipe(BaseModel):
    archetype_id: str
    description: str
    # Список: (ID Молекулы, Имя Слоя, Дефолтный Вектор)
    # Порядок: Outer -> Inner
    layers_config: List[Tuple[MolecularDefinition, str, SemanticVector]]

    def assemble(self, name: str, vector_modifiers: Dict[str, float]) -> 'PolymerAgent':
        """
        Создает инстанс агента.
        vector_modifiers: Словарь вида {"phys_kinetics": 1.5, "vit_resilience": 0.8},
        который умножает/модифицирует дефолтные вектора всех слоев.
        """
        assembled_layers = []
        
        for mol_def, layer_name, default_vec in self.layers_config:
            # 1. Клонируем вектор
            final_vector = default_vec.copy()
            
            # 2. Применяем модификаторы из текста (орки сильнее, эльфы быстрее)
            # Здесь упрощенная логика: если модификатор есть, он влияет на главный axis молекулы
            # В реальном коде нужен более хитрый маппинг
            for axis, value in vector_modifiers.items():
                 # Если ось есть в молекуле — усиливаем её
                if axis in mol_def.conductance_axes or axis in mol_def.stability_axes:
                     # Примерно: current * modifier
                     pass 

            # 3. Вычисляем Integrity (HP слоя) на основе Stability Axis
            # Например, для брони это mat_integrity * multiplier
            integrity_val = 100.0 # Placeholder calculation
            
            assembled_layers.append(
                Molecule(
                    definition=mol_def,
                    vector=final_vector,
                    integrity=integrity_val
                )
            )

        return PolymerAgent(name=name, layers=assembled_layers)

