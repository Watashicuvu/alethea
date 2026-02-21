from src.models.new_schemas import MolecularDefinition

# ==========================================
# ДОМЕН: AGENTS -> LAYER: SHELLS (ОБОЛОЧКИ)
# ==========================================

# --- 1. Мягкая Биологическая Оболочка (ARCH_SHELL_BIO) ---
# Примеры: Кожа, Мышцы, Слизь, Мембрана.
# Особенность: Способна к самовосстановлению (Healing), пропускает урон через боль.
shell_bio_soft = MolecularDefinition(
    name_id="shell_bio_soft",
    description="Living tissue that relies on metabolic resilience.",
    
    # CONDUCTANCE (ВХОД): С чем взаимодействует?
    # - Кинетика (Удары)
    # - Острота (Порезы)
    # - Температура (Ожоги)
    # - Токсины (Через Resilience, если отравлено)
    conductance_axes={
        "phys_kinetics", 
        "mat_acuity", 
        "mat_thermal", 
        "vit_resilience" # Для ядов и болезней
    },

    # STABILITY (СТОЙКОСТЬ): За счет чего существует?
    # Держится на Резистентности (Здоровье) и Метаболизме (Питание тканей).
    stability_axes={
        "vit_resilience",  # HP существа
        "vit_metabolism"   # Регенерация
    },

    # REACTIVITY (ВЫХОД): Реакция на разрушение.
    # При пробитии вызывает боль (Drive) и тратит ресурсы организма.
    reactivity_axes={
        "vit_drive",       # Боль/Паника
        "mat_utility"      # Потеря функциональности (рана мешает)
    }
)

# --- 2. Жесткая Структурная Оболочка (ARCH_SHELL_RIGID) ---
# Примеры: Хитин, Костяные наросты, Латы (как часть экипировки агента), Чешуя дракона.
# Особенность: Не регенерирует (или очень медленно), работает как жесткий вычет урона.
shell_rigid = MolecularDefinition(
    name_id="shell_rigid",
    description="Hardened material barrier driven by density and structural integrity.",

    # CONDUCTANCE:
    # Жесткая броня хорошо гасит "Остроту" (Acuity), но передает "Кинетику" (Kinetics).
    conductance_axes={
        "phys_kinetics", # Дробящий урон проходит
        "mat_acuity",    # Режущий останавливается
        "mat_thermal"    # Нагревается
    },

    # STABILITY:
    # Зависит только от физических параметров материала.
    stability_axes={
        "mat_integrity", # Прочность (HP предмета/панциря)
        "mat_density"    # Плотность (Броня)
    },

    # REACTIVITY:
    # При разрушении создает осколки или превращается в лом (Scrap).
    reactivity_axes={
        "mat_integrity", # Потеря защиты
        "phys_kinetics"  # Рикошет или осколки
    }
)

# --- 3. Эфирный/Магический Барьер (ARCH_SHELL_ETHER) ---
# Примеры: Магический щит, Призрачная форма, Ментальный блок.
# Особенность: Игнорирует физику, пока есть "Мана" (Abstraction).
shell_etheric = MolecularDefinition(
    name_id="shell_etheric",
    description="Energy field sustained by cognitive abstraction or magic.",

    # CONDUCTANCE:
    # Может реагировать на все, но через призму магии.
    conductance_axes={
        "cog_abstraction", # Магические атаки
        "phys_kinetics",   # Физические атаки (если барьер физический)
        "mat_thermal"      # Энергия
    },

    # STABILITY:
    # Держится на сложности заклинания и силе абстракции.
    stability_axes={
        "cog_abstraction", # Мана / Сила воли
        "cog_complexity"   # Сложность структуры щита
    },

    # REACTIVITY:
    # При схлопывании вызывает ментальный шок или взрыв энергии.
    reactivity_axes={
        "cog_determinism", # Ступор / Дезориентация
        "mat_thermal"      # Выброс энергии
    }
)

# --- 4. Социальная Броня / Догма (ARCH_SHELL_SOCIAL) ---
# Примеры: Бюрократия, Религиозный фанатизм, Кодекс чести, Репутация.
# Особенность: Защищает Группировку от информационных и социальных атак.
shell_social = MolecularDefinition(
    name_id="shell_social",
    description="Ideological or bureaucratic barrier protecting the collective mind.",

    # CONDUCTANCE:
    # Атакуется информацией (ложь), эстетикой (сатира) или чужой идеологией.
    conductance_axes={
        "cog_information",  # Аргументы / Пропаганда
        "soc_permeability", # Попытки инфильтрации
        "soc_aesthetics"    # Высмеивание / Символы
    },

    # STABILITY:
    # Держится на сплоченности, догмах и централизации власти.
    stability_axes={
        "soc_cohesion",     # Единство толпы
        "cog_dogmatism",    # Вера в правоту
        "soc_centralization" # Жесткость иерархии
    },

    # REACTIVITY:
    # При разрушении догмы начинается хаос или распад группы.
    reactivity_axes={
        "soc_stratification", # Революция / Смена классов
        "soc_cohesion"        # Разбегание сторонников
    }
)

# ==========================================
# ДОМЕН: AGENTS -> LAYER: CORES (ЯДРА)
# ==========================================

# --- 1. Живое Сердце (ARCH_CORE_BIO) ---
# Универсальный движок для животных, людей, монстров.
# Держится на метаболизме и здоровье.
core_bio_vital = MolecularDefinition(
    name_id="core_bio_vital",
    description="Biological engine converting nutrients into vital energy.",
    
    # CONDUCTANCE (ВХОД):
    # Ядро уязвимо к:
    # 1. Физике (phys_kinetics) — если оболочка пробита (критический удар).
    # 2. Температуре (mat_thermal) — перегрев/замерзание.
    # 3. Зависимости (vit_dependency) — голод, жажда, потребность в кислороде.
    conductance_axes={
        "phys_kinetics", 
        "mat_thermal", 
        "vit_dependency" 
    },

    # STABILITY (СТОЙКОСТЬ):
    # Агент жив, пока есть Resilience (HP) и работает Metabolism.
    stability_axes={
        "vit_resilience",  # Текущее здоровье (Health)
        "vit_metabolism"   # Способность поддерживать жизнь
    },

    # REACTIVITY (ВЫХОД):
    # Смерть (распад ядра) вызывает:
    # 1. Гниение (mat_perishability).
    # 2. Сброс инстинктов/драйва (vit_drive) — предсмертная агония или паника.
    reactivity_axes={
        "mat_perishability", # Труп
        "vit_drive"          # Последний рывок / Агония
    }
)

# --- 2. Эфирное/Магическое Ядро (ARCH_CORE_ETHERIC) ---
# Движок для элементалей, призраков, магических конструктов.
# Держится на мане и сложности заклинания.
core_cog_etheric = MolecularDefinition(
    name_id="core_cog_etheric",
    description="Abstract core sustained by willpower or magical currents.",

    # CONDUCTANCE:
    # Уязвимо к:
    # 1. Развеиванию магии (cog_abstraction).
    # 2. Информационным парадоксам (cog_information).
    # 3. Физике (phys_kinetics) — только если нет иммунитета (через вектора).
    conductance_axes={
        "cog_abstraction", # Магическая атака / Антимагия
        "cog_information", # Истинное Имя / Нарушение контракта
        "phys_kinetics"    # Разрушение якоря в реальном мире
    },

    # STABILITY:
    # Существует за счет концентрации маны и сложности структуры.
    stability_axes={
        "cog_abstraction", # Запас маны
        "cog_complexity"   # Сложность формулы жизни
    },

    # REACTIVITY:
    # Смерть вызывает:
    # 1. Выброс маны (cog_abstraction).
    # 2. Детерминированный коллапс (cog_determinism) — исчезновение или превращение в камень.
    reactivity_axes={
        "cog_abstraction", # Взрыв маны
        "cog_determinism"  # Возврат к неживой материи
    }
)

