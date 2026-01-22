from typing import List
import uuid
from src.models.ecs.data_schemas import InformationData # это сомнительное поле
from src.models.ecs.ontology_schemas import ComponentDefinition, SemanticVector, Sphere, EvolutionRule, LatentPotentialRule
from src.models.ecs.taxonomy import SemanticTag, DataKey


# ====== MATERIAL ==========

# --- Атом Целостности (Integrity) ---
integrity_atom = ComponentDefinition(
    id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"mat_integrity")),
    name="Structural Integrity",
    sphere=Sphere.MATERIAL,
    description="Resistance to physical decomposition or destruction.",
    base_vector=SemanticVector(material=0.7), 
    affordances={
        SemanticTag.ACT_MAT_HOLD_SHAPE, 
        SemanticTag.ACT_MAT_IMPACT,
    },
    evolution_rules=[
        EvolutionRule(
            condition_axis="material",
            operator="lt",
            threshold=0.2,
            effect_delta={SemanticTag.STATE_STRUCTURAL_FAILURE: 1.0} 
        )
    ],
    # Мостик в SOCIAL: Сломанная вещь теряет ценность (Scrap)
    latent_potential=[
        LatentPotentialRule(
            trigger_context=SemanticTag.CTX_INT_INDUSTRIAL,
            result_component_id=SemanticTag.STATE_SCRAP,
            probability=0.5
        )
    ]
)

# --- Атом Термики (Thermal State) ---
thermal_atom = ComponentDefinition(
    id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"mat_thermal")),
    name="Thermal State",
    sphere=Sphere.MATERIAL,
    description="The level of kinetic energy in particles.",
    base_vector=SemanticVector(material=0.5),
    affordances={SemanticTag.ACT_MAT_BURN, SemanticTag.ACT_MAT_FREEZE}, # "cook" удалены, так как их нет в таксономии
    evolution_rules=[
        EvolutionRule(
            condition_axis="material",
            operator="gt",
            threshold=0.9,
            effect_delta={SemanticTag.STATE_STRUCTURAL_WEAKNESS: 0.5}
        )
    ],
    latent_potential=[
        LatentPotentialRule(
            trigger_context=SemanticTag.CTX_INT_THERMAL_SOURCE,
            result_component_id=SemanticTag.ROLE_POWER_SOURCE,
            probability=1.0
        )
    ],
    default_data={DataKey.TEMPERATURE: 20.0}
)

# --- Атом Остроты (Acuity) ---
acuity_atom = ComponentDefinition(
    id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"mat_acuity")),
    name="Mechanical Acuity",
    sphere=Sphere.MATERIAL,
    description="Potential for mechanical penetration or separation.",
    base_vector=SemanticVector(material=0.8),
    affordances={SemanticTag.ACT_MAT_CUT, SemanticTag.ACT_MAT_IMPACT},
    # Мостик в VITALITY: Острое оружие может вызвать критическое состояние
    latent_potential=[
        LatentPotentialRule(
            trigger_context=SemanticTag.CTX_EXTREME_PRESSURE,
            result_component_id=SemanticTag.STATE_BIO_CRITICAL,
            probability=0.2
        )
    ]
)

# --- Атом Плотности (Density) ---
density_atom = ComponentDefinition(
    id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"mat_density")),
    name="Physical Density",
    sphere=Sphere.MATERIAL,
    description="The concentration of mass within a volume.",
    base_vector=SemanticVector(material=0.9),
    affordances={SemanticTag.ACT_MAT_CRUSH},
    evolution_rules=[
        EvolutionRule(
            condition_axis="material",
            operator="lt",
            threshold=0.1,
            effect_delta={SemanticTag.STATE_PHASE_ETHEREAL: 1.0}
        )
    ],
    default_data={DataKey.DENSITY: 1000.0, DataKey.MASS: 1.0}
)

