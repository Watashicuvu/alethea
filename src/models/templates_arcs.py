# src/data/templates_arcs.py
import uuid
from typing import List
from src.models.ecs.ontology_chronicle import (
    NarrativeArcTemplate, NarrativeRole, EventNodeTemplate
)
from src.models.ecs.ontology_schemas import SemanticVector
from src.models.ecs.taxonomy import SemanticTag

def get_standard_arc_templates() -> List[NarrativeArcTemplate]:
    """
    Возвращает библиотеку Сюжетных Арок с полной конфигурацией физики и кастинга.
    """
    arcs: List[NarrativeArcTemplate] = []

    # =========================================================================
    # 1. THE REVENGE CYCLE (Граф Монте-Кристо)
    # =========================================================================
    
    role_avenger = NarrativeRole(
        id="role_hero_avenger", 
        description="A character who suffers a great loss and seeks retribution.",
        # Ищем того, кто выжил (High Vitality), но потерял статус (Low Social)
        query_vector=SemanticVector(vitality=0.7, social=-0.5), 
        required_tags=[SemanticTag.PROP_LIVING]
    )
    
    role_villain = NarrativeRole(
        id="role_villain_nemesis", 
        description="A powerful entity responsible for the hero's loss.",
        # Ищем власть имущего
        query_vector=SemanticVector(social=0.9, material=0.8), 
        required_tags=[SemanticTag.PROP_SENTIENT]
    )

    arc_revenge = NarrativeArcTemplate(
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"arc_classic_revenge")),
        name="The Cycle of Retribution",
        description="A protagonist suffers a personal tragedy caused by an antagonist and dedicates their life to destroying them.",
        # VECTOR:
        # Vitality (0.8): Высокая интенсивность жизни/смерти, физический конфликт.
        # Social (-0.7): Месть — это анти-социальное действие, разрушение связей, статус изгоя.
        # Cognitive (0.3): Требует планирования, но движима эмоциями.
        # Material (0.1): Ресурсы вторичны.
        global_vector=SemanticVector(vitality=0.8, social=-0.7, cognitive=0.3, material=0.1),
        
        cast=[role_avenger, role_villain],
        
        sequence=[
            # STEP 1: Inciting Incident (Trauma)
            # Используем физический конфликт, где Злодей бьет Героя
            EventNodeTemplate(
                name='Inciting',
                id="evt_arch_conflict_physical",
                #archetype_id="evt_arch_conflict_physical", 
                description="The Villain causes significant harm to the Hero.",
                participating_role_ids = ["role_aggressor", "role_defender"],
                # role_mapping={
                #     "role_aggressor": "role_villain_nemesis",
                #     "role_defender": "role_hero_avenger"
                # },
                # Драматичное событие, меняющее статус кво
                step_vector=SemanticVector(vitality=0.5, social=-0.8) 
            ),
            
            # STEP 2: The Low Point (Exile / Escape)
            # Герой бежит в изгнание
            EventNodeTemplate(
                name='Defeating',
                id="evt_arch_spatial_transition",
                description="The Hero is forced to flee to survive.",
                #archetype_id="evt_arch_spatial_transition",
                participating_role_ids = ["role_traveler", "role_origin", "role_destination"],
                # #role_mapping={
                #     "role_traveler": "role_hero_avenger",
                #     "role_origin": "role_villain_nemesis", # Убегает ОТ злодея (метафорически или буквально)
                #     # "role_destination" оставим пустым или назначим Wilds динамически
                # },
                step_vector=SemanticVector(vitality=0.6, social=-0.5)
            ),
            
            # STEP 3: Acquisition of Power (Discovery)
            # Герой находит способ победить (Секрет / Оружие)
            EventNodeTemplate(
                name="Empowerment",
                id="evt_arch_info_discovery",
                description="The Hero uncovers a secret weakness or weapon.",
                #archetype_id="evt_arch_info_discovery",
                participating_role_ids = ["role_investigator", "role_source"],
                #role_mapping={
                    #"role_investigator": "role_hero_avenger",
                    # Источником может быть что угодно, найденное в мире
                    # "role_source" будет назначен динамически DirectorSystem
                #},
                step_vector=SemanticVector(cognitive=0.8, material=0.5)
            ),
            
            # STEP 4: Climax (The Duel)
            # Финальная битва
            EventNodeTemplate(
                name='Climax Duel',
                id="evt_arch_conflict_physical",
                description="The Hero confronts the Villain in a final decisive battle.",
                #archetype_id="evt_arch_conflict_physical",
                participating_role_ids = ["role_aggressor", "role_defender"],
                #role_mapping={
                #     "role_aggressor": "role_hero_avenger", # Теперь Герой атакует
                #     "role_defender": "role_villain_nemesis"
                # },
                # Максимальное напряжение
                step_vector=SemanticVector(vitality=1.0, social=1.0) 
            )
        ]
    )
    arcs.append(arc_revenge)

    # =========================================================================
    # 2. THE HEIST (Ограбление)
    # =========================================================================
    
    role_thief = NarrativeRole(
        id="role_mastermind",
        description="A skilled individual planning a high-stakes acquisition.",
        # Умный (Cognitive) и Ловкий (Vitality)
        query_vector=SemanticVector(cognitive=0.8, vitality=0.6),
        required_tags=[SemanticTag.PROP_SENTIENT]
    )
    
    role_mark = NarrativeRole(
        id="role_target_item", 
        description="A valuable object heavily guarded.",
        # Ценный предмет
        query_vector=SemanticVector(material=0.9, cognitive=0.5), 
        required_tags=[SemanticTag.PROP_ITEM, SemanticTag.PROP_VALUABLE]
    )
    
    arc_heist = NarrativeArcTemplate(
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"arc_grand_heist")),
        name="The Grand Heist",
        description="A calculated operation to retrieve a target from a secured location.",
        # VECTOR:
        # Material (0.9): Цель — материальное благо (лут).
        # Cognitive (0.8): Ключевое — это план, хитрость, навыки.
        # Social (-0.5): Криминал, действие против закона/общества.
        # Vitality (0.3): Нужна ловкость, но прямого боя стараются избегать.
        global_vector=SemanticVector(material=0.9, cognitive=0.8, social=-0.5, vitality=0.3),
        
        cast=[role_thief, role_mark],
        
        sequence=[
            # STEP 1: Recon (Discovery)
            EventNodeTemplate(
                name = 'Recon',
                id="evt_arch_info_discovery",
                description="The Mastermind studies the target location.",
                #archetype_id="evt_arch_info_discovery",
                participating_role_ids = ["role_investigator", "role_source"],
                #role_mapping={
                #     "role_investigator": "role_mastermind",
                #     "role_source": "role_target_item" # Изучаем сам предмет или его охрану
                # },
                step_vector=SemanticVector(cognitive=0.7)
            ),
            
            # STEP 2: Infiltration (Stealth)
            EventNodeTemplate(
                name = 'Infiltration',
                id="step_infiltration",
                description="The Mastermind sneaks towards the target.",
                #archetype_id="evt_arch_stealth",
                participating_role_ids = ["role_infiltrator", "role_observer"],
                #role_mapping={
                #     "role_infiltrator": "role_mastermind",
                #     # "role_observer": Guard (динамически назначается из окружения)
                # },
                step_vector=SemanticVector(cognitive=0.8, social=-0.5) # Избегание контактов
            ),
            
            # STEP 3: The Grab (Interaction/Trade mechanics)
            # Технически это "Обмен" (без оплаты) или спец-событие "Take Item"
            EventNodeTemplate(
                name='acquisition',
                id="evt_arch_exchange_resource",
                description="The Mastermind steals the Target.",
                #archetype_id="evt_arch_exchange_resource", # Используем механику трансфера
                participating_role_ids = ["role_receiver", "role_provider"],
                #role_mapping={
                #     "role_receiver": "role_mastermind",
                #     "role_provider": "role_target_item" # Предмет "отдает" себя
                # },
                step_vector=SemanticVector(material=0.5, social=-1.0) # Кража = плохой social
            ),
            
            # STEP 4: The Escape (Chase)
            EventNodeTemplate(
                name='Escape',
                id="evt_arch_spatial_transition",
                description="The Mastermind flees with the prize.",
                #archetype_id="evt_arch_spatial_transition", # Быстрое перемещение
                participating_role_ids = ["role_traveler", "role_origin"],
                #role_mapping={
                #     "role_traveler": "role_mastermind",
                #     # "role_origin": Location of theft
                # },
                step_vector=SemanticVector(vitality=0.8, material=0.2)
            )
        ]
    )
    arcs.append(arc_heist)

    # =========================================================================
    # 3. THE MYSTERY (Детектив)
    # =========================================================================
    
    role_detective = NarrativeRole(
        id="role_detective",
        description="An investigator solving a crime.",
        query_vector=SemanticVector(cognitive=0.9, vitality=0.3),
        required_tags=[SemanticTag.ACT_VIT_SENSE]
    )
    
    role_suspect = NarrativeRole(
        id="role_hidden_culprit",
        description="The perpetrator hiding their guilt.",
        query_vector=SemanticVector(social=-0.5, cognitive=0.6), # Скрытный и умный
        required_tags=[SemanticTag.ACT_INFO_LIE]
    )
    
    role_witness = NarrativeRole(
        id="role_witness",
        description="Someone who saw something.",
        query_vector=SemanticVector(vitality=0.4), # Обычный NPC
        required_tags=[SemanticTag.ACT_INFO_SHARE]
    )

    arc_mystery = NarrativeArcTemplate(
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"arc_mystery_investigation")),
        name="The Whodunit",
        description="A crime investigation focusing on uncovering the truth.",
        # VECTOR:
        # Cognitive (0.9): Чистый интеллект, анализ, истина.
        # Social (0.4): Взаимодействие со свидетелями, понимание мотивов.
        # Material (0.2): Улики важны, но вторичны по сравнению с выводами.
        # Vitality (0.1): Обычно "кабинетный" жанр, если не нуар-экшен.
        global_vector=SemanticVector(cognitive=0.9, social=0.4, material=0.2, vitality=0.1),
        
        cast=[role_detective, role_suspect, role_witness],
        
        sequence=[
            # STEP 1: Discovery (Finding Body/Clue)
            EventNodeTemplate(
                name='Crime discovery',
                id="evt_arch_info_discovery",
                description="The Detective analyzes the crime scene.",
                #archetype_id="evt_arch_info_discovery",
                participating_role_ids = ["role_investigator", "role_source"],
                #role_mapping={
                #     "role_investigator": "role_detective",
                #     # "role_source": Clue Object (Dynamic)
                # },
                step_vector=SemanticVector(cognitive=0.6, vitality=-0.2) # Memento mori
            ),
            
            # STEP 2: Interrogation (Social + Info)
            # Используем Info Discovery, но с живым источником
            EventNodeTemplate(
                name = 'Interrogation',
                id="evt_arch_info_discovery",
                description="The Detective questions the Witness.",
                #archetype_id="evt_arch_info_discovery", 
                participating_role_ids = ["role_investigator", "role_source"],
                #role_mapping={
                #     "role_investigator": "role_detective",
                #     "role_source": "role_witness"
                # },
                step_vector=SemanticVector(social=0.5, cognitive=0.5)
            ),
            
            # STEP 3: Accusation (Social Confrontation)
            EventNodeTemplate(
                name = 'Accusation',
                id="evt_arch_conflict_social",
                description="The Detective exposes the Culprit.",
                #archetype_id="evt_arch_conflict_social",
                participating_role_ids = ["role_influencer", "role_target"],
                #role_mapping={
                #     "role_influencer": "role_detective", # Давит авторитетом/фактами
                #     "role_target": "role_hidden_culprit"
                # },
                step_vector=SemanticVector(social=1.0, cognitive=0.8)
            ),
            
            # STEP 4: Arrest (Physical)
            EventNodeTemplate(
                name='Arrest',
                id="evt_arch_conflict_physical",
                description="The Culprit is subdued.",
                #archetype_id="evt_arch_conflict_physical",
                participating_role_ids = ["role_aggressor", "role_defender"],
                #role_mapping={
                #     "role_aggressor": "role_detective", # Применяет силу закона
                #     "role_defender": "role_hidden_culprit"
                # },
                step_vector=SemanticVector(vitality=0.7, social=0.5)
            )
        ]
    )
    arcs.append(arc_mystery)

    # =========================================================================
    # 4. THE SIEGE (Оборона)
    # =========================================================================

    role_commander = NarrativeRole(
        id="role_commander",
        description="Leader of the defense.",
        query_vector=SemanticVector(social=0.8, material=0.6), # Authority + Resources
        required_tags=[SemanticTag.ACT_SOC_COMMAND]
    )
    
    role_horde = NarrativeRole(
        id="role_invading_force",
        description="Massive attacking force.",
        query_vector=SemanticVector(vitality=0.9, cognitive=-0.5), # Brute force
        required_tags=[SemanticTag.ACT_MAT_IMPACT]
    )
    
    role_stronghold = NarrativeRole(
        id="role_defended_location",
        description="Strategic location.",
        query_vector=SemanticVector(material=0.9), # High structural integrity
        required_tags=[SemanticTag.PROP_CONTAINER]
    )

    arc_siege = NarrativeArcTemplate(
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"arc_siege_defense")),
        name="The Siege",
        description="Holding a location against waves of enemies.",
        # VECTOR:
        # Material (0.8): Стены, припасы, крепость.
        # Vitality (0.9): Борьба за жизнь, физическая выносливость.
        # Social (0.5): Дисциплина, командование, боевой дух.
        # Cognitive (-0.2): Прямое столкновение, "сила есть - ума не надо" (для Орды), хотя тактика важна.
        global_vector=SemanticVector(material=0.8, vitality=0.9, social=0.5, cognitive=0.0),
        
        cast=[role_commander, role_horde, role_stronghold],
        
        sequence=[
            # STEP 1: Fortification (Preparation)
            # Используем механику крафта/улучшения
            # Поскольку нет отдельного evt_craft, используем Resource Exchange (тратим ресурсы -> получаем защиту)
            # Или просто abstract event, но лучше привязать к evt_arch_exchange_resource (Trade with environment)
            EventNodeTemplate(
                name='fortification',
                id="evt_arch_exchange_resource",
                description="The Commander reinforces the Stronghold.",
                # archetype_id="evt_arch_exchange_resource", 
                participating_role_ids = ["role_provider", "role_receiver"],
                #role_mapping={
                #     "role_provider": "role_commander", # Тратит ресурсы
                #     "role_receiver": "role_defended_location" # Локация получает апгрейд
                # },
                step_vector=SemanticVector(material=0.7, vitality=0.4)
            ),
            
            # STEP 2: Assault (Physical Conflict)
            EventNodeTemplate(
                name='assault',
                id="evt_arch_conflict_physical",
                description="The Horde attacks the Stronghold.",
                # archetype_id="evt_arch_conflict_physical",
                participating_role_ids = ["role_aggressor", "role_defender"],
                #role_mapping={
                #     "role_aggressor": "role_invading_force",
                #     "role_defender": "role_defended_location" # Стены принимают урон
                # },
                step_vector=SemanticVector(vitality=0.9, material=-0.5) # Разрушение
            ),
            
            # STEP 3: Final Stand (Physical Conflict)
            EventNodeTemplate(
                name='final stand',
                id="evt_arch_conflict_physical",
                description="The Commander fights the Horde leaders.",
                #archetype_id="evt_arch_conflict_physical",
                participating_role_ids = ["role_aggressor", "role_defender"],
                #role_mapping={
                #     "role_aggressor": "role_invading_force",
                #     "role_defender": "role_commander"
                # },
                step_vector=SemanticVector(vitality=1.0, social=0.5) # Heroism
            )
        ]
    )
    arcs.append(arc_siege)

    # =========================================================================
    # 5. THE REVOLUTION (Восстание)
    # =========================================================================

    role_rebel = NarrativeRole(
        id="role_rebel_leader",
        description="Revolutionary leader.",
        query_vector=SemanticVector(social=0.7, cognitive=0.6), # Charisma + Plan
        required_tags=[SemanticTag.ACT_SOC_RECRUIT]
    )
    
    role_tyrant = NarrativeRole(
        id="role_oppressor",
        description="Tyrannical ruler.",
        query_vector=SemanticVector(social=0.9, vitality=0.5), # Power + Force
        required_tags=[SemanticTag.ACT_SOC_OPPRESS]
    )

    arc_revolution = NarrativeArcTemplate(
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"arc_political_revolution")),
        name="The Revolution",
        description="Overthrowing a regime.",
        # VECTOR:
        # Material (0.8): Стены, припасы, крепость.
        # Vitality (0.9): Борьба за жизнь, физическая выносливость.
        # Social (0.5): Дисциплина, командование, боевой дух.
        # Cognitive (-0.2): Прямое столкновение, "сила есть - ума не надо" (для Орды), хотя тактика важна.
        global_vector=SemanticVector(material=0.8, vitality=0.9, social=0.5, cognitive=0.0),
        
        cast=[role_rebel, role_tyrant],
        
        sequence=[
            # STEP 1: Oppression (Social Conflict)
            EventNodeTemplate(
                name='oppression',
                id="evt_arch_conflict_social",
                description="The Tyrant oppresses the people.",
                #archetype_id="evt_arch_conflict_social",
                participating_role_ids = ["role_influencer", "role_target"],
                #role_mapping={
                #     "role_influencer": "role_oppressor",
                #     "role_target": "role_rebel_leader" # Или народ (абстрактно)
                # },
                step_vector=SemanticVector(social=-0.8, vitality=-0.2)
            ),
            
            # STEP 2: Sabotage (Stealth / Attack)
            EventNodeTemplate(
                name='Sabotage',
                id="evt_arch_stealth",
                description="The Rebel strikes at the Tyrant's resources.",
                #archetype_id="evt_arch_stealth", # Или Conflict
                participating_role_ids = ["role_infiltrator", "role_observer"],
                #role_mapping={
                #     "role_infiltrator": "role_rebel_leader",
                #     # Observer is dynamic
                # },
                step_vector=SemanticVector(material=-0.5, social=0.4) # Урон режиму
            ),
            
            # STEP 3: The Coup (Social Confrontation)
            EventNodeTemplate(
                name='Coup',
                id="evt_arch_conflict_social",
                description="The Rebel challenges the Tyrant's authority.",
                #archetype_id="evt_arch_conflict_social",
                participating_role_ids = ["role_influencer", "role_target"],
                #role_mapping={
                #     "role_influencer": "role_rebel_leader",
                #     "role_target": "role_oppressor"
                # },
                step_vector=SemanticVector(social=1.0, cognitive=0.5) # Revolution!
            )
        ]
    )
    arcs.append(arc_revolution)

    # ... (Предыдущие импорты должны быть сохранены)
