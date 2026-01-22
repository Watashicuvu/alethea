# src/models/ecs/taxonomy.py
from enum import Enum

class EventArchetype(str, Enum):
    """
    Базовые типы сцен для наложения математических масок (Bias).
    """
    CONFLICT_PHYSICAL = "conflict_physical" # Битва, погоня, физическое преодоление
    CONFLICT_SOCIAL   = "conflict_social"   # Спор, допрос, соблазнение, переговоры
    DISCOVERY         = "discovery"         # Лутинг, расследование, озарение
    TRANSITION        = "transition"        # Путешествие, скрытное проникновение
    CREATION          = "creation"          # Крафт, ритуал, строительство
    RELAXATION        = "relaxation"        # Отдых, таверна (восстановление Vitality)
    MYSTERY           = "mystery"           # Непонятное, хоррор (давление на Cognitive)

class SemanticTag(str, Enum):
    """
    Глобальный реестр семантических тегов.
    Используется в EvolutionRules, LatentPotential и Affordances.
    Никакого хардкода в атомах — только ссылки на этот класс.
    """

    # =========================================================================
    # 1. STATES (Состояния)
    # Теги, которые "висят" на сущности как результат эволюции или воздействия.
    # =========================================================================
    
    # Material States (из integrity, thermal, kinetics, portability)
    STATE_STRUCTURAL_FAILURE = "state_mat_broken"       # Сломано / Разрушено (было: "broken")
    STATE_STRUCTURAL_WEAKNESS = "state_mat_weakness"    # Ослаблено жаром/коррозией (было: "structural_weakness")
    STATE_PHASE_ETHEREAL = "state_mat_ethereal"         # Нематериально / Призрак (было: "ethereal")
    STATE_KIN_STATIC = "state_mat_static"               # Неподвижно / Застряло (было: "static")
    STATE_IMMOBILE = "state_mat_immobile"               # Слишком тяжело для переноски (было: "immobile")
    STATE_SCRAP = "state_mat_scrap"                     # Мусор / Лом (замена "deleted" для perishability)
    STATE_SOC_OBEDIENT = "state_soc_obedient"   # Подчинение
    STATE_SOC_SKEPTICAL = "state_soc_skeptical" # Недоверие (нужно пробить аргументами)
    STATE_INFO_MISLED = "state_info_misled"     # Дезинформирован

    # Vitality States (из resilience, metabolism, fitness)
    STATE_BIO_CRITICAL = "state_vit_critical"           # При смерти / Критическое состояние (было: "critical_condition")
    STATE_BIO_LETHARGIC = "state_vit_lethargic"         # Истощение / Сонливость (было: "lethargic")
    STATE_BIO_EXTINCTION_RISK = "state_vit_extinction"  # Угроза вымирания вида (было: "extinction_risk")
    STATE_BIO_DEAD = "state_vit_dead"                   # Мертв (логическое завершение resilience)

    # Social States (из centralization, cohesion, permeability)
    STATE_SOC_FRAGMENTED = "state_soc_fragmented"       # Разрозненность / Анархия (было: "fragmentation")
    STATE_SOC_INFIGHTING = "state_soc_infighting"       # Внутренние распри (было: "internal_conflict")
    STATE_SOC_ISOLATIONIST = "state_soc_closed"         # Закрытое общество / Секта (было: "closed_society")
    
    # Cognitive States (из agency, complexity)
    STATE_COG_STUPOR = "state_cog_stupor"               # Шок / Потеря воли (было: "stupor")
    STATE_COG_PRIMITIVE = "state_cog_primitive"         # Деградация до инстинктов (было: "primitive_logic")

    # =========================================================================
    # 2. CONTEXTS (Триггеры Потенциала)
    # События или условия среды, которые активируют LatentPotential.
    # =========================================================================
    
    # Material Contexts
    CTX_INT_THERMAL_SOURCE = "ctx_int_thermal"          # Взаимодействие с теплом (было: "steam_engine_interaction")
    CTX_INT_INDUSTRIAL = "ctx_int_industrial"           # Индустриальная обработка (было: "industrial_processing")
    
    # Vitality Contexts
    CTX_EVENT_FAMINE = "ctx_event_famine"               # Голод / Дефицит ресурсов (было: "famine_event")
    CTX_EVENT_DEATH = "ctx_event_death"                 # Смерть рядом / Некротический фон (было: "death_event")
    CTX_HIGH_AWARENESS = "ctx_high_awareness"           # Высокая концентрация/Внимание (было: "high_awareness")
    CTX_EXTREME_PRESSURE = "ctx_evo_pressure"           # Давление среды / Естественный отбор (было: "extreme_pressure")
    
    # Social Contexts
    CTX_THREAT_EXISTENTIAL = "ctx_threat_existential"   # Угроза уничтожения группы (было: "existential_threat")
    CTX_INEQUALITY_EXTREME = "ctx_soc_inequality"       # Классовое расслоение (было: "extreme_inequality")
    
    # Cognitive Contexts
    CTX_ENTROPY_HIGH = "ctx_cog_chaos"                  # Хаос / Глитч реальности (было: "high_chaos_entropy")

    # =========================================================================
    # 3. TRAITS & ROLES (Результаты Потенциала)
    # Новые свойства, которые появляются у сущности (Emergent Gameplay).
    # =========================================================================
    
    # Material Roles
    ROLE_POWER_SOURCE = "role_phys_generator"           # Становится источником энергии (из thermal)
    ROLE_STRATEGIC_RESERVE = "role_mat_reserve"         # Становится страт. запасом (из utility)
    
    # Vitality Traits
    TRAIT_KEEN_SENSES = "trait_vit_keen_eyes"           # Острые чувства (из perception)
    TRAIT_ADAPTIVE_SPECIALIST = "trait_vit_adaptive"    # Уникальная мутация (из diversity)
    
    # Social Traits
    TRAIT_SOC_FANATIC = "trait_soc_fanatic"             # Фанатизм (из cohesion)
    EVENT_CIVIL_UNREST = "event_soc_revolt"             # Революция (из stratification) - технически это EventComponent
    
    # Cognitive Traits
    TRAIT_COG_AWAKENED = "trait_cog_agency"             # Обретение воли/AI (из determinism)
    TRAIT_COG_ABSTRACT = "trait_cog_abstraction"        # Магия/Понимание высших смыслов (из resilience/death)

    # =========================================================================
    # 4. ACTION AFFORDANCES (Абстрактные действия)
    # Ключи для поиска глаголов.
    # =========================================================================
    
    ACT_SOC_STEALTH = "act_soc_stealth"

    # Material Actions
    ACT_MAT_HOLD_SHAPE = "act_mat_hold_shape"
    ACT_MAT_FREEZE = "act_mat_freeze"
    ACT_MAT_BURN = "act_mat_burn"
    ACT_MAT_CUT = "act_mat_cut"
    ACT_MAT_CRUSH = "act_mat_crush"
    ACT_MAT_TRADE = "act_mat_trade" # buy/sell merged
    ACT_MAT_CRAFT = "act_mat_craft"
    ACT_MAT_CONTAIN = "act_mat_contain"
    ACT_MAT_IMPACT = "act_mat_impact"
    ACT_MAT_CONDUCT = "act_mat_conduct"
    ACT_MAT_SPOIL = "act_mat_spoil"
    ACT_MAT_CARRY = "act_mat_carry"
    
    # Vitality Actions
    ACT_VIT_HEAL = "act_vit_heal"
    ACT_VIT_EAT = "act_vit_consume"
    ACT_VIT_PURSUE = "act_vit_pursue"
    ACT_VIT_MUTATE = "act_vit_mutate"
    ACT_VIT_SENSE = "act_vit_detect"
    ACT_VIT_BREED = "act_vit_replicate"
    ACT_VIT_SWARM = "act_vit_swarm"
    
    # Social Actions
    ACT_SOC_COMMAND = "act_soc_command"
    ACT_SOC_UNITE = "act_soc_unite"
    ACT_SOC_RECRUIT = "act_soc_recruit"
    ACT_SOC_OPPRESS = "act_soc_oppress"
    ACT_SOC_EXCHANGE = "act_soc_gift" # trade/gift depending on context
    
    # Cognitive Actions
    ACT_COG_PLAN = "act_cog_plan"
    ACT_COG_CAST = "act_cog_channel" # magic
    ACT_COG_RESIST = "act_cog_deny"
    ACT_COG_CALCULATE = "act_cog_solve"
    ACT_COG_PREDICT = "act_cog_predict"

    # =========================================================================
    # EXTENSION: INFORMATION & AESTHETICS
    # =========================================================================

    # --- Information States & Contexts ---
    STATE_INFO_ENCRYPTED = "state_info_encrypted"       # Данные скрыты/зашифрованы
    STATE_INFO_MYTH = "state_info_myth"                 # Искаженная информация, легенда (низкая точность)
    STATE_INFO_FORGOTTEN = "state_info_forgotten"       # Потерянные знания
    
    CTX_INFO_LEAK = "ctx_info_leak"                     # Утечка информации / Скандал
    CTX_INFO_RESEARCH = "ctx_info_research"             # Процесс исследования / Открытия
    CTX_INFO_MEMETIC_HAZARD = "ctx_info_hazard"         # Опасное знание (сводит с ума)

    ACT_INFO_LEARN = "act_info_learn"                   # Изучить / Прочитать
    ACT_INFO_SHARE = "act_info_share"                   # Рассказать / Опубликовать
    ACT_INFO_DECODE = "act_info_decode"                 # Расшифровать
    ACT_INFO_FORGET = "act_info_forget"                 # Забыть (для очистки памяти NPC)
    ACT_INFO_LIE = "act_info_lie"                       # Дезинформировать

    # --- Aesthetics States & Contexts ---
    STATE_AES_DIVINE = "state_aes_divine"               # Божественная красота / Внушает трепет
    STATE_AES_DESECRATED = "state_aes_desecrated"       # Осквернено / Уродливо
    STATE_AES_OBSOLETE = "state_aes_obsolete"           # Вышло из моды / Кич
    
    CTX_AES_INSPIRATION = "ctx_aes_inspiration"         # Вдохновение (поднимает мораль)
    CTX_AES_REVULSION = "ctx_aes_revulsion"             # Отвращение / Шок

    ACT_AES_ADMIRE = "act_aes_admire"                   # Любоваться
    ACT_AES_CREATE = "act_aes_create"                   # Создавать искусство
    ACT_AES_DEFACE = "act_aes_deface"                   # Вандализм / Осквернение
    ACT_AES_APPRAISE = "act_aes_appraise"               # Оценивать (критика)

    # --- Traversal & Graph Interaction ---
    ACT_TRAV_CLIMB = "act_trav_climb"       # Для Verticality edges
    ACT_TRAV_OPEN = "act_trav_open"         # Для дверей/сундуков
    ACT_TRAV_UNLOCK = "act_trav_unlock"     # Для запертых edges (нужен ключ/skill)
    ACT_TRAV_SQUEEZE = "act_trav_squeeze"   # Пролезть (check size < X)
    ACT_TRAV_JUMP = "act_trav_jump"         # Перепрыгнуть (check agility)

    # =================================================================
    # 5. PROPERTIES (Пассивные свойства для фильтрации ролей)
    # =================================================================
    PROP_LIVING = "prop_is_living"       # Живое существо (имеет Vitality)
    PROP_SENTIENT = "prop_is_sentient"   # Разумное (NPC, Игрок)
    PROP_MOBILE = "prop_is_mobile"       # Может перемещаться (NPC, Монстр, Машина)
    PROP_ITEM = "prop_is_item"           # Можно положить в инвентарь
    PROP_CONTAINER = "prop_is_container" # Может содержать другие предметы
    PROP_VALUABLE = "prop_is_valuable"   # Имеет рыночную цену
    PROP_LOCATION = "prop_location"      # Является локацией

    # ... дополним Actions ...
    ACT_SOC_SERVE = "act_soc_serve"      # Служить/Подчиняться
    ACT_MAT_BLOCK = "act_mat_block"      # Блокировать проход (Дверь, Страж)
    
    STATE_MAT_FLAMMABLE = "state_mat_flammable" # Горючее (масло) - для синергии с огнем
    STATE_MAT_WET = "state_mat_wet"             # Мокрое - для синергии с электричеством/холодом

    # Physical Styles
    STYLE_FORCE = "style_force"       # Грубая сила, пробивание (Heavy)
    STYLE_QUICK = "style_quick"       # Скорость, реакция (Fast)
    STYLE_CONTROL = "style_control"   # Контроль территории/тела (Grapple)
    STYLE_RANGED = "style_ranged"     # Дистанционное воздействие

    # Social Styles
    STYLE_DIPLOMACY = "style_diplomacy" # Мягкая сила, переговоры
    STYLE_DOMINANCE = "style_dominance" # Жесткая сила, давление
    STYLE_DECEPTION = "style_deception" # Скрытое воздействие

    # Cognitive/Magic Styles
    STYLE_MYSTIC = "style_mystic"     # Использование магии/псионики
    STYLE_ANALYTIC = "style_analytic" # Сбор данных
    STYLE_STEALTH = "style_stealth"   # Скрытность

class DataKey(str, Enum):
    # Material
    MASS = "val_mass_kg"
    VOLUME = "val_volume_m3"
    DENSITY = "val_density"
    TEMPERATURE = "val_temp_celsius"
    VELOCITY = "val_velocity_vec"
    RESISTANCE = "val_resistance_ohm"
    
    # Vitality
    HEALTH_CURRENT = "val_hp_current"
    HEALTH_MAX = "val_hp_max"
    METABOLISM_RATE = "val_metabolism_rate"
    SENSORY_RANGE = "val_sense_range"
    
    # Social / Eco
    PRICE = "val_price_base"
    AUTHORITY_LEVEL = "val_authority_lvl"
    
    # Cognitive / Info
    ACCURACY = "val_accuracy"      # Точность информации (0.0 - 1.0)
    COMPLEXITY = "val_complexity"  # Сложность понимания
    MANA_COST = "val_mana_cost"
