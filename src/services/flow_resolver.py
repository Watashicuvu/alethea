#src/systems/resolution/flow_resolver.py
import random
from typing import List, Tuple, Optional, Set
from pydantic import BaseModel, Field
from src.models.ecs.ontology_verbs import VerbAtom, FlowPhase
from src.models.ecs.ontology_schemas import SemanticVector, Sphere

# Конфигурация штрафов/бонусов ритма (Data-Driven!)
FLOW_MATRIX = {
    # (Previous Phase -> Current Phase): Modifier
    (None, FlowPhase.OPENER): 0.1,    # Хорошее начало
    (None, FlowPhase.FINISHER): -0.4, # Нельзя ультовать с порога!
    
    (FlowPhase.OPENER, FlowPhase.LINK): 0.15, # Разгон
    (FlowPhase.LINK, FlowPhase.LINK): 0.05,   # Продолжение комбо
    (FlowPhase.LINK, FlowPhase.FINISHER): 0.3, # Идеальное завершение
    
    (FlowPhase.FINISHER, FlowPhase.OPENER): -0.1, # Нужна пауза (Recovery)
    (FlowPhase.RECOVERY, FlowPhase.OPENER): 0.1,  # Правильный выход из паузы
}

# ActionRecord -- это такой кэш для взаимодействий между сущностями;
# результат этих взаимодействий записывается в персистентную БД, но сам
# ActionRecord должен существовать только пока происходит взаимодействие
# не должен быть слишком умным; должен быть легковесный BERT для тегирования    
class SceneContext(BaseModel):
    # История последних N действий (для анализа комбо)
    history: List[ActionRecord] = Field(default_factory=list)
    
    # Текущий "Импульс" сцены (0..100)
    # 0 = Штиль, 100 = Кульминация/Хаос
    momentum: int = 0
    
    # Флаги состояния (например, "target_staggered", "defense_broken")
    active_tags: Set[str] = Field(default_factory=set)

    @property
    def last_action(self) -> Optional['ActionRecord']:
        return self.history[-1] if self.history else None

class FlowConflictResolver:
    def resolve(self, 
                actor_vector: SemanticVector, 
                target_vector: SemanticVector, 
                verb: VerbAtom, 
                context: SceneContext) -> Tuple[bool, dict]:
        """
        Возвращает (Success, DetailsLog)
        """
        details = {}

        # === 1. BASE VECTOR MATCH (Физика) ===
        # Сравниваем вектора в сфере действия глагола
        # Например, Sphere.MATERIAL (Attack vs Defense)
        axis = verb.sphere.value # "material"
        
        # Получаем значения (с учетом нормализации -1..1)
        actor_val = getattr(actor_vector, axis, 0)
        target_val = getattr(target_vector, axis, 0)
        
        # Базовый шанс (50% + разница сил)
        base_chance = 0.5 + (actor_val - target_val)
        details['base_chance'] = round(base_chance, 2)

        # === 2. FLOW MODIFIER (Ритм) ===
        prev_phase = context.last_action.phase if context.last_action else None
        
        # Ищем в матрице переходов. Если нет — штраф 0.0
        flow_mod = FLOW_MATRIX.get((prev_phase, verb.flow_phase), -0.05)
        details['flow_mod'] = flow_mod

        # === 3. SYNERGY / TAG MATCH (Стиль) ===
        synergy_mod = 0.0
        if context.last_action:
            # А. Проверка тегов (Fast -> Fast)
            # Если у глаголов есть общие теги стиля
            common_tags = set(verb.style_tags) & set(context.last_action.style_tags)
            if common_tags:
                synergy_mod += 0.1 # Бонус за поддержание стиля
                
            # Б. Явные требования (Synergies из VerbAtom)
            # Если глагол требует "staggered" и цель имеет этот тег
            reqs = verb.combo_potential.requires_prev_tags
            if reqs and not set(reqs).isdisjoint(context.active_tags):
                synergy_mod += 0.2 # Критический бонус комбо
        
        details['synergy_mod'] = synergy_mod

        # === 4. MOMENTUM CHECK (Цена) ===
        # Финишеры требуют высокого импульса
        momentum_penalty = 0.0
        if verb.flow_phase == FlowPhase.FINISHER:
            if context.momentum < 70: # Порог (тоже вынести в конфиг)
                momentum_penalty = -0.25
                details['momentum_fail'] = True
        
        # === ИТОГ ===
        final_chance = base_chance + flow_mod + synergy_mod + momentum_penalty
        
        # Clamp (5% ... 95%)
        final_chance = max(0.05, min(0.95, final_chance))
        details['final_chance'] = round(final_chance, 2)
        
        is_success = random.random() < final_chance
        return is_success, details

    def apply_consequences(self, context: SceneContext, verb: VerbAtom, success: bool):
        """Обновляет контекст сцены после действия"""
        if success:
            # Успешные действия разгоняют импульс
            context.momentum += verb.momentum_delta
            # Финишеры сбрасывают напряжение
            if verb.flow_phase == FlowPhase.FINISHER:
                context.momentum = 20 # Reset but keep some tension
        else:
            # Провалы сбивают темп
            context.momentum = max(0, context.momentum - 10)
