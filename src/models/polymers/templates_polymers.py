from src.models.new_schemas import ArchetypeRecipe, SemanticVector
from src.models.molecules.templates_moleculas import (actuator_phys_striker, shell_rigid, mat_int_control,
                                            shell_bio_soft, mind_bio_instinct, mat_struct_container,
                                            core_bio_vital, actuator_phys_projector, mat_payload_treasure,
                                            shell_etheric, mind_cog_sentient, core_cog_etheric, mat_int_grip,
                                            mat_struct_item, mat_payload_resource, mat_engine_mechanism, mat_payload_volatile,
                                            mat_struct_obstacle, actuator_bio_natural, mind_soc_hive, shell_soc_bureaucracy, 
                                            core_mat_resource, topo_gate_generic, topo_atmo_phys, topo_sub_terrain,
                                            topo_sub_fluid, topo_gate_social, topo_atmo_mental, topo_gate_physical,
                                            topo_sub_void, shell_soc_dogma, plot_trig_interaction, plot_event_revelation,
                                            plot_proc_task, plot_proc_calamity, plot_event_disaster,
                                            mat_engine_converter, actuator_soc_voice, shell_social, core_soc_authority)

# TODO можно брать не фиксированные шаблоны, а линейную комбинацию!
# то есть, когда определяем, к чему отнести, можем брать несколько вариантов
# но, на самом деле, лучше просто переопределять индивидуально; не нужна тут
# линейная комбинация 

RECIPE_AGENT_GRUNT = ArchetypeRecipe(
    archetype_id="ARCH_AGENT_GRUNT",
    description="Standard biological combatant relying on equipment and physique.",
    layers_config=[
        # 1. Актуатор (Оружие) - Встречает врага первым (парирование)
        (actuator_phys_striker, "Main Weapon", SemanticVector(phys_kinetics=1.0, mat_acuity=0.8)),
        
        # 2. Внешняя Броня (Экипировка)
        (shell_rigid, "Armor", SemanticVector(mat_density=1.0, mat_integrity=1.0)),
        
        # 3. Биологическое Тело (Последний рубеж)
        (shell_bio_soft, "Body", SemanticVector(vit_resilience=1.0, mat_density=0.5)),
        
        # 4. Разум (Инстинкт/Дисциплина)
        (mind_bio_instinct, "Mind", SemanticVector(vit_drive=1.0)),
        
        # 5. Ядро (Сердце)
        (core_bio_vital, "Life Core", SemanticVector(vit_metabolism=1.0, vit_resilience=0.5))
    ]
)

RECIPE_AGENT_CASTER = ArchetypeRecipe(
    archetype_id="ARCH_AGENT_CASTER",
    description="Ranged unit utilizing projectiles or magic with low physical defense.",
    layers_config=[
        # 1. Актуатор (Дальний бой)
        (actuator_phys_projector, "Focus/Bow", SemanticVector(phys_kinetics=0.5, cog_complexity=1.0)),
        
        # 2. Магический Щит (Вместо лат)
        (shell_etheric, "Mana Shield", SemanticVector(cog_abstraction=1.0, phys_kinetics=0.5)),
        
        # 3. Тело (Хрупкое)
        (shell_bio_soft, "Body", SemanticVector(vit_resilience=0.6, mat_density=0.3)),
        
        # 4. Разум (Высокий интеллект)
        (mind_cog_sentient, "Mind", SemanticVector(cog_agency=1.5, cog_information=1.0)),
        
        # 5. Ядро (Связь с маной)
        (core_cog_etheric, "Soul Core", SemanticVector(cog_abstraction=2.0))
    ]
)