# --- 3. Власть / Лидерство (ARCH_CORE_AUTHORITY) ---
# "Ядро" для социальных агентов (Группировка, Культ, Корпорация).
# Это Лидер или Совет. Если его убрать — группа распадается.
core_soc_authority = MolecularDefinition(
    name_id="core_soc_authority",
    description="Social center of gravity holding a group together.",

    # CONDUCTANCE:
    # Уязвимо к:
    # 1. Интригам/Компромату (cog_information).
    # 2. Подкупу/Предательству (soc_reciprocity).
    # 3. Потере статуса (soc_stratification).
    conductance_axes={
        "cog_information",    # Слухи, шантаж
        "soc_reciprocity",    # Коррупция
        "soc_stratification"  # Вызов на дуэль / Смещение
    },

    # STABILITY:
    # Держится на Централизации (Власть) и Агентности (Воля лидера).
    stability_axes={
        "soc_centralization", # Легитимность власти
        "cog_agency"          # Способность принимать решения
    },

    # REACTIVITY:
    # Падение лидера вызывает:
    # 1. Децентрализацию (Хаос).
    # 2. Потерю сплоченности (soc_cohesion).
    reactivity_axes={
        "soc_centralization", # Анархия
        "soc_cohesion"        # Гражданская война / Распад
    }
)

# --- 4. Казна / Ресурсная База (ARCH_CORE_TREASURY) ---
# Экономическое сердце организации или "аккумулятор" робота/голема.
# Существует, пока есть ресурс.
core_mat_resource = MolecularDefinition(
    name_id="core_mat_resource",
    description="Accumulation of fungible resources ensuring survival.",

    # CONDUCTANCE:
    # Истощается через:
    # 1. Траты/Потребление (mat_utility).
    # 2. Кражу/Инфляцию (mat_fungibility).
    # 3. Рыночные изменения (mat_scarcity).
    conductance_axes={
        "mat_utility",      # Расходы на содержание
        "mat_fungibility",  # Воровство
        "mat_scarcity"      # Внешний кризис
    },

    # STABILITY:
    # Живет, пока есть Дефицит (Ценность) и Запас.
    stability_axes={
        "mat_scarcity",    # Наличие ценного ресурса
        "mat_fungibility"  # Ликвидность
    },

    # REACTIVITY:
    # При разрушении (банкротстве/разбитии) ресурсы выпадают.
    reactivity_axes={
        "mat_fungibility", # Лут (Loot Drop)
        "soc_stratification" # Потеря влияния из-за бедности
    }
)

# ==========================================
# ДОМЕН: AGENTS -> LAYER: ACTUATORS (ИНСТРУМЕНТЫ)
# ==========================================

# --- 1. Ударный Инструмент (ARCH_ACTUATOR_STRIKER) ---
# Примеры: Меч, Дубина, Кулак, Топор.
# Суть: Трансформирует энергию движения в физический урон.
actuator_phys_striker = MolecularDefinition(
    name_id="actuator_phys_striker",
    description="Melee implement designed to deliver kinetic or acute trauma.",

    # CONDUCTANCE (ВХОД):
    # Как инструмент взаимодействует с целью при контакте?
    # - Кинетика (Сила удара)
    # - Плотность (Масса оружия влияет на пробитие)
    conductance_axes={
        "phys_kinetics", # Импульс
        "mat_density"    # Тяжесть/Инерция
    },

    # STABILITY (СТОЙКОСТЬ):
    # Инструмент ломается от использования.
    # - Integrity: Прочность (клинок может сломаться).
    # - Acuity: Заточка (клинок может затупиться).
    stability_axes={
        "mat_integrity", # Прочность материала
        "mat_acuity"     # Острота кромки
    },

    # REACTIVITY (ВЫХОД):
    # Какой эффект наносится цели?
    # - Kinetics: Отбрасывание / Дробление костей.
    # - Acuity: Разрезание тканей / Кровотечение.
    reactivity_axes={
        "phys_kinetics", # Дробящий урон
        "mat_acuity"     # Режущий урон
    }
)

# --- 2. Дальнобойный / Проектор (ARCH_ACTUATOR_PROJECTOR) ---
# Примеры: Лук, Пистолет, Магический посох (стреляющий болтами).
# Суть: Запускает снаряд или луч. Сам инструмент не касается врага.
actuator_phys_projector = MolecularDefinition(
    name_id="actuator_phys_projector",
    description="Mechanism for launching projectiles or directing energy beams.",

    # CONDUCTANCE (ВХОД):
    # Требует навыка и настройки.
    # - Perception: Прицеливание.
    # - Complexity: Сложность перезарядки/механизма.
    conductance_axes={
        "vit_perception", # Точность наведения
        "cog_complexity"  # Механика стрельбы
    },

    # STABILITY (СТОЙКОСТЬ):
    # Изнашивается сам механизм.
    stability_axes={
        "mat_integrity", # Состояние механизма
        "mat_thermal"    # Перегрев (для огнестрела/магии)
    },

    # REACTIVITY (ВЫХОД):
    # Создает вектор ускорения для снаряда (Payload).
    # Сам актуатор урон не наносит, он разгоняет "пулю".
    reactivity_axes={
        "phys_kinetics", # Начальная скорость снаряда
        "mat_thermal"    # Дульная вспышка / Выстрел
    }
)

# --- 3. Естественное Оружие (ARCH_ACTUATOR_NATURAL) ---
# Примеры: Клыки, Когти, Рога, Шипы.
# Суть: Часть тела. Если сломается — больно самому агенту.
actuator_bio_natural = MolecularDefinition(
    name_id="actuator_bio_natural",
    description="Biological appendage evolved for combat.",

    # CONDUCTANCE:
    # Зависит от силы мышц и драйва (ярости).
    conductance_axes={
        "phys_kinetics", # Мышечная сила
        "vit_drive"      # Агрессия (чем злее, тем сильнее кусает)
    },

    # STABILITY:
    # В отличие от меча, здесь Stability = Здоровье агента.
    # Поломка когтя = потеря Resilience.
    stability_axes={
        "vit_resilience", # Живая ткань
        "mat_integrity"   # Структура кости/хитина
    },

    # REACTIVITY:
    # Обычно это разрыв тканей (Acuity) или захват.
    reactivity_axes={
        "mat_acuity",    # Глубокие раны
        "vit_dependency" # Вампиризм / Поедание (опционально через вектора)
    }
)

# --- 4. Социальный Манипулятор (ARCH_ACTUATOR_VOICE) ---
# Примеры: Голос, Печать, Скипетр, Дипломатическая нота.
# Суть: Инструмент проецирования воли (Power Projection).
actuator_soc_voice = MolecularDefinition(
    name_id="actuator_soc_voice",
    description="Instrument of social influence and information dissemination.",

    # CONDUCTANCE:
    # Работает с информацией и статусом.
    conductance_axes={
        "cog_information", # Смысл слов
        "soc_aesthetics"   # Харизма / Внешний вид
    },

    # STABILITY:
    # Держится на авторитете и догмах.
    # Если вас "переспорили", ваш инструмент (голос) теряет силу.
    stability_axes={
        "soc_stratification", # Статус говорящего
        "cog_dogmatism"       # Уверенность в правоте
    },

    # REACTIVITY:
    # Наносит "урон" по лояльности или убеждениям цели.
    reactivity_axes={
        "soc_reciprocity", # Принуждение к сделке
        "soc_cohesion"     # Вдохновение (бафф) или Раскол (дебафф)
    }
)