# --- Атом Кинетики (Kinetics) ---
kinetics_atom = ComponentDefinition(
    id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"phys_kinetics")),
    name="Kinetic State",
    sphere=Sphere.MATERIAL,
    base_vector=SemanticVector(material=0.5),
    affordances={SemanticTag.ACT_MAT_IMPACT},
    evolution_rules=[
        EvolutionRule(
            condition_axis="material",
            operator="lt",
            threshold=0.01,
            effect_delta={SemanticTag.STATE_KIN_STATIC: 1.0}
        )
    ],
    default_data={DataKey.VELOCITY: [0.0, 0.0, 0.0]}
)

# --- Атом Проводимости (Conductivity) ---
conductivity_atom = ComponentDefinition(
    id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"phys_conductivity")),
    name="Energy Conductivity",
    sphere=Sphere.MATERIAL,
    base_vector=SemanticVector(material=0.4, cognitive=0.2),
    affordances={SemanticTag.ACT_MAT_CONDUCT},
    default_data={DataKey.RESISTANCE: 1.0}
)

# ECONOMY PART
 
# --- Атом Тленности (Perishability) ---
perishability_atom = ComponentDefinition(
    id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"mat_perishability")),
    name="Perishability",
    sphere=Sphere.MATERIAL,
    base_vector=SemanticVector(material=0.4, vitality=0.2),
    affordances={SemanticTag.ACT_MAT_SPOIL}, # Заменили "expire" и "storage"
    evolution_rules=[
        EvolutionRule(
            condition_axis="material",
            operator="lt",
            threshold=0.1,
            effect_delta={SemanticTag.STATE_SCRAP: 1.0}
        )
    ]
)

# --- Атом Дефицитности (Scarcity) ---
scarcity_atom = ComponentDefinition(
    id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"mat_scarcity")),
    name="Resource Scarcity",
    sphere=Sphere.MATERIAL,
    base_vector=SemanticVector(material=0.9, social=0.5),
    affordances={SemanticTag.ACT_MAT_TRADE}, # "speculate" и "monopolize" отсутствуют в таксономии
    default_data={DataKey.PRICE: 100.0}
)

# --- Атом Утилитарности (Utility) ---
utility_atom = ComponentDefinition(
    id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"mat_utility")),
    name="Functional Utility",
    sphere=Sphere.MATERIAL,
    base_vector=SemanticVector(material=0.5, vitality=0.6),
    affordances={SemanticTag.ACT_VIT_EAT, SemanticTag.ACT_MAT_CRAFT}, # "process", "survive" -> Eat/Craft
    latent_potential=[
        LatentPotentialRule(
            trigger_context=SemanticTag.CTX_EVENT_FAMINE,
            result_component_id=SemanticTag.ROLE_STRATEGIC_RESERVE,
            probability=0.9
        )
    ]
)

# --- Атом Транспортабельности (Portability) ---
portability_atom = ComponentDefinition(
    id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"mat_portability")),
    name="Logistical Portability",
    sphere=Sphere.MATERIAL,
    base_vector=SemanticVector(material=0.3, social=0.3),
    affordances={SemanticTag.ACT_MAT_CARRY}, # "export", "smuggle" -> Carry
    evolution_rules=[
        EvolutionRule(
            condition_axis="material",
            operator="lt",
            threshold=0.1,
            effect_delta={SemanticTag.STATE_IMMOBILE: 1.0}
        )
    ]
)

# --- Атом Взаимозаменяемости (Fungibility) ---
fungibility_atom = ComponentDefinition(
    id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"mat_fungibility")),
    name="Asset Fungibility",
    sphere=Sphere.MATERIAL,
    base_vector=SemanticVector(material=0.2, cognitive=0.4),
    affordances={SemanticTag.ACT_MAT_TRADE} # Остальные теги ("stack", "replace") удалены как магические
)


# ====== VITALITY ==========

# INDIVIDUAL PART