RECIPE_AGENT_CONSTRUCT = ArchetypeRecipe(
    archetype_id="ARCH_AGENT_CONSTRUCT",
    description="Non-biological entity driven by fuel or magic.",
    layers_config=[
        # 1. Кулаки / Встроенное лезвие
        (actuator_phys_striker, "Manipulator", SemanticVector(phys_kinetics=1.5, mat_density=2.0)),
        
        # 2. Корпус (Броня и Тело едины)
        (shell_rigid, "Chassis", SemanticVector(mat_integrity=3.0, mat_density=2.5)),
        
        # 3. Двигатель (Вместо органов)
        (mat_engine_converter, "Engine", SemanticVector(mat_thermal=1.0, mat_utility=1.0)),
        
        # 4. Ядро (Программа / Магия)
        (core_cog_etheric, "Control Unit", SemanticVector(cog_determinism=2.0))
    ]
)

RECIPE_AGENT_LEADER = ArchetypeRecipe(
    archetype_id="ARCH_AGENT_LEADER",
    description="High-value target protected by social structures and influence.",
    layers_config=[
        # 1. Голос (Приказы)
        (actuator_soc_voice, "Authority", SemanticVector(soc_stratification=2.0, cog_information=1.5)),
        
        # 2. Социальная Защита (Статус/Свита)
        (shell_social, "Status Barrier", SemanticVector(soc_stratification=2.0, soc_cohesion=1.5)),
        
        # 3. Тело (Обычно слабое)
        (shell_bio_soft, "Body", SemanticVector(vit_resilience=0.8)),
        
        # 4. Разум (Интриган)
        (mind_cog_sentient, "Ego", SemanticVector(cog_agency=2.0, cog_dogmatism=1.5)),
        
        # 5. Ядро Власти
        (core_soc_authority, "Power Core", SemanticVector(soc_centralization=2.0))
    ]
)

# --- 1. Контейнер / Хранилище (ARCH_OBJ_CONTAINER) ---
# Использование: Сундук, Сейф, Бочка, Шкаф.
# Логика: Interface (Замок) -> Shell (Стенки) -> Payload (Содержимое).
RECIPE_OBJ_CONTAINER = ArchetypeRecipe(
    archetype_id="ARCH_OBJ_CONTAINER",
    description="Stationary object designed to store items. Requires interaction or destruction to open.",
    layers_config=[
        # 1. Интерфейс (Замок / Крышка)
        # Если это сундук с замком, vector modifiers добавят complexity.
        (mat_int_control, "Lock Mechanism", SemanticVector(phys_kinetics=0.5, cog_complexity=0.1)),
        
        # 2. Каркас (Стенки)
        # Защищает Payload. Если Integrity упадет в 0, Payload выпадет.
        (mat_struct_container, "Casing", SemanticVector(mat_integrity=1.0, mat_density=1.0)),
        
        # 3. Наполнение (Лут)
        # По умолчанию считаем, что там сокровища. Текст может заменить это на Resource.
        (mat_payload_treasure, "Contents", SemanticVector(mat_fungibility=1.0))
    ]
)

# --- 2. Предмет / Расходник (ARCH_OBJ_ITEM) ---
# Использование: Зелье, Еда, Слиток, Ключ.
# Логика: Маленький объект, который можно взять (Grip). Часто хрупкий.
RECIPE_OBJ_ITEM = ArchetypeRecipe(
    archetype_id="ARCH_OBJ_ITEM",
    description="Portable object capable of being carried or consumed.",
    layers_config=[
        # 1. Интерфейс (Ручка / Пробка) - Обеспечивает Portability
        (mat_int_grip, "Handle", SemanticVector(mat_portability=1.0, mat_utility=1.0)),
        
        # 2. Каркас (Тело предмета)
        # Для зелья это стекло (Integrity low), для слитка - металл (Integrity high).
        (mat_struct_item, "Body", SemanticVector(mat_integrity=0.5, mat_density=0.2)),
        
        # 3. Наполнение (Эффект)
        # Для зелья это Resource (Heal), для меча это может быть магия.
        (mat_payload_resource, "Effect", SemanticVector(mat_utility=1.0))
    ]
)