# ==========================================
# ДОМЕН: OBJECTS -> LAYER: STRUCTURE (КАРКАС)
# ==========================================

# --- 1. Монолит / Преграда (ARCH_MAT_OBSTACLE) ---
# Примеры: Каменная стена, Скала, Ствол дерева, Статуя.
# Суть: Объект, чья главная функция — занимать место и блокировать движение.
mat_struct_obstacle = MolecularDefinition(
    name_id="mat_struct_obstacle",
    description="Immovable dense structure acting as a physical barrier.",

    # CONDUCTANCE (ВХОД):
    # Как разрушить стену?
    # - Кинетика (Таран, Взрыв).
    # - Термика (Огонь для дерева, плавление для камня).
    # - Акуити (Бур, Кирка).
    conductance_axes={
        "phys_kinetics", 
        "mat_thermal", 
        "mat_acuity"
    },

    # STABILITY (СТОЙКОСТЬ):
    # Держится на массе и целостности.
    # Если Density высокая, объект почти невозможно сдвинуть.
    stability_axes={
        "mat_density",    # Масса / Устойчивость
        "mat_integrity"   # Прочность материала
    },

    # REACTIVITY (ВЫХОД):
    # При разрушении превращается в руины/мусор.
    # Это создает "Сложный ландшафт" (Terrain).
    reactivity_axes={
        "mat_density",    # Обломки (препятствие поменьше)
        "phys_kinetics"   # Обрушение (урон тем, кто рядом)
    }
)

# --- 2. Контейнер / Оболочка (ARCH_MAT_CONTAINER) ---
# Примеры: Бутылка зелья, Сундук, Сейф, Бочка.
# Суть: Полая структура, защищающая Payload (Начинку).
mat_struct_container = MolecularDefinition(
    name_id="mat_struct_container",
    description="Hollow structure designed to house and protect a payload.",

    # CONDUCTANCE (ВХОД):
    # Контейнеры часто ломают или вскрывают.
    # - Кинетика (Разбить бутылку).
    # - Акуити (Вскрыть замок / Разрезать мешок).
    conductance_axes={
        "phys_kinetics",
        "mat_acuity"
    },

    # STABILITY (СТОЙКОСТЬ):
    # Обычно ниже, чем у Монолита.
    # Важен параметр Integrity (насколько легко разбить).
    stability_axes={
        "mat_integrity", 
        "mat_portability" # Можно ли унести контейнер с собой?
    },

    # REACTIVITY (ВЫХОД):
    # Самое важное: при разрушении каркаса высвобождается содержимое (Payload).
    # Сам каркас становится мусором (Scrap).
    reactivity_axes={
        "mat_integrity"   # Исчезновение преграды
        # Payload активируется логикой полимера, а не самой молекулой каркаса
    }
)

# --- 3. Предмет / Тело Инструмента (ARCH_MAT_ITEM_BODY) ---
# Примеры: Лежащий меч, Книга, Монета, Слиток.
# Суть: Объект, который можно поднять и использовать. У него нет "внутри" и "снаружи", он цельный.
mat_struct_item = MolecularDefinition(
    name_id="mat_struct_item",
    description="Portable object body capable of being equipped or traded.",

    # CONDUCTANCE (ВХОД):
    # Взаимодействие через поднятие (Portability) или уничтожение.
    conductance_axes={
        "mat_portability", # Взять в инвентарь
        "mat_thermal",     # Расплавить
        "phys_kinetics"    # Сломать
    },

    # STABILITY (СТОЙКОСТЬ):
    stability_axes={
        "mat_integrity",   # Целостность
        "mat_density"      # Вес (влияет на возможность переноски)
    },

    # REACTIVITY (ВЫХОД):
    # Предметы часто являются ресурсами.
    reactivity_axes={
        "mat_fungibility", # Ценность (Лом/Материалы)
        "soc_aesthetics"   # Потеря красоты при поломке
    }
)

# ==========================================
# ДОМЕН: OBJECTS -> LAYER: ENGINE (МЕХАНИЗМ)
# ==========================================

# --- 1. Активный Конвертер / Двигатель (ARCH_ENG_CONVERTER) ---
# Примеры: Паровой котел, ДВС, Магический реактор, Печь.
# Суть: Потребляет расходуемый ресурс (Fuel) и генерирует работу/эффект.
mat_engine_converter = MolecularDefinition(
    name_id="mat_engine_converter",
    description="Active system that consumes fuel to generate kinetic or thermal energy.",

    # CONDUCTANCE (ВХОД):
    # Что нужно для работы?
    # - Utility: Топливо (уголь, бензин).
    # - Thermal: Искра/Нагрев для старта.
    # - Abstraction: Мана (если это магический движок).
    conductance_axes={
        "mat_utility",      # Потребление ресурса (Fuel)
        "mat_thermal",      # Температура запуска
        "cog_abstraction"   # Магическое топливо
    },

    # STABILITY (СТОЙКОСТЬ):
    # Двигатели хрупки и могут перегреться.
    stability_axes={
        "mat_integrity", # Механическая целостность (износ)
        "mat_thermal"    # Теплоемкость (порог перегрева)
    },

    # REACTIVITY (ВЫХОД):
    # Что производит?
    # - Kinetics: Движение поршней/колес.
    # - Thermal: Тепло (для печи или как побочный эффект).
    reactivity_axes={
        "phys_kinetics", # Тяга / Вращение
        "mat_thermal"    # Выделение тепла
    }
)

# --- 2. Трансмиссия / Механика (ARCH_ENG_MECHANISM) ---
# Примеры: Шестеренки часов, Рычаг, Пружина капкана, Дверная ручка.
# Суть: Не сжигает топливо, а преобразует/хранит входящую кинетику.
mat_engine_mechanism = MolecularDefinition(
    name_id="mat_engine_mechanism",
    description="Passive mechanical system for transferring or storing kinetic load.",

    # CONDUCTANCE (ВХОД):
    # Принимает усилие извне.
    # - Kinetics: Кто-то крутит ручку или взводит пружину.
    # - Complexity: Требует правильного обращения (взлом замка).
    conductance_axes={
        "phys_kinetics",  # Входящая сила (Torque)
        "cog_complexity"  # Секрет механизма (Lockpicking)
    },

    # STABILITY (СТОЙКОСТЬ):
    # Ломается от перенапряжения или ржавчины.
    stability_axes={
        "mat_integrity", # Прочность деталей
        "mat_density"    # Трение / Сопротивление материала
    },

    # REACTIVITY (ВЫХОД):
    # Передает усилие на Актуатор или Интерфейс.
    reactivity_axes={
        "phys_kinetics", # Преобразованное движение (открытие двери, удар капкана)
        "mat_acuity"     # Щелчок / Срабатывание (Trigger)
    }
)

# ==========================================
# ДОМЕН: OBJECTS -> LAYER: PAYLOAD (НАПОЛНЕНИЕ)
# ==========================================

# --- 1. Нестабильная Субстанция (ARCH_PAYLOAD_VOLATILE) ---
# Примеры: Порох, Напалм, Кислота, Ядовитый газ.
# Суть: Вещество, готовое к бурному высвобождению энергии.
mat_payload_volatile = MolecularDefinition(
    name_id="mat_payload_volatile",
    description="Unstable matter capable of rapid energetic expansion or chemical reaction.",

    # CONDUCTANCE (ВХОД):
    # Триггеры детонации:
    # - Thermal: Огонь (запал).
    # - Kinetics: Удар (детонатор).
    # - Integrity: Если контейнер разрушен, вещество реагирует с воздухом.
    conductance_axes={
        "mat_thermal",      # Нагрев
        "phys_kinetics",    # Сотрясение
        "mat_integrity"     # Нарушение изоляции
    },

    # STABILITY (СТОЙКОСТЬ):
    # Обычно низкая. Вещество "хочет" взорваться.
    stability_axes={
        "mat_integrity",    # Химическая стабильность
        "mat_perishability" # Срок годности (динамит "потеет")
    },

    # REACTIVITY (ВЫХОД):
    # Эффект при срабатывании (Вектор Взрыва):
    # - Thermal: Ожоги.
    # - Kinetics: Ударная волна.
    # - Toxin: (через Resilience в векторе) Отравление.
    reactivity_axes={
        "mat_thermal",      # Огонь
        "phys_kinetics",    # Взрыв
        "mat_acuity"        # Осколки (если контейнер был жестким)
    }
)