# Добавляем этот код перед return arcs

    # =========================================================================
    # 6. THE RISE AND FALL (Трагедия / Карьера / Коррупция)
    # =========================================================================
    # Подходит для: Aristotelian Tragedy, Stagnation (как фаза), Whistleblower Scandal (со стороны злодея)

    role_climber = NarrativeRole(
        id="role_climber",
        description="An ambitious individual seeking higher status or power.",
        # Высокий Drive (Vitality) и Agency (Cognitive), но может быть низкий Social в начале
        query_vector=SemanticVector(vitality=0.7, cognitive=0.6),
        required_tags=[SemanticTag.ACT_COG_PLAN] # Должен уметь планировать
    )

    role_prize = NarrativeRole(
        id="role_status_source",
        description="The source of power, status, or wealth.",
        # Это может быть Трон, Артефакт или Должность.
        query_vector=SemanticVector(social=0.9, material=0.8),
        required_tags=[SemanticTag.PROP_VALUABLE]
    )
    
    # Опциональная роль: Тот, кто сбрасывает героя (Судьба, Соперник, Разоблачитель)
    role_nemesis = NarrativeRole(
        id="role_nemesis",
        description="The agent of the climber's downfall.",
        query_vector=SemanticVector(social=0.5, cognitive=0.7),
        required_tags=[SemanticTag.ACT_SOC_OPPRESS]
    )

    arc_rise_fall = NarrativeArcTemplate(
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS, "arc_rise_and_fall")),
        name="The Rise and Fall",
        description="The ascent to power followed by a catastrophic loss due to hubris or external forces.",
        # VECTOR:
        # Social (0.9): Все вертится вокруг статуса и иерархии.
        # Cognitive (0.5): Ошибки суждения (Hubris) играют ключевую роль.
        # Material (0.6): Часто связано с накоплением ресурсов.
        # Vitality (0.2): Физическое выживание вторично до финала.
        global_vector=SemanticVector(social=0.9, cognitive=0.5, material=0.6, vitality=0.2),
        
        cast=[role_climber, role_prize, role_nemesis],
        
        sequence=[
            # STEP 1: Ascension (Social/Material Gain)
            # Герой получает власть (покупка, назначение, захват)
            EventNodeTemplate(
                name='Ascension',
                id="evt_arch_exchange_resource", # Или Social Rank Up, если есть такой атом
                description="The Climber acquires the Prize/Status.",
                participating_role_ids=["role_receiver", "role_provider"],
                # role_mapping={
                #     "role_receiver": "role_climber",
                #     "role_provider": "role_status_source"
                # },
                step_vector=SemanticVector(social=0.8, material=0.5)
            ),

            # STEP 2: Hubris / Abuse (Social Conflict)
            # Герой злоупотребляет силой или совершает ошибку
            EventNodeTemplate(
                name='Hubris',
                id="evt_arch_conflict_social",
                description="The Climber misuses their power, creating enemies.",
                participating_role_ids=["role_influencer", "role_target"],
                # role_mapping={
                #     "role_influencer": "role_climber",
                #     "role_target": "role_nemesis" # Создает врага
                # },
                step_vector=SemanticVector(social=-0.5, cognitive=-0.5) # Ошибка суждения
            ),

            # STEP 3: The Turn (Discovery/Loss)
            # Разоблачение, потеря ресурсов или предательство
            EventNodeTemplate(
                name='Peripeteia',
                id="evt_arch_info_discovery", # Часто крах начинается с информации (компромат)
                description="A fatal weakness or scandal is revealed.",
                participating_role_ids=["role_investigator", "role_source"],
                # role_mapping={
                #     "role_investigator": "role_nemesis",
                #     "role_source": "role_climber" # Ищем грязь на героя
                # },
                step_vector=SemanticVector(social=-0.8, cognitive=0.7)
            ),

            # STEP 4: Collapse (Total Loss)
            # Финальное падение
            EventNodeTemplate(
                name='Catastrophe',
                id="evt_arch_conflict_physical", # Или Social Exile
                description="The Climber loses everything.",
                participating_role_ids=["role_aggressor", "role_defender"],
                # role_mapping={
                #     "role_aggressor": "role_nemesis",
                #     "role_defender": "role_climber"
                # },
                step_vector=SemanticVector(social=-1.0, material=-0.9) # Полный крах
            )
        ]
    )
    arcs.append(arc_rise_fall)

    # =========================================================================
    # 7. THE HERO'S JOURNEY (Экспедиция / Трансформация)
    # =========================================================================
    # Подходит для: Hero's Journey, Grassroots Movement (как путь лидера), Exploration

    role_seeker = NarrativeRole(
        id="role_seeker",
        description="An individual leaving their comfort zone to find something.",
        # Баланс векторов, потенциал к росту
        query_vector=SemanticVector(vitality=0.6, cognitive=0.5, social=0.4),
        required_tags=[SemanticTag.ACT_VIT_PURSUE] # Стремление
    )

    role_mentor = NarrativeRole(
        id="role_mentor",
        description="Possessor of knowledge or skills needed for the journey.",
        # Высокий Cognitive (мудрость)
        query_vector=SemanticVector(cognitive=0.8, social=0.6),
        required_tags=[SemanticTag.ACT_INFO_SHARE] # Учитель
    )
    
    role_threshold = NarrativeRole(
        id="role_unknown_world",
        description="A dangerous or unknown location/domain.",
        # Опасная среда
        query_vector=SemanticVector(vitality=-0.5, material=0.7), 
        required_tags=[SemanticTag.PROP_LOCATION]
    )

    arc_journey = NarrativeArcTemplate(
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS, "arc_quest_journey")),
        name="The Transformation Journey",
        description="A protagonist enters an unknown world, faces trials, and returns changed.",
        # VECTOR:
        # Vitality (0.7): Путешествие требует сил, выживания.
        # Cognitive (0.8): Это процесс обучения, открытия нового (Information Atom).
        # Social (0.3): Обычно это путь одиночки или малой группы.
        # Material (0.4): Сбор лута важен, но вторичен по сравнению с опытом.
        global_vector=SemanticVector(vitality=0.7, cognitive=0.8, social=0.3, material=0.4),
        
        cast=[role_seeker, role_mentor, role_threshold],
        
        sequence=[
            # STEP 1: The Call / Preparation (Social/Info)
            # Получение задания или навыка от Ментора
            EventNodeTemplate(
                name='Initiation',
                id="evt_arch_info_discovery", # Получение Lore/Skill
                description="The Seeker receives knowledge or a mission.",
                participating_role_ids=["role_investigator", "role_source"],
                # role_mapping={
                #     "role_investigator": "role_seeker",
                #     "role_source": "role_mentor"
                # },
                step_vector=SemanticVector(cognitive=0.6, social=0.5)
            ),

            # STEP 2: Crossing the Threshold (Movement)
            # Вход в опасную зону
            EventNodeTemplate(
                name='Departure',
                id="evt_arch_spatial_transition",
                description="The Seeker enters the Unknown World.",
                participating_role_ids=["role_traveler", "role_destination"],
                # role_mapping={
                #     "role_traveler": "role_seeker",
                #     "role_destination": "role_threshold"
                # },
                step_vector=SemanticVector(vitality=0.5, material=0.3) # Исследование
            ),

            # STEP 3: The Ordeal (Challenge)
            # Столкновение с опасностью среды или стражем
            EventNodeTemplate(
                name='The Ordeal',
                id="evt_arch_conflict_physical",
                description="The Seeker faces a mortal challenge.",
                participating_role_ids=["role_defender", "role_aggressor"],
                # role_mapping={
                #     "role_defender": "role_seeker",
                #     "role_aggressor": "role_threshold" # Среда атакует (или монстр в ней)
                # },
                step_vector=SemanticVector(vitality=0.9, cognitive=0.7) # Нужно выжить и понять паттерн
            ),

            # STEP 4: Return with Elixir (Transformation)
            # Герой возвращается, но его вектор изменился (levelup)
            EventNodeTemplate(
                name='Return',
                id="evt_arch_spatial_transition",
                description="The Seeker returns, possessing new power.",
                participating_role_ids=["role_traveler", "role_origin"],
                # role_mapping={
                #     "role_traveler": "role_seeker",
                #     # "role_origin": Unknown World
                # },
                step_vector=SemanticVector(social=0.7, cognitive=1.0) # Признание и мудрость
            )
        ]
    )
    arcs.append(arc_journey)

    return arcs