# --- 3. Активное Устройство / Ловушка (ARCH_OBJ_DEVICE) ---
# Использование: Мина, Капкан, Рычаг, Турель.
# Логика: Interface (Триггер) -> Engine (Механизм) -> Payload (Эффект).
RECIPE_OBJ_DEVICE = ArchetypeRecipe(
    archetype_id="ARCH_OBJ_DEVICE",
    description="Mechanism that converts input energy into an active effect.",
    layers_config=[
        # 1. Интерфейс (Триггер / Сенсор)
        # Может реагировать на нажатие (Kinetics) или движение.
        (mat_int_control, "Trigger", SemanticVector(phys_kinetics=0.1, cog_complexity=0.5)),
        
        # 2. Механизм (Двигатель)
        # Преобразует триггер в действие.
        (mat_engine_mechanism, "Mechanism", SemanticVector(mat_integrity=0.8)),
        
        # 3. Наполнение (Боеголовка)
        # Взрывчатка или иной эффект.
        (mat_payload_volatile, "Payload", SemanticVector(phys_kinetics=2.0, mat_thermal=1.5))
    ]
)

# --- 4. Преграда / Структура (ARCH_OBJ_OBSTACLE) ---
# Использование: Дверь, Стена, Завал, Статуя.
# Логика: Только Shell. Иногда Interface (если это дверь с ручкой).
RECIPE_OBJ_OBSTACLE = ArchetypeRecipe(
    archetype_id="ARCH_OBJ_OBSTACLE",
    description="Large static structure blocking movement.",
    layers_config=[
        # 1. Интерфейс (Опционально - Ручка двери)
        # У стены этого слоя не будет (vector modifiers могут обнулить Integrity слоя).
        (mat_int_control, "Access Point", SemanticVector(phys_kinetics=0.5)),

        # 2. Каркас (Масса)
        # Главный слой. Огромная Density и Integrity.
        (mat_struct_obstacle, "Structure", SemanticVector(mat_integrity=5.0, mat_density=10.0))
        
        # Payload обычно отсутствует или равен debris (обломкам).
    ]
)

# --- 1. Рой / Толпа (ARCH_GROUP_SWARM) ---
# Использование: Стая волков, Рой насекомых, Толпа зомби, Крестьянский бунт.
# Логика: Единый биологический организм. Управляется инстинктом.
# Смерть: Когда заканчивается "биомасса" (Core Vital).
RECIPE_GROUP_SWARM = ArchetypeRecipe(
    archetype_id="ARCH_GROUP_SWARM",
    description="Biological collective driven by instinct and mass. High physical presence, low organization.",
    layers_config=[
        # 1. Актуатор (Множество зубов/рук)
        # Атакует физически. Сила зависит от размера (Kinetics).
        (actuator_bio_natural, "Swarm Attack", SemanticVector(phys_kinetics=2.0, vit_drive=1.5)),
        
        # 2. Оболочка (Биомасса)
        # Рой — это "жидкое тело". Урон распределяется по всем.
        # Высокая Resilience, но низкая Density (легко разбросать).
        (shell_bio_soft, "Biomass", SemanticVector(vit_resilience=5.0, mat_density=0.5)),
        
        # 3. Разум (Коллективное бессознательное)
        # Реагирует на эмоции (страх/ярость), но не на аргументы.
        (mind_soc_hive, "Hive Mind", SemanticVector(soc_cohesion=1.0, vit_drive=2.0)),
        
        # 4. Ядро (Популяция)
        # Если убить достаточно особей, рой умирает (рассеивается).
        (core_bio_vital, "Population", SemanticVector(vit_fitness=1.0))
    ]
)

