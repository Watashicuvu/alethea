import random
import time
from collections import deque
from src.services.knowledge_service import WorldKnowledgeService

# Буфер для детекции "Дня Сурка"
history_buffer = deque(maxlen=4)

def run_data_driven_tick(location_uuid: str, service: WorldKnowledgeService):
    
    # 1. Загрузка Сцены
    entities = service.load_scene_snapshot(location_uuid)
    if len(entities) < 2:
        print("Empty room.")
        return

    # Выбор пары (Актор -> Цель)
    actor = random.choice(entities)
    target = random.choice([e for e in entities if e['id'] != actor['id']])

    print(f"\n--- ⏱ TICK: {actor['name']} interacts with {target['name']} ---")

    # 2. Анализ Контекста (Векторная Математика)
    # Считаем "естественное расстояние" между ними
    similarity = service.calculate_interaction_outcome(actor['vector'], target['vector'])
    
    # 3. Определение Режима (Intent & Query)
    
    # А. Проверка на стагнацию
    current_state_tag = "NEUTRAL"
    if similarity > 0.75: current_state_tag = "SYNERGY"
    elif similarity < 0.35: current_state_tag = "CONFLICT"
    
    history_buffer.append(current_state_tag)
    is_stagnating = (len(history_buffer) == 4 and len(set(history_buffer)) == 1)

    query_vec = None
    intent_sign = 0.0
    mode_desc = ""

    if is_stagnating:
        # --- ORTHOGONAL BIAS (Маятник) ---
        print("   🌀 STAGNATION DETECTED! Injecting Orthogonal Event.")
        # Ищем событие, перпендикулярное текущему вектору Актора.
        # Это "сменит тему" (например, от Боя к Торговле).
        query_vec = service.get_orthogonal_query(actor['vector'], intensity=1.0)
        
        # Ортогональные события обычно "меняют" состояние, а не просто добавляют/убавляют
        intent_sign = 0.5 
        mode_desc = "SHIFT"
        history_buffer.clear() # Сброс
        
    else:
        # --- STANDARD PHYSICS ---
        if current_state_tag == "SYNERGY":
            # Они хотят делать что-то СОВМЕСТНОЕ, похожее на них самих.
            # Вектор поиска = Среднее между Актором и Целью
            # query_vec = (VecA + VecB) / 2
            # Для простоты берем вектор Актора
            query_vec = actor['vector']
            intent_sign = 1.0 # Buff / Craft / Trade
            mode_desc = "COOP (+)"
            
        elif current_state_tag == "CONFLICT":
            # Они хотят УНИЧТОЖИТЬ друг друга.
            # Вектор поиска = Актор (как он атакует?)
            query_vec = actor['vector']
            intent_sign = -1.0 # Damage / Steal / Debuff
            mode_desc = "HOSTILE (-)"
            
        else:
            print("   💤 Neutral interaction (ignored)")
            return

    # 4. Поиск Глагола в Онтологии (Read from DB)
    # Мы не хардкодим "Attack", мы спрашиваем Qdrant: "Что подходит к этому вектору?"
    verb_data = service.find_best_verb(query_vec)
    
    if not verb_data:
        print("   ❌ No applicable mechanics found.")
        return

    print(f"   🎲 Selected Mechanics: '{verb_data['name']}' (Score: {verb_data['score']:.2f})")
    print(f"      Mode: {mode_desc} | Verb Stats: {verb_data['stats']}")

    # 5. Применение Физики (Write to DB)
    # Изменяем статы Цели на основе статов Глагола и Знака Намерения
    new_stats, changes_log = service.apply_interaction_physics(
        target_entity=target,
        verb_data=verb_data,
        intent_multiplier=intent_sign
    )

    if changes_log:
        print(f"   📉 Outcome for {target['name']}: {changes_log}")
        service.update_entity_state(target['id'], new_stats)
    else:
        print(f"   Action had no effect.")
        