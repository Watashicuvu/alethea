from src.models.ecs.ontology_schemas import SemanticVector

# Конфиг скина, а не отдельный класс
class ArcSkin:
    def __init__(self, base_template_id: str, step_overrides: dict, vector_modifier: SemanticVector):
        self.base_template_id = base_template_id
        self.step_overrides = step_overrides # Переименование шагов
        self.vector_modifier = vector_modifier # Сдвиг весов

# Библиотека скинов
ARC_SKINS = {
    "whistleblower_scandal": ArcSkin(
        base_template_id="arc_political_revolution", # Ссылка на шаблон из templates_arcs
        
        # Переопределяем описания шагов, не меняя логику графа
        step_overrides={
            "oppression": "Hidden corruption occurs within the organization.",
            "sabotage": "The Whistleblower leaks sensitive data (Data Breach).",
            "coup": "Public hearings lead to leadership resignation."
        },
        
        # Делаем арку "умнее" и менее "кровавой"
        vector_modifier=SemanticVector(vitality=-0.5, cognitive=0.5) 
    ),
    
    "aristotelian_tragedy": ArcSkin(
        base_template_id="arc_rise_and_fall", # Нужен новый шаблон Rise & Fall
        step_overrides={
            "peak": "Hubris: The Hero ignores warnings.",
            "crisis": "Peripeteia: Fortune reverses completely.",
            "collapse": "Catharsis: The Hero accepts their fate."
        },
        vector_modifier=SemanticVector(social=-1.0) # Потеря статуса критична
    )
}

class EventArcType:
    """
    Класс-контейнер для хранения констант типов арок.
    Помогает избежать опечаток при вызове шаблонов.
    """
    # --- Классические/Базовые (из прошлого контекста) ---
    RISE_AND_FALL = "rise_and_fall"
    STAGNATION = "stagnation"
    REVOLUTION = "revolution"

    # --- Новые: Современная политика (Modern Political) ---
    # Пример: Брексит, предвыборные кампании популистов
    POPULIST_SURGE = "populist_surge"
    
    # Пример: Уотергейт, Сноуден, WikiLeaks
    WHISTLEBLOWER_SCANDAL = "whistleblower_scandal"
    
    # Пример: Холодная война, торговые войны
    DIPLOMATIC_STANDOFF = "diplomatic_standoff"
    
    # Пример: Экологические движения, BLM
    GRASSROOTS_MOVEMENT = "grassroots_movement"

    # --- Новые: Драматургия (Dramaturgical) ---
    # Классическая трагедия (по Аристотелю)
    ARISTOTELIAN_TRAGEDY = "aristotelian_tragedy"
    
    # Путь героя (по Джозефу Кэмпбеллу) - адаптирован для событий
    HEROS_JOURNEY = "heros_journey"
    
    # Театр абсурда (Беккет) - для ситуаций без разрешения
    ABSURDIST_LOOP = "absurdist_loop"


# Словарь шаблонов, определяющий этапы каждого типа арки
ARC_TEMPLATES = {
    # === Классические ===
    EventArcType.RISE_AND_FALL: [
        "Зарождение", "Рост влияния", "Пик могущества", "Кризис", "Упадок", "Крах"
    ],
    EventArcType.REVOLUTION: [
        "Недовольство", "Искра", "Мобилизация", "Столкновение", "Свержение", "Новый порядок"
    ],

    # === Современная политика ===
    EventArcType.POPULIST_SURGE: [
        "Маргинализация элит",      # Ощущение, что элиты оторвались от народа
        "Появление харизматика",    # Лидер использует простую риторику
        "Поляризация общества",     # Разделение на "мы" и "они"
        "Электоральный шок",        # Неожиданная победа или событие
        "Институциональный конфликт", # Борьба лидера с системой
        "Нормализация или Импичмент"  # Итог
    ],
    EventArcType.WHISTLEBLOWER_SCANDAL: [
        "Скрытое нарушение",        # Коррупция или преступление в тайне
        "Утечка данных",            # Появление компромата (Leak)
        "Медийный взрыв",           # Публикация и общественный резонанс
        "Охота на ведьм",           # Преследование источника/журналистов
        "Общественное расследование",
        "Системные реформы (или их имитация)"
    ],
    EventArcType.DIPLOMATIC_STANDOFF: [
        "Провокация",               # Первое агрессивное действие
        "Эскалация риторики",       # Обмен угрозами
        "Санкционный обмен",        # Экономические меры
        "Балансирование на грани",  # Пик напряжения (Brinkmanship)
        "Деэскалация / Переговоры", # Отвод войск или саммит
        "Холодный мир"              # Возврат к статус-кво с недоверием
    ],
    EventArcType.GRASSROOTS_MOVEMENT: [
        "Локальная несправедливость",
        "Организация в соцсетях",   # Виральный рост
        "Уличные акции",            # Выход из онлайна в офлайн
        "Привлечение инфлюенсеров", # Масштабирование
        "Законодательная реакция",  # Власть вынуждена реагировать
        "Институционализация"       # Движение становится партией или НКО
    ],

    # === Драматургия ===
    EventArcType.ARISTOTELIAN_TRAGEDY: [
        "Высокое положение",        # Герой/Субъект на вершине
        "Гамартия (Роковая ошибка)",# Неверное решение из-за гордыни
        "Перипетия",                # Внезапный поворот судьбы к худшему
        "Анагноризис",              # Осознание своей ошибки (слишком поздно)
        "Катастрофа",               # Финальное разрушение
        "Катарсис (Очищение)"       # Урок для наблюдателей
    ],
    EventArcType.HEROS_JOURNEY: [
        "Зов к приключениям",       # Вызов статус-кво
        "Пересечение порога",       # Точка невозврата
        "Испытания и союзники",     # Формирование команды
        "Главная битва",            # Решающий конфликт
        "Воскрешение / Трансформация", # Изменение сути субъекта
        "Возвращение с эликсиром"   # Внедрение изменений в мир
    ],
    EventArcType.ABSURDIST_LOOP: [
        "Ожидание",                 # Ожидание перемен
        "Ложная надежда",           # Кажется, что что-то происходит
        "Разочарование",            # Ничего не произошло
        "Повторение действия",      # Попытка сделать то же самое
        "Осознание бессмысленности",
        "Возврат к началу"          # Цикл замыкается
    ]
}

def get_arc_stages(arc_type):
    """
    Возвращает список этапов для выбранного типа арки.
    """
    return ARC_TEMPLATES.get(arc_type, ["Неизвестный тип арки"])

# --- Пример использования ---

# 1. Пример политического события: Скандал с утечкой данных
print(f"--- Сценарий: {EventArcType.WHISTLEBLOWER_SCANDAL} ---")
stages = get_arc_stages(EventArcType.WHISTLEBLOWER_SCANDAL)
for i, stage in enumerate(stages, 1):
    print(f"Фаза {i}: {stage}")

print("\n")

# 2. Пример драматургического события: Крах корпорации (Трагедия)
print(f"--- Сценарий: {EventArcType.ARISTOTELIAN_TRAGEDY} ---")
stages = get_arc_stages(EventArcType.ARISTOTELIAN_TRAGEDY)
for i, stage in enumerate(stages, 1):
    print(f"Фаза {i}: {stage}")
    