# --- Атом Резистентности (Resilience) ---
resilience_atom = ComponentDefinition(
    id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"vit_resilience")),
    name="Biological Resilience",
    sphere=Sphere.VITALITY,
    description="The capacity of a biological system to maintain integrity and recover.",
    base_vector=SemanticVector(vitality=0.6),
    affordances={SemanticTag.ACT_VIT_HEAL}, # "endure_pain", "survive_toxin" удалены (нет в таксономии)
    evolution_rules=[
        EvolutionRule(
            condition_axis="vitality",
            operator="lt",
            threshold=0.1,
            effect_delta={SemanticTag.STATE_BIO_CRITICAL: 1.0} # Переход в критическое состояние
        )
    ],
    latent_potential=[
        # Мостик в COGNITIVE: "Айсберг" — при смерти есть шанс осознания высших смыслов
        LatentPotentialRule(
            trigger_context=SemanticTag.CTX_EVENT_DEATH, 
            result_component_id=SemanticTag.TRAIT_COG_ABSTRACT, 
            probability=0.1
        )
    ],
    default_data={
        DataKey.HEALTH_CURRENT: 100.0,
        DataKey.HEALTH_MAX: 100.0
    }
)

# --- Атом Импульса (Drive) ---
drive_atom = ComponentDefinition(
    id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"vit_drive")),
    name="Vital Drive",
    sphere=Sphere.VITALITY,
    description="The intensity of primal urges and survival instincts.",
    base_vector=SemanticVector(vitality=0.8, cognitive=0.2),
    affordances={SemanticTag.ACT_VIT_PURSUE, SemanticTag.ACT_MAT_IMPACT}, # "react", "initiate_conflict" удалены
    # Эволюция: при низком материальном векторе (голод) драйв падает
    evolution_rules=[
        EvolutionRule(
            condition_axis="material",
            operator="lt",
            threshold=0.3,
            effect_delta={SemanticTag.STATE_BIO_LETHARGIC: 0.5}
        )
    ]
)

# --- Атом Метаболизма (Metabolism) ---
metabolism_atom = ComponentDefinition(
    id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"vit_metabolism")),
    name="Metabolic Rate",
    sphere=Sphere.VITALITY,
    description="The speed of energy conversion and resource consumption.",
    base_vector=SemanticVector(vitality=0.7, material=0.2), 
    affordances={SemanticTag.ACT_VIT_EAT}, # "exhaust", "hibernate" удалены
    evolution_rules=[
        EvolutionRule(
            condition_axis="vitality",
            operator="lt",
            threshold=0.2,
            effect_delta={SemanticTag.STATE_BIO_LETHARGIC: 1.0} # Истощение
        )
    ],
    default_data={DataKey.METABOLISM_RATE: 1.0}
)

# --- Атом Перцепции (Perception) ---
perception_atom = ComponentDefinition(
    id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"vit_perception")),
    name="Biological Perception",
    sphere=Sphere.VITALITY,
    base_vector=SemanticVector(vitality=0.4, cognitive=0.5),
    affordances={SemanticTag.ACT_VIT_SENSE}, # "track", "ignore", "identify" удалены
    latent_potential=[
        # Мостик в Эмерджентность: Высокое внимание открывает доступ к скрытым деталям
        LatentPotentialRule(
            trigger_context=SemanticTag.CTX_HIGH_AWARENESS,
            result_component_id=SemanticTag.TRAIT_KEEN_SENSES,
            probability=0.3
        )
    ],
    default_data={DataKey.SENSORY_RANGE: 20.0}
)

# POPULATION PART

# --- Атом Репродукции (Procreation) ---
procreation_atom = ComponentDefinition(
    id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"vit_procreation")),
    name="Procreation Drive",
    sphere=Sphere.VITALITY,
    base_vector=SemanticVector(vitality=0.9),
    affordances={SemanticTag.ACT_VIT_BREED}, 
    evolution_rules=[
        EvolutionRule(
            condition_axis="material", # Репродукция напрямую зависит от ресурсов в слоте
            operator="lt",
            threshold=0.3,
            effect_delta={SemanticTag.ACT_VIT_BREED: -0.5} 
        )
    ]
)