# --- 2. Полезный Ресурс (ARCH_PAYLOAD_RESOURCE) ---
# Примеры: Зелье лечения, Вода, Еда, Топливо.
# Суть: Материя, которую можно потребить (Consume) для восстановления статов Агента.
mat_payload_resource = MolecularDefinition(
    name_id="mat_payload_resource",
    description="Consumable matter providing utility or vital restoration.",

    # CONDUCTANCE (ВХОД):
    # Как использовать?
    # - Utility: Использование по назначению (выпить/съесть).
    # - Thermal: Можно сварить/заморозить (изменяет свойства).
    conductance_axes={
        "mat_utility",      # Активация потребления
        "mat_thermal"       # Готовка / Порча
    },

    # STABILITY (СТОЙКОСТЬ):
    # Еда гниет, зелья выдыхаются.
    stability_axes={
        "mat_perishability", # Таймер гниения
        "mat_density"        # Вязкость (жидкость вытекает без контейнера)
    },

    # REACTIVITY (ВЫХОД):
    # Эффект на потребителя:
    # - Resilience: Лечение.
    # - Metabolism: Насыщение.
    # - Drive: Стимуляторы (бафф скорости/агрессии).
    reactivity_axes={
        "vit_resilience",    # Heal
        "vit_metabolism",    # Feed
        "vit_drive"          # Buff
    }
)

# --- 3. Ценность / Лут (ARCH_PAYLOAD_TREASURE) ---
# Примеры: Золотые монеты, Драгоценные камни, Данные (Information).
# Суть: Не имеет функционального применения (не стреляет, не лечит), но имеет меновую стоимость.
mat_payload_treasure = MolecularDefinition(
    name_id="mat_payload_treasure",
    description="Matter valued for its scarcity or fungibility.",

    # CONDUCTANCE (ВХОД):
    # Взаимодействие через торговлю или оценку.
    conductance_axes={
        "mat_fungibility",  # Обмен
        "soc_aesthetics"    # Оценка красоты
    },

    # STABILITY (СТОЙКОСТЬ):
    # Золото вечно, данные могут исказиться.
    stability_axes={
        "mat_integrity",    # Физическая сохранность
        "mat_scarcity"      # Редкость (поддерживает цену)
    },

    # REACTIVITY (ВЫХОД):
    # Влияет на социальный статус владельца.
    reactivity_axes={
        "mat_fungibility",  # Прирост богатства
        "soc_stratification" # Престиж
    }
)

# ==========================================
# ДОМЕН: OBJECTS -> LAYER: INTERFACE (ИНТЕРФЕЙС)
# ==========================================

# --- 1. Рукоять / Крепление (ARCH_INT_GRIP) ---
# Примеры: Эфес меча, Ручка чемодана, Ремни рюкзака.
# Суть: Позволяет Агенту объединить свой вектор перемещения с вектором объекта.
mat_int_grip = MolecularDefinition(
    name_id="mat_int_grip",
    description="Ergonomic adapter allowing an agent to wield or carry the object.",

    # CONDUCTANCE (ВХОД):
    # Насколько удобно держать?
    # - Portability: Эргономика (удобная ручка повышает эффективность).
    # - Utility: Специализация (двуручный хват, крепление на пояс).
    conductance_axes={
        "mat_portability", # Удобство переноски
        "mat_utility"      # Функциональное соответствие руке
    },

    # STABILITY (СТОЙКОСТЬ):
    # Рукоять может сломаться или стать скользкой.
    stability_axes={
        "mat_integrity",   # Прочность соединения
        "mat_density"      # Баланс веса
    },

    # REACTIVITY (ВЫХОД):
    # Передает кинетику от Агента к Предмету без потерь.
    reactivity_axes={
        "phys_kinetics"    # Передача импульса
    }
)

# --- 2. Элемент Управления / Триггер (ARCH_INT_CONTROL) ---
# Примеры: Спусковой крючок, Рычаг, Кнопка, Замочная скважина.
# Суть: Преобразует малое усилие (или навык) в сигнал для Механизма (Engine).
mat_int_control = MolecularDefinition(
    name_id="mat_int_control",
    description="Input device transforming agent intent into mechanical signal.",

    # CONDUCTANCE (ВХОД):
    # Требует либо силы, либо ума.
    # - Kinetics: Нажатие (кнопка).
    # - Complexity: Взлом замка или ввод пароля.
    conductance_axes={
        "phys_kinetics",   # Физический ввод
        "cog_complexity"   # Интеллектуальный ввод (Puzzle/Lock)
    },

    # STABILITY (СТОЙКОСТЬ):
    # Замки ломаются, кнопки заедают.
    stability_axes={
        "mat_integrity",   # Исправность
        "cog_determinism"  # Надежность срабатывания (без глюков)
    },

    # REACTIVITY (ВЫХОД):
    # Генерирует управляющий сигнал для Engine.
    reactivity_axes={
        "cog_information", # Логический сигнал (Открыть/Закрыть)
        "mat_acuity"       # Механический щелчок (спуск бойка)
    }
)

# --- 3. Информационный Дисплей (ARCH_INT_DISPLAY) ---
# Примеры: Экран радара, Страница книги, Карта, Руны на мече.
# Суть: Пассивный интерфейс, передающий информацию Агенту.
mat_int_display = MolecularDefinition(
    name_id="mat_int_display",
    description="Surface designed to convey visual or tactile information.",

    # CONDUCTANCE (ВХОД):
    # Чтобы "считать" интерфейс, нужно восприятие и знание языка.
    conductance_axes={
        "vit_perception",  # Увидеть/Прочитать
        "cog_information"  # Понять (Lore check)
    },

    # STABILITY (СТОЙКОСТЬ):
    # Страницы рвутся, экраны бьются, чернила выцветают.
    stability_axes={
        "mat_integrity",   # Целостность носителя
        "cog_information"  # Читаемость текста (Accuracy)
    },

    # REACTIVITY (ВЫХОД):
    # Обучение или раскрытие сюжета.
    reactivity_axes={
        "cog_information", # Знание
        "cog_abstraction"  # Магический эффект от прочтения (свиток)
    }
)

# ==========================================
# ДОМЕН: NEXUS -> LAYER: SUBSTRATE (ПОЧВА)
# ==========================================

# --- 1. Ландшафтная Основа (ARCH_TOPO_SUBSTRATE) ---
# Примеры: Твердая земля, Болото, Ледяной каток, Зыбучие пески.
# Суть: Определяет стоимость передвижения (Movement Cost) и опору.
topo_sub_terrain = MolecularDefinition(
    name_id="topo_sub_terrain",
    description="Physical medium providing support and friction for movement.",

    # CONDUCTANCE (ВХОД):
    # Агент воздействует на землю весом и движением.
    # - Kinetics: Попытка пройти.
    # - Density: Давление массы агента на поверхность.
    conductance_axes={
        "phys_kinetics", # Вектор движения агента
        "mat_density"    # Вес агента (важно для зыбучих песков/льда)
    },

    # STABILITY (СТОЙКОСТЬ):
    # Обычно ландшафт неразрушим (Integrity = Infinite), 
    # но может меняться (лед тает -> Thermal).
    stability_axes={
        "mat_density",   # Плотность поверхности
        "mat_thermal"    # Агрегатное состояние (Грязь/Камень)
    },

    # REACTIVITY (ВЫХОД):
    # Возвращает модификатор движения.
    # - Kinetics: Трение (отрицательная кинетика = замедление).
    # - Resilience: Урон (лаза, кислотная лужа).
    reactivity_axes={
        "phys_kinetics", # Трение / Скольжение
        "vit_resilience" # Экологический урон (Environmental Damage)
    }
)