# --- 2. Организация / Гильдия (ARCH_GROUP_ORG) ---
# Использование: Торговая гильдия, Городской совет, Корпорация, Армия.
# Логика: Держится на Деньгах и Правилах. Уязвима к коррупции и банкротству.
# Смерть: Казна пуста (Core Treasury).
RECIPE_GROUP_ORG = ArchetypeRecipe(
    archetype_id="ARCH_GROUP_ORG",
    description="Formal structure reliant on resources and procedures.",
    layers_config=[
        # 1. Актуатор (Влияние / Дипломатия)
        # Организация "бьет" законами, сделками или наемниками.
        (actuator_soc_voice, "Influence", SemanticVector(soc_reciprocity=1.5, cog_information=1.0)),
        
        # 2. Оболочка (Бюрократия)
        # Гасит инициативу и хаос. Очень прочная против "быстрых" изменений.
        # Чтобы пробить, нужна высокая Complexity (юридическая хитрость).
        (shell_soc_bureaucracy, "Red Tape", SemanticVector(soc_centralization=2.0, cog_complexity=1.5)),
        
        # 3. Разум (Совет директоров / Штаб)
        # Принимает рациональные решения.
        (mind_cog_sentient, "Administration", SemanticVector(cog_agency=1.0, cog_complexity=2.0)),
        
        # 4. Ядро (Казна)
        # Нет денег — нет организации.
        (core_mat_resource, "Treasury", SemanticVector(mat_fungibility=5.0, mat_scarcity=1.0))
    ]
)

# --- 3. Культ / Секта (ARCH_GROUP_CULT) ---
# Использование: Религиозные фанатики, Тайное общество, Революционная ячейка.
# Логика: Держится на Лидере и Догме. Уязвима к потере лидера, но иммунна к логике/деньгам.
# Смерть: Убийство Лидера (Core Authority).
RECIPE_GROUP_CULT = ArchetypeRecipe(
    archetype_id="ARCH_GROUP_CULT",
    description="Ideological group centered around a charismatic leader or dogma.",
    layers_config=[
        # 1. Актуатор (Пропаганда / Террор)
        # Атакует веру (Information) или тела (Kinetics).
        (actuator_soc_voice, "Propaganda", SemanticVector(cog_dogmatism=2.0, soc_aggression=1.5)),
        
        # 2. Оболочка (Догма)
        # Информационный фильтр. Отсеивает "ересь" (чужую Information).
        # Пробивается только фактами невероятной силы (Revelation) или смертью лидера.
        (shell_soc_dogma, "Ideological Shield", SemanticVector(cog_dogmatism=3.0, soc_cohesion=2.0)),
        
        # 3. Разум (Фанатизм)
        # Единая воля, подавление индивидуальности.
        (mind_soc_hive, "Fanaticism", SemanticVector(soc_submission=2.0)),
        
        # 4. Ядро (Лидер / Идол)
        # Центр всего. Если уничтожить (компромат или убийство), культ распадается.
        (core_soc_authority, "The Leader", SemanticVector(soc_centralization=3.0, soc_stratification=2.0))
    ]
)

# --- 1. Стандартный Локус / Комната (ARCH_LOC_STANDARD) ---
# Использование: Лесная поляна, Комната в таверне, Городская площадь.
# Логика: Открытый проход -> Нейтральная среда -> Твердая земля.
RECIPE_LOC_STANDARD = ArchetypeRecipe(
    archetype_id="ARCH_LOC_STANDARD",
    description="Standard traversable space with minimal resistance.",
    layers_config=[
        # 1. Шлюз (Обычно открыт или простая дверь)
        # Permeability: Высокая (легко войти).
        (topo_gate_generic, "Entrance", SemanticVector(phys_kinetics=0.0, soc_permeability=1.0)),
        
        # 2. Атмосфера (Нейтральная)
        # Не наносит урона, просто есть. Density воздуха.
        (topo_atmo_phys, "Ambience", SemanticVector(mat_density=0.1)),
        
        # 3. Субстрат (Твердая земля)
        # Стандартное трение.
        (topo_sub_terrain, "Ground", SemanticVector(phys_kinetics=0.0, mat_density=1.0))
    ]
)