# --- Атом Популяционного фитнеса (Fitness) ---
fitness_atom = ComponentDefinition(
    id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"vit_fitness")),
    name="Population Fitness",
    sphere=Sphere.VITALITY,
    base_vector=SemanticVector(vitality=0.7, social=0.2),
    affordances={SemanticTag.ACT_VIT_SWARM}, 
    evolution_rules=[
        EvolutionRule(
            condition_axis="vitality",
            operator="lt",
            threshold=0.15,
            effect_delta={SemanticTag.STATE_BIO_EXTINCTION_RISK: 1.0} # Угроза вымирания
        )
    ]
)

# --- Атом Разнообразия (Diversity) ---
diversity_atom = ComponentDefinition(
    id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"vit_diversity")),
    name="Genetic Diversity",
    sphere=Sphere.VITALITY,
    base_vector=SemanticVector(vitality=0.4, cognitive=0.3),
    affordances={SemanticTag.ACT_VIT_MUTATE},
    latent_potential=[
        # Мостик в Трейты: Давление среды рождает адаптивного специалиста
        LatentPotentialRule(
            trigger_context=SemanticTag.CTX_EXTREME_PRESSURE,
            result_component_id=SemanticTag.TRAIT_ADAPTIVE_SPECIALIST,
            probability=0.2
        )
    ]
)

# --- Атом Симбиотичности (Dependency) ---
dependency_atom = ComponentDefinition(
    id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"vit_dependency")),
    name="Symbiotic Dependency",
    sphere=Sphere.VITALITY,
    base_vector=SemanticVector(vitality=0.3, social=0.6),
    affordances={SemanticTag.ACT_SOC_EXCHANGE}, # Взаимодействие через обмен ресурсами
    default_data={"dependency_strength": 0.5} # Оставили как кастомное поле, так как в DataKey его нет
)


# ====== SOCIAL ==========

# --- Атом Централизации (Centralization) ---
centralization_atom = ComponentDefinition(
    id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"soc_centralization")),
    name="Centralization",
    sphere=Sphere.SOCIAL,
    description="The degree to which power is concentrated in a single node.",
    base_vector=SemanticVector(social=0.8, cognitive=0.2), 
    affordances={SemanticTag.ACT_SOC_COMMAND}, # Удалены delegate и coordinate (отсутствуют в таксономии)
    evolution_rules=[
        EvolutionRule(
            condition_axis="social",
            operator="lt",
            threshold=0.3,
            effect_delta={SemanticTag.STATE_SOC_FRAGMENTED: 1.0} # Коллапс управления
        )
    ],
    default_data={DataKey.AUTHORITY_LEVEL: 1.0}
)

# --- Атом Сплоченности (Cohesion) ---
cohesion_atom = ComponentDefinition(
    id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"soc_cohesion")),
    name="Social Cohesion",
    sphere=Sphere.SOCIAL,
    description="The strength of bonds between members of a group.",
    base_vector=SemanticVector(social=0.7),
    affordances={SemanticTag.ACT_SOC_UNITE}, # Удален rally
    evolution_rules=[
        EvolutionRule(
            condition_axis="social",
            operator="lt",
            threshold=0.2,
            effect_delta={SemanticTag.STATE_SOC_INFIGHTING: 1.0} # Внутренние конфликты
        )
    ],
    latent_potential=[
        # Мостик в Эмерджентность: Внешняя угроза превращает сплоченность в фанатизм
        LatentPotentialRule(
            trigger_context=SemanticTag.CTX_THREAT_EXISTENTIAL,
            result_component_id=SemanticTag.TRAIT_SOC_FANATIC,
            probability=0.4
        )
    ]
)

# --- Атом Проницаемости (Permeability) ---
permeability_atom = ComponentDefinition(
    id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"soc_permeability")),
    name="Social Permeability",
    sphere=Sphere.SOCIAL,
    description="The ease of entering or leaving a social group.",
    base_vector=SemanticVector(social=0.5, cognitive=0.3), 
    affordances={SemanticTag.ACT_SOC_RECRUIT}, # Удалены infiltrate, exile, defect
    evolution_rules=[
        EvolutionRule(
            condition_axis="social",
            operator="lt",
            threshold=0.2,
            effect_delta={SemanticTag.STATE_SOC_ISOLATIONIST: 1.0} # Сектантство/Закрытость
        )
    ]
)

