# src/ingestion/game_math.py

from typing import Dict, List, Any, Optional
from src.ingestion.graph_schemas import MoleculeType
from src.models.ecs.taxonomy import SemanticTag

class GameMath:
    """
    Единый центр расчета игровых характеристик.
    Отвечает за наложение Масок (Bias), смешивание Атомов и нормализацию.
    """
    
    # 1. МАСКИ СУЩНОСТЕЙ (Уже были, переносим сюда)
    MOLECULE_BIAS = {
        "AGENT":     {"mat": 0.5, "vit": 1.2, "soc": 1.2, "cog": 1.2},
        "GROUP":     {"mat": 0.2, "vit": 0.8, "soc": 2.0, "cog": 1.0},
        "ASSET":     {"mat": 1.5, "vit": 0.5, "soc": 0.1, "cog": 0.3},
        "LOCATION":  {"mat": 1.2, "vit": 1.0, "soc": 0.5, "cog": 0.5},
        "CONSTRUCT": {"mat": 0.1, "vit": 0.5, "soc": 0.8, "cog": 1.5},
        "LORE":      {"mat": 0.0, "vit": 0.0, "soc": 0.5, "cog": 2.0},
    }

    # 2. МАСКИ СОБЫТИЙ
    # Мы определяем профиль для жанровых архетипов событий.
    EVENT_BIAS = {
        # Физический конфликт (Битва, Погоня)
        "conflict_physical": {"mat": 1.1, "vit": 1.8, "soc": 0.4, "cog": 0.6},
        # Социальный конфликт (Дебаты, Соблазнение, Допрос)
        "conflict_social":   {"mat": 0.2, "vit": 0.6, "soc": 1.8, "cog": 1.2},
        # Исследование / Открытие (Лутинг, Анализ)
        "discovery":         {"mat": 0.8, "vit": 0.5, "soc": 0.3, "cog": 1.5},
        # Перемещение (Путешествие)
        "transition":        {"mat": 1.0, "vit": 1.2, "soc": 0.5, "cog": 0.5},
        # Создание / Крафт / Ритуал
        "creation":          {"mat": 1.3, "vit": 0.6, "soc": 0.4, "cog": 1.4},
        # Fallback
        "generic":           {"mat": 1.0, "vit": 1.0, "soc": 1.0, "cog": 1.0},
    }

    @staticmethod
    def calculate_stats(
        base_vector_stats: Dict[str, float],
        atom_influence: Dict[str, List[float]],
        category: str,
        is_event: bool = False
    ) -> Dict[str, float]:
        """
        Главная формула:
        Final = (Base * (1-W) + Atoms * W) * TypeMask
        """
        ATOM_WEIGHT = 0.3
        
        # Выбираем маску
        if is_event:
            # Пытаемся найти по подстроке (например, evt_arch_conflict_physical -> conflict_physical)
            bias = GameMath.EVENT_BIAS["generic"]
            for key, val in GameMath.EVENT_BIAS.items():
                if key in category.lower():
                    bias = val
                    break
        else:
            bias = GameMath.MOLECULE_BIAS.get(category, GameMath.MOLECULE_BIAS.get("UNKNOWN", {}))

        final_stats = {}
        # Используем ключи осей: material, vitality, social, cognitive
        for axis, base_val in base_vector_stats.items():
            # 1. Blending with Atoms
            atoms_vals = atom_influence.get(axis, [])
            if atoms_vals:
                atom_avg = sum(atoms_vals) / len(atoms_vals)
                merged_val = (base_val * (1.0 - ATOM_WEIGHT)) + (atom_avg * ATOM_WEIGHT)
            else:
                merged_val = base_val
            
            # 2. Applying Bias
            # axis[:3] -> "mat", "vit"...
            short_key = axis[:3]
            bias_mult = bias.get(short_key, 1.0)
            
            final_stats[axis] = merged_val * bias_mult

        return final_stats

    @staticmethod
    def validate_tags(raw_tags: List[str], allowed_enum: Any) -> List[str]:
        """
        Фильтрует галлюцинации LLM. Оставляет только те теги, которые есть в taxonomy.py.
        """
        valid_values = set(item.value for item in allowed_enum)
        validated = []
        for t in raw_tags:
            t_clean = t.lower().strip()
            if t_clean in valid_values:
                validated.append(t_clean)
            else:
                # Можно добавить fuzzy matching, если LLM немного ошибается (prop_living vs prop_is_living)
                # Но для строгости пока просто отбрасываем
                pass
        return validated
    
    # 3. ACTION BIAS (Для Глаголов)
    # Помогает отличить Магию (Cog) от Боя (Vit) и Танцев (Soc)
    ACTION_BIAS = {
        "COMBAT":    {"mat": 1.2, "vit": 1.5, "soc": 0.3, "cog": 0.6},
        "MAGIC":     {"mat": 0.5, "vit": 0.8, "soc": 0.5, "cog": 1.8},
        "SOCIAL":    {"mat": 0.2, "vit": 0.5, "soc": 1.8, "cog": 1.2},
        "EXPLORE":   {"mat": 1.0, "vit": 1.0, "soc": 0.2, "cog": 1.5},
        "STEALTH":   {"mat": 0.5, "vit": 0.8, "soc": 0.5, "cog": 1.5},
        # Если это просто Flavor, мы не даем ему быть "сильной" механикой
        "FLAVOR":    {"mat": 0.8, "vit": 0.8, "soc": 0.8, "cog": 0.8}, 
    }

    # 4. VIBE BIAS (Для Атмосферы)
    # Вайбы должны быть экстремальными. Если страх — то Cognitive 2.0.
    VIBE_BIAS = {
        # Ключевые слова ищем в тегах или тексте
        "fear":      {"mat": 0.5, "vit": 0.3, "soc": 0.2, "cog": 2.0}, # Ужас
        "tension":   {"mat": 0.8, "vit": 1.2, "soc": 0.5, "cog": 1.5}, # Напряжение
        "wonder":    {"mat": 0.5, "vit": 0.5, "soc": 1.2, "cog": 1.8}, # Чудо
        "decay":     {"mat": 1.5, "vit": -0.5, "soc": 0.1, "cog": 0.5}, # Гниение (Material high, Vitality negative)
        "default":   {"mat": 1.0, "vit": 1.0, "soc": 1.0, "cog": 1.0},
    }

    @staticmethod
    def calculate_action_stats(base_stats: Dict[str, float], system: str) -> Dict[str, float]:
        """Спец-расчет для глаголов."""
        bias = GameMath.ACTION_BIAS.get(system, GameMath.ACTION_BIAS["FLAVOR"])
        return GameMath._apply_bias(base_stats, bias)

    @staticmethod
    def calculate_vibe_stats(base_stats: Dict[str, float], tags: List[str]) -> Dict[str, float]:
        """Спец-расчет для вайбов на основе тегов."""
        # Простейшая эвристика: ищем ключевые слова в тегах
        bias = GameMath.VIBE_BIAS["default"]
        tags_str = " ".join(tags).lower()
        
        if "fear" in tags_str or "dread" in tags_str: bias = GameMath.VIBE_BIAS["fear"]
        elif "decay" in tags_str or "rot" in tags_str: bias = GameMath.VIBE_BIAS["decay"]
        elif "magic" in tags_str or "wonder" in tags_str: bias = GameMath.VIBE_BIAS["wonder"]
        
        return GameMath._apply_bias(base_stats, bias)

    @staticmethod
    def _apply_bias(stats, bias):
        # Вспомогательный метод (Dry)
        final = {}
        for axis, val in stats.items():
            short = axis[:3]
            final[axis] = val * bias.get(short, 1.0)
        return final
    