# ==========================================
# ДОМЕН: NEXUS -> LAYER: ATMOSPHERE (ПОЛЕ)
# ==========================================

# --- 2. Физическая Среда (ARCH_TOPO_ATMOSPHERE_PHYS) ---
# Примеры: Радиация, Экстремальный холод, Токсичный туман, Невесомость.
# Суть: Пассивный эффект, накладываемый на физику/тело каждый тик.
topo_atmo_phys = MolecularDefinition(
    name_id="topo_atmo_phys",
    description="Ambient physical conditions affecting all entities in the locus.",

    # CONDUCTANCE (ВХОД):
    # Что защищает от среды?
    # - Resilience: Иммунитет / Здоровье.
    # - Integrity: Броня / Герметичность (для роботов).
    conductance_axes={
        "vit_resilience", # Сопротивление организма
        "mat_integrity"   # Сопротивление экипировки
    },

    # STABILITY (СТОЙКОСТЬ):
    # Плотность тумана или сила шторма.
    # Может быть развеяно сильным ветром (Kinetics).
    stability_axes={
        "mat_density",   # Концентрация вещества в воздухе
        "phys_kinetics"  # Ветровая нагрузка
    },

    # REACTIVITY (ВЫХОД):
    # Чем бьет среда?
    # - Thermal: Температурный урон.
    # - Resilience: Токсичный урон.
    reactivity_axes={
        "mat_thermal",    # Freeze / Burn
        "vit_resilience"  # Poison / Rot
    }
)

# --- 3. Психо-Социальная Аура (ARCH_TOPO_ATMOSPHERE_MENTAL) ---
# Примеры: Святая земля (умиротворение), Дом с привидениями (страх), Офис (бюрократия).
# Суть: Ментальное давление на волю и эмоции.
topo_atmo_mental = MolecularDefinition(
    name_id="topo_atmo_mental",
    description="Cognitive or social field influencing behavior and morale.",

    # CONDUCTANCE (ВХОД):
    # Что защищает разум?
    # - Dogmatism: Сила убеждений.
    # - Cohesion: Чувство локтя (группа меньше боится).
    conductance_axes={
        "cog_dogmatism", # Mental Resistence
        "soc_cohesion"   # Social Support
    },

    # STABILITY (СТОЙКОСТЬ):
    # Держится на абстракции (магия) или авторитете (символы власти).
    stability_axes={
        "cog_abstraction", # Магическая поддержка ауры
        "soc_aesthetics"   # Атмосфера величия/ужаса
    },

    # REACTIVITY (ВЫХОД):
    # Эффект:
    # - Drive: Страх (снижает инициативу) или Ярость.
    # - Determinism: Ступор / Подчинение правилам.
    reactivity_axes={
        "vit_drive",       # Fear / Courage Buff
        "cog_determinism"  # Control / Confusion
    }
)

# ==========================================
# ДОМЕН: NEXUS -> LAYER: GATEWAY (ШЛЮЗ)
# ==========================================

# --- 4. Точка Перехода (ARCH_TOPO_GATE) ---
# Примеры: Дверь, Пещерный проход, Телепорт, Таможенный пост.
# Суть: Условный оператор (IF condition THEN move), регулирующий связь графа.
topo_gate_generic = MolecularDefinition(
    name_id="topo_gate_generic",
    description="Transition point controlling access between loci.",

    # CONDUCTANCE (ВХОД):
    # Ключ к проходу.
    # - Kinetics: Просто пройти (если открыто) или выломать.
    # - Information: Пароль / Ключ-карта.
    # - Permeability: Социальный допуск (фейс-контроль).
    conductance_axes={
        "phys_kinetics",  # Movement attempt
        "cog_information", # Auth / Key
        "soc_permeability" # Social Access (Friend/Foe)
    },

    # STABILITY (СТОЙКОСТЬ):
    # Насколько сложно заблокировать или разрушить проход.
    stability_axes={
        "mat_integrity",   # Физическая прочность двери
        "cog_complexity"   # Сложность магического замка
    },

    # REACTIVITY (ВЫХОД):
    # - Kinetics: Перемещение (успех) или Отбрасывание (провал).
    # - Thermal: Урон (защитное поле).
    reactivity_axes={
        "phys_kinetics", # Teleport / Move vector
        "mat_thermal"    # Zap damage (trap)
    }
)

# ==========================================
# ДОМЕН: PLOT -> LAYER: TRIGGER (УСЛОВИЕ)
# ==========================================

# --- 1. Сюжетный Триггер / Детектор (ARCH_PLOT_TRIGGER) ---
# Примеры: "Начало бунта (если голод > 90)", "Появление босса (если убиты миньоны)".
# Суть: Пассивный сенсор, который ждет накопления определенного вектора в Локусе.
plot_trigger_condition = MolecularDefinition(
    name_id="plot_trigger_condition",
    description="Contextual sensor that activates a linked event when thresholds are met.",

    # CONDUCTANCE (ВХОД):
    # Что мониторит триггер?
    # - Scarcity: Кризис ресурсов.
    # - Aggression/Drive: Напряжение в обществе.
    # - Information: Сюжетные флаги (знание секрета).
    conductance_axes={
        "mat_scarcity",    # Экономические условия
        "vit_drive",       # Социальное напряжение
        "cog_information"  # Факты/Улики
    },

    # STABILITY (СТОЙКОСТЬ):
    # Триггер существует, пока актуален.
    # Обычно он "вечный" (High Integrity), пока не сработает.
    # Но может быть "забыт" (Information decay), если долго не срабатывает.
    stability_axes={
        "cog_information", # Актуальность условия
        "cog_complexity"   # Сложность условий (цепочка событий)
    },

    # REACTIVITY (ВЫХОД):
    # При активации (Saturate) триггер "ломается" и запускает Событие.
    reactivity_axes={
        "cog_information", # Сигнал запуска (Event Spawn)
        "cog_determinism"  # Изменение правил игры (смена фазы)
    }
)

# ==========================================
# ДОМЕН: PLOT -> LAYER: EVENT (СОБЫТИЕ)
# ==========================================

# --- 2. Мгновенное Событие (ARCH_PLOT_EVENT) ---
# Примеры: Взрыв, Землетрясение, Чудо, Внезапная атака.
# Суть: "Взрывная" сущность. Живет 1 тик. Прикладывает огромный вектор к локации.
plot_event_instant = MolecularDefinition(
    name_id="plot_event_instant",
    description="High-energy transient entity applying an instant vector shift.",

    # CONDUCTANCE (ВХОД):
    # Событие уже запущено, его сложно остановить.
    # Но можно ослабить щитами (Defender).
    conductance_axes={
        "phys_kinetics",   # Попытка сдержать взрыв
        "cog_abstraction"  # Контрмагия
    },

    # STABILITY (СТОЙКОСТЬ):
    # Живет за счет своей энергии.
    # Thermal/Kinetics здесь выступают как "Заряд".
    # Как только заряд передан (Reactivity), Stability падает в 0.
    stability_axes={
        "mat_thermal",     # Энергия события
        "phys_kinetics"    # Импульс
    },

    # REACTIVITY (ВЫХОД):
    # Вектор воздействия на мир.
    # - Damage: Урон всем в локусе.
    # - Panic: Ментальный удар.
    reactivity_axes={
        "phys_kinetics",   # Ударная волна
        "vit_drive",       # Шок/Паника
        "mat_integrity"    # Разрушение структур
    }
)