# --- Атом Стратификации (Stratification) ---
stratification_atom = ComponentDefinition(
    id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"soc_stratification")),
    name="Social Stratification",
    sphere=Sphere.SOCIAL,
    description="The depth and rigidity of hierarchy and class layers.",
    base_vector=SemanticVector(social=0.9, material=0.2),
    affordances={SemanticTag.ACT_SOC_OPPRESS}, # Удалены revolt, rank_up
    latent_potential=[
        # Мостик в Глобальные События: Расслоение порождает революцию при неравенстве
        LatentPotentialRule(
            trigger_context=SemanticTag.CTX_INEQUALITY_EXTREME,
            result_component_id=SemanticTag.EVENT_CIVIL_UNREST,
            probability=0.6
        )
    ],
    default_data={DataKey.AUTHORITY_LEVEL: 0.5}
)

# --- Атом Взаимности (Reciprocity) ---
reciprocity_atom = ComponentDefinition(
    id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"soc_reciprocity")),
    name="Reciprocity Mode",
    sphere=Sphere.SOCIAL,
    description="The logic of exchange between members.",
    base_vector=SemanticVector(social=0.6, material=0.4),
    affordances={
        SemanticTag.ACT_SOC_EXCHANGE, 
        SemanticTag.ACT_MAT_TRADE  # Мостик в Material: торговля — это и социальный, и физический акт
    },
    default_data={DataKey.PRICE: 1.0}
)


# ====== COGNITIVE ==========

# --- Атом Агентности (Agency) ---
agency_atom = ComponentDefinition(
    id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"cog_agency")),
    name="Cognitive Agency",
    sphere=Sphere.COGNITIVE,
    description="The capacity for self-directed goal setting and action.",
    base_vector=SemanticVector(cognitive=0.8, social=0.2),
    affordances={SemanticTag.ACT_COG_PLAN}, # Удалены "betray" и "lead" как магические строки
    evolution_rules=[
        EvolutionRule(
            condition_axis="cognitive",
            operator="lt",
            threshold=0.1,
            effect_delta={SemanticTag.STATE_COG_STUPOR: 1.0} # Потеря воли при шоке
        )
    ]
)

# --- Атом Абстракции (Abstraction / Magic Potential) ---
abstraction_atom = ComponentDefinition(
    id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"cog_abstraction")),
    name="Conceptual Abstraction",
    sphere=Sphere.COGNITIVE,
    description="Capacity to manipulate non-material concepts and energies.",
    base_vector=SemanticVector(cognitive=0.9, vitality=0.1),
    affordances={SemanticTag.ACT_COG_CAST}, # Объединяет "channel", "decipher", "perceive"
    default_data={DataKey.MANA_COST: 1.2} # Используем стандартизированный ключ
)

# --- Атом Догматизма (Dogmatism) ---
dogmatism_atom = ComponentDefinition(
    id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"cog_dogmatism")),
    name="Cognitive Dogmatism",
    sphere=Sphere.COGNITIVE,
    description="Adherence to a fixed internal model of reality.",
    base_vector=SemanticVector(cognitive=0.5, social=0.5),
    affordances={SemanticTag.ACT_COG_RESIST} # "sacrifice_self" и "enforce_rule" удалены
)

# --- Атом Сложности (Complexity) ---
complexity_atom = ComponentDefinition(
    id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"cog_complexity")),
    name="Cognitive Complexity",
    sphere=Sphere.COGNITIVE,
    description="The depth of logical chaining and capacity for multi-layered planning.",
    base_vector=SemanticVector(cognitive=0.9),
    affordances={
        SemanticTag.ACT_COG_CALCULATE, 
        SemanticTag.ACT_COG_PREDICT
    },
    evolution_rules=[
        EvolutionRule(
            condition_axis="cognitive",
            operator="lt",
            threshold=0.3,
            effect_delta={SemanticTag.STATE_COG_PRIMITIVE: 1.0} # Деградация до инстинктов
        )
    ],
    default_data={DataKey.COMPLEXITY: 5} # Заменяет "max_plan_steps"
)

