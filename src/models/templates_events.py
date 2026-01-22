# src/data/templates_events.py

from typing import List
import uuid
from src.models.ecs.ontology_chronicle import EventNodeTemplate
from src.models.ecs.ontology_schemas import SemanticVector, Sphere
from src.models.ecs.taxonomy import SemanticTag


class EventArchetype(EventNodeTemplate):
    """
    Расширенный шаблон события, включающий 'Физику' последствий.
    Используется движком для классификации входящих действий.
    """
    # Примерные последствия (для AI, чтобы он знал, к чему это ведет)
    # "vitality_loss", "info_gain", "possession_transfer"
    primary_consequence_tags: List[str] 
    
    # Сфера, в которой происходит основное действие
    dominant_sphere: Sphere


# ==============================================================================
# 1. EVENT ARCHETYPES (Физика событий)
# ==============================================================================

def get_standard_event_archetypes() -> List[EventArchetype]:
    """
    Возвращает набор архетипов событий.
    Вектора step_vector настроены вручную для отражения 'физического смысла' события.
    Вектора поиска (step_vector) оставлены пустыми для генерации через SBERT.
    """
    archetypes: List[EventArchetype] = []

    # -------------------------------------------------------------------------
    # 1. PHYSICAL CONFLICT (Насилие / Бой)
    # Механика: Прямое столкновение, наносящее урон Vitality.
    # -------------------------------------------------------------------------
    evt_conflict = EventArchetype(
        name = "scuffle",
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"evt_arch_conflict_physical")),
        description="A violent interaction where entities exchange physical damage.",
        
        # ФИЗИКА:
        # Vitality: Высокая (кровь, боль, адреналин)
        # Social: Отрицательная (разрыв связей, агрессия)
        # Material: Средняя (использование оружия, разрушение окружения)
        step_vector=SemanticVector(vitality=0.9, social=-0.5, material=0.4),
        
        dominant_sphere=Sphere.VITALITY,
        
        # ПОСЛЕДСТВИЯ (Tags):
        primary_consequence_tags=[
            SemanticTag.STATE_BIO_CRITICAL,      # Ранение
            SemanticTag.STATE_BIO_DEAD,          # Смерть
            SemanticTag.STATE_STRUCTURAL_FAILURE # Разрушение брони/стен
        ],
        
        # РОЛИ (Локальные ID для этого типа события):
        participating_role_ids=["role_aggressor", "role_defender"]
    )
    # Инициализируем пустой вектор поиска
    #evt_conflict.step_vector = SemanticVector() 
    archetypes.append(evt_conflict)

    # -------------------------------------------------------------------------
    # 2. SOCIAL EXCHANGE (Торговля / Договор)
    # Механика: Мирный обмен ресурсами или информацией.
    # -------------------------------------------------------------------------
    evt_trade = EventArchetype(
        name='Exchange',
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"evt_arch_exchange_resource")),
        description="A voluntary transfer of resources, items, or services between entities.",
        
        # ФИЗИКА:
        # Material: Позитивная (перемещение благ)
        # Social: Позитивная (укрепление связей, сделка)
        step_vector=SemanticVector(material=0.6, social=0.4),
        
        dominant_sphere=Sphere.MATERIAL,
        
        primary_consequence_tags=[
            SemanticTag.ACT_MAT_TRADE,     # Сам факт торговли
            # SemanticTag.RELATION_ALLY (MISSING: Нет тега для улучшения отношений)
        ],
        
        participating_role_ids=["role_provider", "role_receiver"]
    )
    #evt_trade.step_vector = SemanticVector()
    archetypes.append(evt_trade)

    # -------------------------------------------------------------------------
    # 3. INFORMATION DISCOVERY (Расследование / Озарение)
    # Механика: Получение скрытых данных.
    # -------------------------------------------------------------------------
    evt_discovery = EventArchetype(
        name='Information gain',
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"evt_arch_info_discovery")),
        description="The acquisition of previously hidden or unknown information through observation or analysis.",
        
        # ФИЗИКА:
        # Cognitive: Очень высокая (инсайт, знание)
        # Vitality: Низкая (обычно безопасно)
        step_vector=SemanticVector(cognitive=0.9, vitality=0.1),
        
        dominant_sphere=Sphere.COGNITIVE,
        
        primary_consequence_tags=[
            SemanticTag.ACT_INFO_LEARN,    # Изучение
            SemanticTag.CTX_INFO_RESEARCH, # Контекст исследования
            SemanticTag.STATE_INFO_MYTH    # (Возможно) Развенчание мифа
        ],
        
        participating_role_ids=["role_investigator", "role_source"]
    )
    #evt_discovery.step_vector = SemanticVector()
    archetypes.append(evt_discovery)

    # -------------------------------------------------------------------------
    # 4. SPATIAL TRANSITION (Погоня / Путешествие)
    # Механика: Интенсивное перемещение, требующее выносливости.
    # -------------------------------------------------------------------------
    evt_chase = EventArchetype(
        name='Traversal',
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"evt_arch_spatial_transition")),
        description="Rapid movement across topology nodes, often under pressure.",
        
        # ФИЗИКА:
        # Vitality: Высокая (бег, карабканье)
        # Material: Взаимодействие с ландшафтом
        step_vector=SemanticVector(vitality=0.7, material=0.3),
        
        dominant_sphere=Sphere.MATERIAL, # Перемещение в пространстве
        
        primary_consequence_tags=[
            SemanticTag.ACT_VIT_PURSUE,   # Преследование
            SemanticTag.ACT_TRAV_JUMP,    # Преодоление препятствий
            SemanticTag.STATE_BIO_LETHARGIC # Усталость (после)
        ],
        
        participating_role_ids=["role_traveler", "role_origin", "role_destination"]
    )
    #evt_chase.step_vector = SemanticVector()
    archetypes.append(evt_chase)

    # -------------------------------------------------------------------------
    # 5. SOCIAL CONFRONTATION (Запугивание / Дебаты)
    # Механика: Конфликт воли, не наносящий физ. урона, но меняющий иерархию.
    # -------------------------------------------------------------------------
    evt_debate = EventArchetype(
        name='scare tactic',
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"evt_arch_conflict_social")),
        description="A clash of wills, authority, or status intended to dominate or persuade without violence.",
        
        # ФИЗИКА:
        # Social: Экстремальная (давление, харизма)
        # Cognitive: Средняя (аргументация)
        step_vector=SemanticVector(social=0.9, cognitive=0.5),
        
        dominant_sphere=Sphere.SOCIAL,
        
        primary_consequence_tags=[
            SemanticTag.ACT_SOC_COMMAND,  # Попытка подчинить
            SemanticTag.ACT_SOC_OPPRESS,  # Давление
            # SemanticTag.STATE_MORALE_BROKEN (MISSING: Нужно добавить состояние морали)
            SemanticTag.STATE_COG_STUPOR  # Шок / Потеря дара речи
        ],
        
        participating_role_ids=["role_influencer", "role_target"]
    )
    #evt_debate.step_vector = SemanticVector()
    archetypes.append(evt_debate)

    # -------------------------------------------------------------------------
    # 6. STEALTH / INFILTRATION (Скрытность)
    # Механика: Действие с целью минимизировать Social/Vitality след.
    # -------------------------------------------------------------------------
    evt_stealth = EventArchetype(
        name='Stealth',
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"evt_arch_stealth")),
        description="Moving or acting while actively avoiding detection and social interaction.",
        
        # ФИЗИКА:
        # Social: Отрицательная (избегание контактов)
        # Cognitive: Высокая (планирование, внимание)
        step_vector=SemanticVector(social=-0.8, cognitive=0.6, vitality=0.2),
        
        dominant_sphere=Sphere.COGNITIVE, # Это "умное" действие
        
        primary_consequence_tags=[
            SemanticTag.ACT_VIT_SENSE,    # Прислушивание
            SemanticTag.ACT_SOC_STEALTH,
            SemanticTag.ACT_COG_PLAN      # Используем Планирование как замену
        ],
        
        participating_role_ids=["role_infiltrator", "role_observer"]
    )
    #evt_stealth.step_vector = SemanticVector()
    archetypes.append(evt_stealth)

    return archetypes