# ==========================================
# ДОМЕН: PLOT -> LAYER: PROCESS / QUEST (ПРОЦЕСС)
# ==========================================

# --- 3. Длительный Процесс / Квест (ARCH_PLOT_PROCESS) ---
# Примеры: "Эпидемия" (убивает медленно), "Строительство храма" (требует ресурсы), "Квест на убийство крыс".
# Суть: Сущность, протяженная во времени. Имеет полоску прогресса (или HP).
plot_process_quest = MolecularDefinition(
    name_id="plot_process_quest",
    description="Durable narrative entity that progresses or decays over time.",

    # CONDUCTANCE (ВХОД):
    # Что продвигает квест (или лечит эпидемию)?
    # - Utility: Принести ресурсы (стройка).
    # - Kinetics: Убить монстров (боевой квест).
    # - Information: Найти улики (детектив).
    conductance_axes={
        "mat_utility",     # Вклад ресурсами
        "phys_kinetics",   # Вклад действием/боем
        "cog_information"  # Вклад знаниями
    },

    # STABILITY (СТОЙКОСТЬ):
    # За счет чего процесс держится?
    # - Perishability: Таймер (если таймер истек -> провал/конец).
    # - Integrity: "Здоровье" проблемы (нужно свести в 0, чтобы выполнить).
    stability_axes={
        "mat_perishability", # Таймер / Срок жизни события
        "mat_integrity"      # Объем задачи (Quest HP)
    },

    # REACTIVITY (ВЫХОД):
    # Эффект пока идет процесс (Debuff) или награда при завершении (Loot).
    # - Scarcity: Потребляет ресурсы (стройка).
    # - Resilience: Наносит урон (чума).
    # - Fungibility: Награда (золото) при смерти квеста.
    reactivity_axes={
        "mat_scarcity",    # Economic Drain
        "vit_resilience",  # DoT (Damage over Time)
        "mat_fungibility"  # Reward Drop
    }
)

# --- 1. Вязкий / Жидкий Субстрат (ARCH_TOPO_SUB_FLUID) ---
# Примеры: Болото, Глубокий снег, Вода, Зыбучие пески.
# Суть: Чем быстрее двигаешься или чем тяжелее ты, тем сильнее среда сопротивляется.
topo_sub_fluid = MolecularDefinition(
    name_id="topo_sub_fluid",
    description="Viscous medium that resists movement based on velocity and density.",

    # CONDUCTANCE (ВХОД):
    # Среда реагирует на:
    # - Kinetics: Скорость движения (чем быстрее, тем выше сопротивление воды).
    # - Density: Удельный вес (тонет или плавает).
    conductance_axes={
        "phys_kinetics", 
        "mat_density"
    },

    # STABILITY (СТОЙКОСТЬ):
    # Жидкость нельзя "сломать", но можно заморозить/испарить (Thermal).
    stability_axes={
        "mat_thermal",    # Агрегатное состояние
        "mat_density"     # Плотность самой жидкости
    },

    # REACTIVITY (ВЫХОД):
    # - Kinetics: Отрицательный вектор (Замедление / Вязкость).
    # - Perishability: Риск утонуть (если есть механика дыхания) или коррозия.
    reactivity_axes={
        "phys_kinetics",     # Drag force (Замедление)
        "mat_perishability"  # Влажность / Порча снаряжения
    }
)

# --- 2. Агрессивный Субстрат (ARCH_TOPO_SUB_HAZARD) ---
# Примеры: Лава, Кислотная лужа, Пол с шипами, Электрический пол.
# Суть: Поверхность, контакт с которой наносит прямой урон.
topo_sub_hazard = MolecularDefinition(
    name_id="topo_sub_hazard",
    description="Surface that inflicts damage upon physical contact.",

    # CONDUCTANCE (ВХОД):
    # Триггерится касанием.
    # - Density: Тяжелый агент получает больше урона (глубже проваливается в шипы).
    # - Integrity: Броня может защитить (например, сапоги от шипов).
    conductance_axes={
        "mat_density", 
        "mat_integrity"
    },

    # STABILITY (СТОЙКОСТЬ):
    # Лава остывает, шипы ломаются.
    stability_axes={
        "mat_thermal",    # Температура (для лавы)
        "mat_integrity"   # Острота шипов
    },

    # REACTIVITY (ВЫХОД):
    # Главный вектор — урон.
    # - Resilience: Биологический урон.
    # - Thermal: Термический ожог.
    # - Integrity: Разрушение снаряжения.
    reactivity_axes={
        "vit_resilience", # HP Damage
        "mat_thermal",    # Burn
        "mat_integrity"   # Armor break
    }
)

# --- 3. Эфирная Пустота (ARCH_TOPO_SUB_VOID) ---
# Примеры: Воздух (для полета), Космос, Астрал.
# Суть: Отсутствие опоры. Требует специфического способа передвижения (Flight).
topo_sub_void = MolecularDefinition(
    name_id="topo_sub_void",
    description="Lack of support requiring flight or propulsion.",

    # CONDUCTANCE (ВХОД):
    # Чтобы двигаться, нужна Кинетика (тяга), а не трение о пол.
    conductance_axes={
        "phys_kinetics", # Propulsion
        "mat_density"    # Gravity pull
    },

    # STABILITY (СТОЙКОСТЬ):
    # Неприменимо (пустота вечна), но может быть "плотность атмосферы".
    stability_axes={
        "mat_density"
    },

    # REACTIVITY (ВЫХОД):
    # - Kinetics: Падение (Gravity), если нет тяги.
    reactivity_axes={
        "phys_kinetics"  # Вектор гравитации (вниз)
    }
)

# --- 1. Магический Фон (ARCH_TOPO_ATMO_MAGIC) ---
# Примеры: Лей-линия, Зона дикой магии, Храм маны, Анти-магическое поле.
# Суть: Влияет на способность использовать `cog_abstraction` (магию).
topo_atmo_magic = MolecularDefinition(
    name_id="topo_atmo_magic",
    description="Ambient magical field enhancing or suppressing supernatural abilities.",

    # CONDUCTANCE (ВХОД):
    # Реагирует на применение магии внутри.
    conductance_axes={
        "cog_abstraction", # Cast spell
        "cog_complexity"   # Ritual
    },

    # STABILITY (СТОЙКОСТЬ):
    # Насыщенность маной. Истощается, если много колдовать.
    stability_axes={
        "cog_abstraction", # Mana Pool локации
        "cog_determinism"  # Стабильность законов магии
    },

    # REACTIVITY (ВЫХОД):
    # - Abstraction: Бафф (реген маны) или Дебафф (тишина/mana burn).
    # - Determinism: Искажение реальности (Wild Magic Surge).
    reactivity_axes={
        "cog_abstraction", # Power Mod
        "cog_determinism"  # Random effects
    }
)

# --- 1. Физический Барьер (ARCH_TOPO_GATE_PHYSICAL) ---
# Примеры: Запертая дверь, Завал, Решетка.
# Суть: Препятствие, которое нужно устранить физически (ключом или силой).
topo_gate_physical = MolecularDefinition(
    name_id="topo_gate_physical",
    description="Physical structure blocking passage until opened or destroyed.",

    # CONDUCTANCE (ВХОД):
    # Взаимодействие через:
    # - Acuity: Взлом замка (отмычка).
    # - Kinetics: Выбивание двери.
    # - Integrity: Ключ (как "совместимость" формы).
    conductance_axes={
        "mat_acuity",      # Lockpicking
        "phys_kinetics",   # Bashing
        "mat_integrity"    # Key insertion
    },

    # STABILITY (СТОЙКОСТЬ):
    # Прочность двери.
    stability_axes={
        "mat_integrity",   # Door HP
        "mat_density"      # Heavy door
    },

    # REACTIVITY (ВЫХОД):
    # Если открыто -> Kinetics (проход).
    # Если закрыто -> Kinetics (отдача/stop).
    reactivity_axes={
        "phys_kinetics"
    }
)