# --- Атом Детерминизма (Determinism) ---
determinism_atom = ComponentDefinition(
    id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"cog_determinism")),
    name="Behavioral Determinism",
    sphere=Sphere.COGNITIVE,
    description="The predictability of behavior. Chaos vs Algorithm.",
    base_vector=SemanticVector(cognitive=0.6, material=0.2),
    affordances={SemanticTag.ACT_COG_CALCULATE}, # "predict", "standardize" удалены
    latent_potential=[
        # МОСТ: При высоком хаосе алгоритмическая сущность может "Пробудиться"
        LatentPotentialRule(
            trigger_context=SemanticTag.CTX_ENTROPY_HIGH,
            result_component_id=SemanticTag.TRAIT_COG_AWAKENED,
            probability=0.05
        )
    ]
)


# ====== SPECIAL ==========

# Атом Информации (Information / Lore)
information_atom = ComponentDefinition(
    id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"cog_information")),
    name="Information Content",
    sphere=Sphere.COGNITIVE,
    description="Structured data, knowledge, or narrative content.",
    base_vector=SemanticVector(cognitive=0.8, social=0.4), # Социальный вес, так как инфа нужна для общения
    affordances={
        SemanticTag.ACT_INFO_LEARN, 
        SemanticTag.ACT_INFO_SHARE, 
        SemanticTag.ACT_INFO_DECODE,
        SemanticTag.ACT_INFO_LIE
    },
    evolution_rules=[
        # Эрозия правды: Со временем или при передаче точность падает
        EvolutionRule(
            condition_axis="cognitive", # Используем ось Cognitive как "Точность/Accuracy"
            operator="lt",
            threshold=0.4,
            # result_tags=[SemanticTag.STATE_INFO_MYTH], # Факт превращается в Легенду
            effect_delta={"value": 0.5} # Мифы могут стоить дороже сухих фактов (как артефакты)
        ),
        # Полная потеря данных
        EvolutionRule(
            condition_axis="cognitive",
            operator="lt",
            threshold=0.05,
            # result_tags=[SemanticTag.STATE_INFO_FORGOTTEN],
            effect_delta={"value": 0.0}
        )
    ],
    latent_potential=[
        # Опасное знание (Лавкрафтианский троп)
        # Если сложность информации (Cognitive) запредельна для понимания
        LatentPotentialRule(
            trigger_context=SemanticTag.CTX_INFO_MEMETIC_HAZARD,
            result_component_id=SemanticTag.STATE_COG_STUPOR, # Сводит с ума читателя
            probability=0.3,
            modifiers={"sanity_damage": 1.0}
        ),
        # Утечка секрета (Связь с Social)
        # Если инфа имеет тег SECRET (это можно задать в default_data или tags) и попадает в публичный контекст
        LatentPotentialRule(
            trigger_context=SemanticTag.CTX_INFO_LEAK,
            result_component_id=SemanticTag.EVENT_CIVIL_UNREST, # Скандал может вызвать бунт
            probability=0.5
        )
    ],
    default_data=InformationData(accuracy=1.0, is_secret=False).model_dump(by_alias=True)
)

