# src/data/templates_roles.py

from typing import List
import uuid
from src.models.ecs.ontology_chronicle import NarrativeRole
from src.models.ecs.ontology_schemas import SemanticVector
from src.models.ecs.taxonomy import SemanticTag

def get_common_roles() -> List[NarrativeRole]:
    """
    Возвращает библиотеку ролей для использования в EventArchetypes и NarrativeArcs.
    
    query_vector здесь определяет 'Идеальный Профиль' кандидата.
    CastingEngine будет искать сущности, чей cached_vector близок к этому.
    """
    roles: List[NarrativeRole] = []
    
    # =========================================================================
    # A. AGENTS (Действующие лица)
    # Сущности, обладающие волей (или псевдо-волей).
    # =========================================================================

    # 1. АГРЕССОР (Воин, Бандит, Монстр)
    roles.append(NarrativeRole(
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"role_aggressor")),
        description="An entity initiating violence or conflict.",
        # Ищем сильного (Vitality) и агрессивного/доминирующего (Social < 0 или > 0 в зависимости от трактовки, 
        # но обычно для врага берем высокий Material как 'Вооруженность')
        query_vector=SemanticVector(vitality=0.8, material=0.5, social=-0.2),
        required_tags=[SemanticTag.ACT_MAT_IMPACT] # Обязан уметь наносить урон
    ))
    
    # 2. ЗАЩИТНИК / ЖЕРТВА (Танк, Гражданский)
    roles.append(NarrativeRole(
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"role_defender")),
        description="An entity attempting to survive violence or protect others.",
        # Высокая Vitality (Выживаемость), возможно Social (Связи/Семья, которую защищает)
        query_vector=SemanticVector(vitality=0.6, social=0.3),
        required_tags=[SemanticTag.PROP_LIVING] # Обычно это живое существо
    ))
    
    # 3. ПОСТАВЩИК (Торговец, Крафтер)
    roles.append(NarrativeRole(
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"role_provider")),
        description="An entity possessing resources to share or trade.",
        # Высокий Material (Богатство), Позитивный Social (Договороспособность)
        query_vector=SemanticVector(material=0.8, social=0.5),
        required_tags=[SemanticTag.ACT_MAT_TRADE]
    ))
    
    # 4. ВЛИЯТЕЛЬНАЯ ФИГУРА (Король, Мэр, Капитан)
    roles.append(NarrativeRole(
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"role_influencer")),
        description="An entity exerting social pressure, authority, or charisma.",
        # Доминантный Social, высокий Cognitive (Стратегия/Знания)
        query_vector=SemanticVector(social=0.9, cognitive=0.4),
        required_tags=[SemanticTag.ACT_SOC_COMMAND] # Или OPPRESS, если тиран
    ))
    
    # 5. СЛЕДОВАТЕЛЬ (Детектив, Ученый)
    roles.append(NarrativeRole(
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"role_investigator")),
        description="An entity actively seeking information and analyzing environment.",
        # Высокий Cognitive (Интеллект), средняя Vitality (Активность)
        query_vector=SemanticVector(cognitive=0.8, vitality=0.3),
        required_tags=[SemanticTag.ACT_VIT_SENSE] # Должны быть чувства/сенсоры
    ))
    
    # 6. ИСТОЧНИК (Свидетель, Информатор - Агент)
    # *Отличие от role_info_source (предмета)*: Это существо, с которым можно говорить.
    roles.append(NarrativeRole(
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"role_source")),
        description="An entity containing hidden information that can be revealed.",
        # Высокий Cognitive (Знает секрет)
        query_vector=SemanticVector(cognitive=0.7),
        required_tags=[SemanticTag.PROP_SENTIENT] # Должен быть разумным
    ))

    # 7. ПУТЕШЕСТВЕННИК (Курьер, Беглец)
    roles.append(NarrativeRole(
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"role_traveler")),
        description="An entity moving through the environment over long distances.",
        # Vitality (Выносливость), Material (Снаряжение)
        query_vector=SemanticVector(vitality=0.7, material=0.4),
        required_tags=[SemanticTag.PROP_MOBILE]
    ))
    
    # 8. ЛАЗУТЧИК (Вор, Шпион)
    roles.append(NarrativeRole(
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"role_infiltrator")),
        description="An entity attempting to move undetected to bypass defenses.",
        # Cognitive (Хитрость), Vitality (Ловкость), Low Social (Скрытность/Маргинал)
        query_vector=SemanticVector(cognitive=0.6, vitality=0.5, social=-0.4),
        required_tags=[
            SemanticTag.PROP_MOBILE,
            SemanticTag.ACT_SOC_STEALTH
        ] 
    ))

    # =========================================================================
    # B. OBJECTS (Предметы / Инструменты)
    # Не обладают волей, но имеют физические свойства и ценность.
    # =========================================================================

    # 9. СОКРОВИЩЕ / МАКГАФФИН (Ключ, Артефакт, Документы)
    roles.append(NarrativeRole(
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"role_treasure")),
        description="A portable object of high material or cognitive value.",
        # Очень высокий Material (Золото) или Cognitive (Данные)
        # Ставим микс, чтобы ловило и то, и другое.
        query_vector=SemanticVector(material=0.7, cognitive=0.7),
        required_tags=[SemanticTag.PROP_ITEM, SemanticTag.PROP_VALUABLE]
    ))

    # 10. ИНСТРУМЕНТ / ОРУЖИЕ (Меч, Отмычка, Бомба)
    roles.append(NarrativeRole(
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"role_tool")),
        description="An object used to inflict damage or overcome obstacles.",
        # Чистый Material (Прочность/Острота)
        query_vector=SemanticVector(material=0.8, vitality=0.0),
        required_tags=[SemanticTag.PROP_ITEM, SemanticTag.ACT_MAT_IMPACT]
    ))

    # 11. НОСИТЕЛЬ ИНФОРМАЦИИ (Книга, Терминал, Стела)
    # *Отличие от role_source*: Это предмет.
    roles.append(NarrativeRole(
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"role_info_source")),
        description="An inanimate object containing legible information.",
        # Чистый Cognitive
        query_vector=SemanticVector(cognitive=0.9),
        required_tags=[SemanticTag.ACT_INFO_SHARE] # "Readable"
    ))

    # =========================================================================
    # C. LOCATIONS (Места как Роли)
    # Узлы топологии, выступающие целями или декорациями.
    # =========================================================================

    # 12. ПУНКТ НАЗНАЧЕНИЯ (Город, База, Выход)
    roles.append(NarrativeRole(
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"role_destination")),
        description="A location that serves as the goal of a journey.",
        # Social (Безопасность/Цивилизация) или Material (Укрытие)
        query_vector=SemanticVector(social=0.5, material=0.5),
        required_tags=[SemanticTag.PROP_CONTAINER] # Это локация
    ))

    # 13. ОПАСНАЯ ЗОНА (Болото, Радиация, Минное поле)
    roles.append(NarrativeRole(
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"role_hazard_zone")),
        description="A location with environmental dangers hindering progress.",
        # Отрицательная Vitality (Убивает), Высокий Material (Сложный ландшафт)
        query_vector=SemanticVector(vitality=-0.8, material=0.6),
        required_tags=[SemanticTag.CTX_EXTREME_PRESSURE] # Давление среды
    ))

    return roles
