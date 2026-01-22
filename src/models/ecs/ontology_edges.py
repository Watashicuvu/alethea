from enum import Enum
from pydantic import BaseModel

class SocialRelType(str, Enum):
    # Горизонтальные связи
    ALLY = "ally"             # Союз (AI помогает в бою)
    HOSTILE = "hostile"       # Вражда (AI атакует при встрече)
    NEUTRAL = "neutral"       # Игнорирование
    
    # Вертикальные связи (Иерархия)
    MASTER_SLAVE = "master_of" # Подчинение (AI отдает приказы)
    PARENT_CHILD = "parent_of" # Забота/Наследование
    
    # Эмоциональные связи
    DEBT = "debtor_to"         # Долг (Влияет на торговлю/убеждение)
    ROMANCE = "romantic_with"  # Особые интеракции

class SocialLink(BaseModel):
    type: SocialRelType
    intensity: float = 1.0     # 0.1 (знакомые) -> 1.0 (кровные братья)
    publicly_known: bool = True # Секретный роман?

class ContainerRelType(str, Enum):
    # Локация -> Локация
    IS_INSIDE = "is_inside"      # Комната внутри Дома (Zoning)
    
    # Сущность -> Локация
    LOCATED_AT = "located_at"    # NPC стоит в комнате
    
    # Сущность -> Сущность (Инвентарь)
    EQUIPPED = "equipped_by"     # Меч в руке (Дает статы)
    IN_INVENTORY = "stored_by"   # Меч в рюкзаке (Только вес)
    IMPLANTED = "implanted_in"   # Кибер-имплант / Паразит
    
    # Сущность -> Знание (Knowledge Graph)
    KNOWS_SECRET = "knows_secret" # NPC знает секрет
    HAS_SKILL = "has_skill"       # (Опционально, если скиллы это узлы)