# --- 2. Социальный КПП (ARCH_TOPO_GATE_SOCIAL) ---
# Примеры: Стража у ворот, Таможня, Ресепшн, Фейс-контроль.
# Суть: Агент-шлюз. Пропускает на основе статуса или договоренности.
topo_gate_social = MolecularDefinition(
    name_id="topo_gate_social",
    description="Social checkpoint regulating access based on status or permission.",

    # CONDUCTANCE (ВХОД):
    # Чем убеждать?
    # - Reciprocity: Взятка.
    # - Stratification: Приказ ("Я герцог!").
    # - Information: Пропуск / Документы.
    conductance_axes={
        "soc_reciprocity",    # Bribe
        "soc_stratification", # Authority
        "cog_information"     # Papers
    },

    # STABILITY (СТОЙКОСТЬ):
    # Неподкупность стражи / Строгость правил.
    stability_axes={
        "soc_centralization", # Order
        "cog_dogmatism"       # Duty
    },

    # REACTIVITY (ВЫХОД):
    # Пропуск или Тревога.
    reactivity_axes={
        "soc_permeability",   # Grant Access
        "soc_aggression"      # Attack intruder (через вызов охраны)
    }
)

# --- 1. Средовой Сенсор (ARCH_TRIG_ENVIRONMENT) ---
# Примеры: "Если голод в городе > 80%", "Если уровень маны < 10%".
# Суть: Пассивно мониторит глобальные переменные Локуса.
plot_trig_environment = MolecularDefinition(
    name_id="plot_trig_environment",
    description="Passive sensor monitoring global state vectors (scarcity, danger, magic).",

    # CONDUCTANCE (ВХОД):
    # Что отслеживаем?
    # - Scarcity: Кризисы ресурсов.
    # - Density: Перенаселение / Давление.
    # - Abstraction: Магический фон.
    conductance_axes={
        "mat_scarcity",
        "mat_density",
        "cog_abstraction"
    },

    # STABILITY (СТОЙКОСТЬ):
    # Порог чувствительности.
    # Если Complexity высока, триггер сработает только при очень специфичных условиях.
    stability_axes={
        "cog_complexity",  # Сложность условия
        "cog_determinism"  # Жесткость правила
    },

    # REACTIVITY (ВЫХОД):
    # Запускает событие (Spawn Event).
    reactivity_axes={
        "cog_information"  # Сигнал запуска
    }
)

# --- 2. Социальный Интерактор (ARCH_TRIG_INTERACTION) ---
# Примеры: Диалог с NPC, Торговля, Попытка убеждения.
# Суть: Активная точка входа, требующая Агентности (Agency) игрока.
plot_trig_interaction = MolecularDefinition(
    name_id="plot_trig_interaction",
    description="Active trigger requiring social or cognitive engagement from an agent.",

    # CONDUCTANCE (ВХОД):
    # Чем воздействовать?
    # - Information: Сказать кодовую фразу / Спросить.
    # - Reciprocity: Предложить обмен / Взятку.
    # - Aesthetics: Харизма / Внешний вид.
    conductance_axes={
        "cog_information",
        "soc_reciprocity",
        "soc_aesthetics"
    },

    # STABILITY (СТОЙКОСТЬ):
    # "Социальная защита" триггера.
    # - Permeability: Насколько NPC открыт к общению?
    # - Stratification: Доступен ли этот разговор моему статусу?
    stability_axes={
        "soc_permeability",
        "soc_stratification"
    },

    # REACTIVITY (ВЫХОД):
    # Открывает доступ к информации или квесту.
    reactivity_axes={
        "cog_information", # Выдача Lore / Слухов
        "soc_cohesion"     # Изменение репутации
    }
)

# --- 3. Хронометр / Таймер (ARCH_TRIG_TEMPORAL) ---
# Примеры: "Полночь", "Через 3 дня", "Таймер бомбы".
# Суть: Неизбежный триггер, зависящий от энтропии/времени.
plot_trig_temporal = MolecularDefinition(
    name_id="plot_trig_temporal",
    description="Inevitable trigger driven by time decay or entropy.",

    # CONDUCTANCE (ВХОД):
    # Время течет само, но иногда его можно ускорить/замедлить.
    # - Perishability: Естественный ход времени (гниение/истечение).
    # - Kinetics: Некоторые механизмы заводятся движением.
    conductance_axes={
        "mat_perishability",
        "phys_kinetics" 
    },

    # STABILITY (СТОЙКОСТЬ):
    # Сколько времени осталось?
    # Decay превращает Stability (Duration) в 0 -> Триггер срабатывает.
    stability_axes={
        "mat_perishability", # Duration
        "cog_determinism"    # Неотвратимость (можно ли остановить таймер?)
    },

    # REACTIVITY (ВЫХОД):
    # Сигнал "Время вышло".
    reactivity_axes={
        "cog_determinism", # Принудительное изменение фазы
        "mat_thermal"      # Активация (если это бомба)
    }
)

# --- 1. Катастрофа / Удар (ARCH_EVENT_DISASTER) ---
# Примеры: Взрыв, Обвал, Удар молнии.
# Суть: Мгновенный выброс физической энергии.
plot_event_disaster = MolecularDefinition(
    name_id="plot_event_disaster",
    description="Sudden release of destructive physical energy.",

    # CONDUCTANCE (ВХОД):
    # Сопротивление среды (можно ли заглушить взрыв?).
    conductance_axes={
        "mat_density",    # Плотность среды
        "mat_thermal"     # Поглощение тепла
    },

    # STABILITY (СТОЙКОСТЬ):
    # Сила заряда.
    stability_axes={
        "phys_kinetics",
        "mat_thermal"
    },

    # REACTIVITY (ВЫХОД):
    # Урон.
    reactivity_axes={
        "phys_kinetics",  # Shockwave
        "mat_integrity",  # Destruction
        "vit_resilience"  # Casualty
    }
)

# --- 2. Откровение / Твист (ARCH_EVENT_REVELATION) ---
# Примеры: "Я твой отец", "Убийца — дворецкий", Изучение Древнего Свитка.
# Суть: Мгновенное изменение информационной картины (Knowledge Shock).
plot_event_revelation = MolecularDefinition(
    name_id="plot_event_revelation",
    description="Sudden influx of critical information reshaping cognitive models.",

    # CONDUCTANCE (ВХОД):
    # Восприятие.
    conductance_axes={
        "vit_perception", # Увидеть/Услышать
        "cog_agency"      # Осознать
    },

    # STABILITY (СТОЙКОСТЬ):
    # Шокирующая сила правды.
    stability_axes={
        "cog_information", # Важность факта
        "cog_complexity"   # Глубина тайны
    },

    # REACTIVITY (ВЫХОД):
    # Изменение поведения Агентов.
    # - Dogmatism: Разрушение старых верований.
    # - Drive: Смена мотивации.
    reactivity_axes={
        "cog_dogmatism",   # Shatter Faith
        "vit_drive",       # New Goal
        "soc_cohesion"     # Betrayal effect (распад группы)
    }
)