# --- 2. Опасная Зона / Ловушка (ARCH_LOC_HAZARD) ---
# Использование: Яма с кольями, Радиоактивное болото, Горящее здание.
# Логика: Легкий вход (или скрытый) -> Агрессивная среда -> Опасный пол.
RECIPE_LOC_HAZARD = ArchetypeRecipe(
    archetype_id="ARCH_LOC_HAZARD",
    description="Hostile environment designed to damage or impede agents.",
    layers_config=[
        # 1. Шлюз (Ловушка)
        # Легко войти (Kinetics +), но может сработать триггер при входе.
        (topo_gate_generic, "Perimeter", SemanticVector(phys_kinetics=1.0, cog_information=0.1)),
        
        # 2. Атмосфера (Вредная)
        # Радиация, Жар, Ядовитый газ. Наносит DoT (Damage over Time).
        # Вектор Reactivity будет содержать vit_resilience (Урон).
        (topo_atmo_phys, "Hazard Field", SemanticVector(mat_thermal=1.5, vit_resilience=-0.5)),
        
        # 3. Субстрат (Замедляющий или ранящий)
        # Болото (Fluid) или Шипы (Hazard).
        # Вектор Reactivity замедляет движение (Kinetics < 0).
        (topo_sub_fluid, "Difficult Terrain", SemanticVector(phys_kinetics=-0.8))
    ]
)

# --- 3. Социальный Хаб / Святилище (ARCH_LOC_SANCTUARY) ---
# Использование: Тронный зал, Храм, Банк, Штаб гильдии.
# Логика: Строгий контроль входа -> Подавляющая аура -> Удобный пол.
RECIPE_LOC_SANCTUARY = ArchetypeRecipe(
    archetype_id="ARCH_LOC_SANCTUARY",
    description="Protected zone governed by social rules or magical wards.",
    layers_config=[
        # 1. Шлюз (Стража / Фейс-контроль)
        # Требует Status (Stratification) или Pass (Information).
        (topo_gate_social, "Guard Post", SemanticVector(soc_stratification=1.5, soc_reciprocity=1.0)),
        
        # 2. Атмосфера (Ментал / Аура)
        # Подавляет агрессию (Aggression dampening) или повышает мораль.
        # Stability: cog_dogmatism (Сила закона/веры).
        (topo_atmo_mental, "Social Aura", SemanticVector(cog_dogmatism=2.0, soc_aggression=-1.0)),
        
        # 3. Субстрат (Пол)
        # Обычно благоустроенный (мрамор, ковры). Бонус к эстетике.
        (topo_sub_terrain, "Floor", SemanticVector(soc_aesthetics=1.0))
    ]
)

# --- 4. Транзит / Барьер (ARCH_LOC_TRANSIT) ---
# Использование: Коридор, Мост над пропастью, Вентиляционная шахта, Телепорт.
# Логика: Главное здесь — Шлюз (сложность прохода) и Субстрат (риск падения).
RECIPE_LOC_TRANSIT = ArchetypeRecipe(
    archetype_id="ARCH_LOC_TRANSIT",
    description="Connector node emphasizing movement constraints.",
    layers_config=[
        # 1. Шлюз (Физическое препятствие)
        # Запертая дверь, Завал. Требует Key или Strength.
        (topo_gate_physical, "Barrier", SemanticVector(mat_integrity=2.0, mat_acuity=0.5)),
        
        # 2. Атмосфера (Пустота / Ветер)
        # Может сдуть (Kinetics).
        (topo_atmo_phys, "Draft", SemanticVector(phys_kinetics=0.5)),
        
        # 3. Субстрат (Узкий / Опасный)
        # Void (нужен полет) или узкий мостик (требует ловкости).
        (topo_sub_void, "Abyss", SemanticVector(mat_density=0.0)) 
    ]
)