# Атом Эстетики (Aesthetics / Prestige)
aesthetics_atom = ComponentDefinition(
    id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"soc_aesthetics")),
    name="Aesthetic Value",
    sphere=Sphere.SOCIAL, # Красота — это социальный конструкт
    description="Visual or conceptual appeal that evokes emotional response.",
    base_vector=SemanticVector(social=0.9, cognitive=0.3),
    affordances={
        SemanticTag.ACT_AES_ADMIRE, 
        SemanticTag.ACT_AES_DEFACE, 
        SemanticTag.ACT_AES_APPRAISE
    },
    evolution_rules=[
        # Осквернение: Если объект физически поврежден (Material падает), страдает эстетика
        EvolutionRule(
            condition_axis="material", # Слушаем материальное состояние родителя (через прокси)
            operator="lt",
            threshold=0.3,
            # result_tags=[SemanticTag.STATE_AES_DESECRATED],
            effect_delta={"value": -0.8} # Испорченный шедевр теряет цену
        ),
        # Устаревание: Эстетика может "протухнуть" (выйти из моды)
        EvolutionRule(
            condition_axis="social",
            operator="lt",
            threshold=0.2,
            # result_tags=[SemanticTag.STATE_AES_OBSOLETE],
            effect_delta={"prestige": -0.5}
        )
    ],
    latent_potential=[
        # Вдохновение: Высокая эстетика в правильном контексте (Храм, Музей)
        LatentPotentialRule(
            trigger_context=SemanticTag.CTX_AES_INSPIRATION,
            result_component_id="trait_morale_boost", # Временный бафф для наблюдателей
            probability=0.8,
            # min_context_intensity=0.6
        ),
        # Шок/Отвращение: Если эстетика имеет отрицательный вектор (Ужас, Расчлененка)
        # Это позволяет использовать aesthetics_atom для описания "Ужасающих сцен"
        LatentPotentialRule(
            trigger_context=SemanticTag.CTX_AES_REVULSION,
            result_component_id=SemanticTag.STATE_COG_STUPOR, # Шок
            probability=0.7
        )
    ],
    default_data={"style_tags": ["ancient", "baroque"]} # Теги стиля для матчинга; их можно не хардкодить
)

# --- Атом Навыка (Generic Skill Container) ---
skill_atom = ComponentDefinition(
    id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"sys_skill")),
    name="Learned Skill",
    sphere=Sphere.COGNITIVE,
    description="A discrete unit of specialized knowledge or technique.",
    
    # Базовый вектор пуст — он будет заполняться при генерации!
    base_vector=SemanticVector(), 
    
    # Аффордансы тоже пусты — они придут из метаданных навыка
    affordances=set(),

    evolution_rules=[
        # ПРАВИЛО 1: Обычная практика (Гринд)
        # Если просто много пользовался (usage_xp), растет точность
        EvolutionRule(
            condition_axis="usage_xp",
            operator="gt",
            threshold=100.0,
            effect_delta={"val_accuracy": 0.1}
        ),
        
        # ПРАВИЛО 2: Драматический прорыв (Pacing)
        # Если навык использовался в контексте "Смертельной опасности" (High Tension),
        # он мутирует мгновенно, минуя XP.
        EvolutionRule(
            condition_axis="context_tension", # <-- Это значение мы прокидываем из PacingState
            operator="gt",
            threshold=0.9, # Только в кульминации
            effect_delta={
                "vector_multiplier": 1.5, # Резкий скачок силы
                "new_affordance_unlock": 1.0 # Триггер добавления нового тега
            }
        )
    ],
    
    default_data={
        "skill_name": "Unknown Skill",
        "xp_current": 0.0,
        "xp_next_level": 100.0,
        "scaling_stat": "cog_abstraction" # От чего зависит сила?
    }
)

ALL_ATOMS = [
    integrity_atom, thermal_atom, acuity_atom,
    density_atom, kinetics_atom, conductivity_atom,
    perishability_atom, scarcity_atom, utility_atom,
    portability_atom, fungibility_atom, resilience_atom,
    drive_atom, metabolism_atom, perception_atom, fitness_atom,
    diversity_atom, dependency_atom, centralization_atom,
    cohesion_atom, permeability_atom, stratification_atom,
    reciprocity_atom, agency_atom, abstraction_atom, dogmatism_atom,
    complexity_atom, determinism_atom, information_atom, aesthetics_atom,
    skill_atom
]

def get_standard_atoms() -> List[ComponentDefinition]:
    return ALL_ATOMS