# --- 3. Социальный Потрясение (ARCH_EVENT_CRISIS) ---
# Примеры: Обвал рынка, Объявление войны, Смерть короля.
# Суть: Мгновенное изменение правил социума.
plot_event_crisis = MolecularDefinition(
    name_id="plot_event_crisis",
    description="Sudden shift in social hierarchy or economic value.",

    # STABILITY:
    # Масштаб кризиса.
    stability_axes={
        "soc_centralization", # Уровень хаоса
        "mat_scarcity"        # Глубина дефицита
    },

    # REACTIVITY:
    # - Fungibility: Деньги превращаются в фантики.
    # - Stratification: Падение элит.
    reactivity_axes={
        "mat_fungibility",    # Inflation / Market Crash
        "soc_stratification", # Revolution
        "soc_aggression"      # Riots
    }
)

# --- 1. Процесс-Задача / Квест (ARCH_PROC_QUEST) ---
# Примеры: Постройка дома, Крафт меча, Обучение навыку.
# Суть: Накопитель прогресса. Нужно "залить" ресурсы, чтобы получить результат.
plot_proc_task = MolecularDefinition(
    name_id="plot_proc_task",
    description="Constructive process requiring resource accumulation to complete.",

    # CONDUCTANCE (ВХОД):
    # Игрок "бьёт" по квесту ресурсами/действиями.
    conductance_axes={
        "mat_utility",    # Материалы
        "phys_kinetics",  # Работа
        "sys_skill"       # Применение навыка
    },

    # STABILITY (СТОЙКОСТЬ):
    # Объем работы (Progress Bar).
    # Когда Stability -> 0, процесс завершается успехом.
    stability_axes={
        "mat_integrity",  # Оставшаяся работа
        "cog_complexity"  # Сложность задачи
    },

    # REACTIVITY (ВЫХОД):
    # Награда при завершении (Loot) + Опыт (Process).
    reactivity_axes={
        "mat_fungibility", # Result Item / Gold
        "sys_skill"        # XP Gain
    }
)

# --- 2. Бедствие / Проклятие (ARCH_PROC_CALAMITY) ---
# Примеры: Чума, Голод, Утечка радиации.
# Суть: Процесс с отрицательной обратной связью. Постоянно наносит урон, пока не устранен.
plot_proc_calamity = MolecularDefinition(
    name_id="plot_proc_calamity",
    description="Destructive process draining resources or vitality over time.",

    # CONDUCTANCE (ВХОД):
    # Как остановить?
    # - Utility: Лекарства / Ремонт.
    # - Abstraction: Снятие проклятия.
    conductance_axes={
        "mat_utility",
        "cog_abstraction"
    },

    # STABILITY (СТОЙКОСТЬ):
    # Сила болезни / Уровень радиации.
    stability_axes={
        "vit_toxin",       # Virulence (кастомный тег или через Resilience)
        "mat_density"      # Концентрация загрязнения
    },

    # REACTIVITY (ВЫХОД):
    # Постоянный урон (DoT).
    reactivity_axes={
        "vit_resilience",  # Health Drain
        "mat_integrity",   # Structural Decay
        "soc_cohesion"     # Social Panic
    }
)

# --- 1. Животный Инстинкт (ARCH_MIND_INSTINCT) ---
# Для зверей, монстров, зомби.
mind_bio_instinct = MolecularDefinition(
    name_id="mind_bio_instinct",
    description="Reactive cognitive layer driven by survival drives.",
    # CONDUCTANCE: Реагирует на боль (Drive), страх и простые сигналы.
    conductance_axes={"vit_drive", "vit_perception", "phys_kinetics"}, 
    # STABILITY: Держится на ярости/голоде.
    stability_axes={"vit_drive", "vit_metabolism"},
    # REACTIVITY: Паника (Kinetics) или Атака.
    reactivity_axes={"phys_kinetics", "vit_drive"}
)

# --- 2. Разумное Эго (ARCH_MIND_SENTIENT) ---
# Для людей, эльфов, разумной нежити.
mind_cog_sentient = MolecularDefinition(
    name_id="mind_cog_sentient",
    description="Complex cognitive layer capable of logic and social interaction.",
    # CONDUCTANCE: Понимает речь (Info), социальные сигналы (Stratification).
    conductance_axes={"cog_information", "soc_stratification", "cog_dogmatism"},
    # STABILITY: Воля (Agency) и сложность мышления.
    stability_axes={"cog_agency", "cog_complexity"},
    # REACTIVITY: Принятие решений, смена убеждений.
    reactivity_axes={"cog_agency", "soc_reciprocity"}
)

# --- 3. Коллективный Разум / Рой (ARCH_MIND_HIVE) ---
# Для роев насекомых, толпы, фанатиков.
mind_soc_hive = MolecularDefinition(
    name_id="mind_soc_hive",
    description="Distributed cognition relying on group cohesion.",
    conductance_axes={"soc_cohesion", "soc_aesthetics"}, # Сигналы "свой-чужой"
    stability_axes={"soc_cohesion"}, # Пока мы едины — мы непобедимы
    reactivity_axes={"soc_aggression"} # Атака толпой
)

# --- 1. Идеологический Барьер / Догма (ARCH_SHELL_DOGMA) ---
# Использование: Секты, Религиозные ордена, Политические партии.
# Суть: Защищает организацию от чужих идей (Information) и размывания ценностей.
shell_soc_dogma = MolecularDefinition(
    name_id="shell_soc_dogma",
    description="Ideological barrier filtering information through strict beliefs.",

    # CONDUCTANCE (ВХОД):
    # Что атакует догму?
    # - Information: Аргументы, факты, ересь.
    # - Permeability: Попытки инфильтрации (шпионы).
    # - Dogmatism: Столкновение с чужой верой.
    conductance_axes={
        "cog_information", 
        "soc_permeability", 
        "cog_dogmatism"
    },

    # STABILITY (СТОЙКОСТЬ):
    # За счет чего держится?
    # - Dogmatism: Фанатичная вера (чем выше, тем прочнее).
    # - Cohesion: Сплоченность группы (поддержка друг друга).
    stability_axes={
        "cog_dogmatism", 
        "soc_cohesion"
    },

    # REACTIVITY (ВЫХОД):
    # Что происходит при разрушении (крахе веры)?
    # - Cohesion: Резкий социальный распад (раскол секты).
    # - Stratification: Падение авторитета лидеров.
    reactivity_axes={
        "soc_cohesion",      # Debuff (Panic/Disband)
        "soc_stratification" # Debuff (Loss of status)
    }
)

# --- 2. Бюрократия / Процедурный Щит (ARCH_SHELL_BUREAUCRACY) ---
# Использование: Правительство, Банк, Армия, Корпорация.
# Суть: Гасит инициативу и хаос за счет бесконечных правил и задержек.
shell_soc_bureaucracy = MolecularDefinition(
    name_id="shell_soc_bureaucracy",
    description="Complex procedural structure that absorbs chaotic impulses.",

    # CONDUCTANCE (ВХОД):
    # Что вязнет в бюрократии?
    # - Centralization: Попытки перехвата управления.
    # - Complexity: Сложные схемы (мошенничество).
    # - Agency: Личная инициатива (гасится правилами).
    conductance_axes={
        "soc_centralization", 
        "cog_complexity",
        "cog_agency" 
    },

    # STABILITY (СТОЙКОСТЬ):
    # Держится на жесткости процедур.
    # - Determinism: "Все должно быть по инструкции".
    # - Centralization: Вертикаль власти.
    stability_axes={
        "soc_centralization", 
        "cog_determinism"
    },

    # REACTIVITY (ВЫХОД):
    # При коллапсе системы (например, революции или банкротстве):
    # - Stratification: Начинается классовая грызня за ресурсы.
    # - Scarcity: Ресурсы блокируются или исчезают.
    reactivity_axes={
        "soc_stratification", # Internal Conflict
        "mat_scarcity"        # Resource Freeze
    }
)