# --- 1. Сцена / Мгновенное Событие (ARCH_PLOT_SCENE) ---
# Использование: Взрыв ловушки, Важный диалог, Скример, Внезапное озарение.
# Логика: Триггер (ждет условия) -> Событие (бабах).
# Жизненный цикл: Ждет в фоне -> Срабатывает 1 раз -> Удаляется.
RECIPE_PLOT_SCENE = ArchetypeRecipe(
    archetype_id="ARCH_PLOT_SCENE",
    description="Latent event waiting for specific conditions to release an instant impulse.",
    layers_config=[
        # 1. Триггер (Сенсор)
        # Ждет вектора (Информации, Времени или Движения).
        # Пока Integrity триггера > 0, импульс не проходит дальше.
        # Как только условие выполнено (Trigger Saturate), слой "ломается".
        (plot_trig_interaction, "Trigger", SemanticVector(cog_information=1.0, vit_perception=0.5)),
        
        # 2. Событие (Начинка)
        # Мгновенный выброс энергии/информации.
        # Это "Payload" сюжета.
        (plot_event_revelation, "Climax", SemanticVector(cog_information=2.0, soc_stratification=1.0))
    ]
)

# --- 2. Квест / Проект (ARCH_PLOT_QUEST) ---
# Использование: "Убить 10 крыс", "Построить храм", "Расследовать убийство".
# Логика: Вход (взять квест) -> Тело (прогресс-бар) -> Финал (награда).
# Жизненный цикл: Активен долго. Игрок "бьет" его своими действиями (Kinetics/Utility).
RECIPE_PLOT_QUEST = ArchetypeRecipe(
    archetype_id="ARCH_PLOT_QUEST",
    description="Progress-based entity requiring cumulative effort to complete.",
    layers_config=[
        # 1. Условие старта (Триггер)
        # Чтобы получить квест, нужно поговорить (Interaction) или найти предмет.
        (plot_trig_interaction, "Quest Giver", SemanticVector(soc_reciprocity=1.0)),
        
        # 2. Тело Квеста (Процесс)
        # Имеет высокое Integrity (например, 100 HP).
        # Игрок наносит "урон" выполнением задач.
        # Если Integrity упадет до 0 -> Квест выполнен.
        (plot_proc_task, "Progress Bar", SemanticVector(mat_integrity=10.0, cog_complexity=1.0)),
        
        # 3. Награда (Событие завершения)
        # Срабатывает, когда разрушен слой Процесса.
        # Выдает опыт, лут или меняет отношение фракций.
        (plot_event_revelation, "Completion Reward", SemanticVector(mat_fungibility=5.0, sys_skill=1.0))
    ]
)

# --- 3. Хроника / Бедствие (ARCH_PLOT_CHRONICLE) ---
# Использование: Таймер до взрыва, Эпидемия, Сезон дождей, Война фракций.
# Логика: Работает само по себе (Time Decay).
# Жизненный цикл: "Гниет" со временем или наносит урон каждый ход.
RECIPE_PLOT_CHRONICLE = ArchetypeRecipe(
    archetype_id="ARCH_PLOT_CHRONICLE",
    description="Time-dependent entity that exerts pressure or decays over duration.",
    layers_config=[
        # 1. Таймер / Живучесть (Процесс)
        # Integrity убывает каждый ход (Time Tick).
        # Или убывает от контр-мер игрока (Лекарство против Чумы).
        (plot_proc_calamity, "Duration", SemanticVector(mat_perishability=10.0, vit_toxin=1.0)),
        
        # 2. Эффект (Событие при завершении или в процессе)
        # Если это таймер бомбы -> Взрыв (Disaster).
        # Если это эпидемия -> Слой Process сам генерирует Reactivity каждый ход.
        (plot_event_disaster, "Consequence", SemanticVector(phys_kinetics=5.0, mat_thermal=5.0))
    ]
)
