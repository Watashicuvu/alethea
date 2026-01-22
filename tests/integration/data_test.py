# test_generation.py
import os
from src.services.vector_db import VectorDatabase

# 1. Инициализация (теперь через слои)
db = VectorDatabase()

# Указываем путь к файлу, который сгенерировал генератор
# (Убедись, что имя файла совпадает с тем, что в папке assets)
json_path = "assets/ontology_dark_fantasy_forest.json" 

if os.path.exists(json_path):
    print(f"Loading layer from {json_path}...")
    # Загружаем как Core слой (базовый контент)
    db.load_layer_from_file("core_set", json_path, is_core=True)
else:
    print(f"❌ File not found: {json_path}. Run data_generator.py first!")
    exit()

# 2. Получаем прототип для теста
# Прототипы лежат внутри слоев. Достанем первый попавшийся из слоя 'core_set'
core_layer = db.layers.get("core_set")
if not core_layer or not core_layer.prototypes:
    print("❌ No prototypes found in the database.")
    exit()

ent_proto = core_layer.prototypes[0]
print(f"\n🧬 Spawning Prototype: {ent_proto.name}")
print(f"   Desc: {ent_proto.description}")

# 3. Заполняем слоты (Векторный Спуск)
print("-" * 40)
for slot in ent_proto.slots:
    print(f"🔍 Slot '{slot.name}' (Sphere: {slot.required_sphere.value})")
    print(f"   Query: '{slot.search_query_text}'")
    
    # Ищем подходящий атом!
    # Возвращает список кортежей: [(Atom, 0.95), (Atom, 0.82), ...]
    candidates = db.search_atoms(
        query_vector=slot.search_query_vector, 
        sphere=slot.required_sphere,
        total_top_k=1 
    )
    
    if candidates:
        # !!! ВАЖНО: Распаковка кортежа !!!
        chosen_atom, score = candidates[0]
        
        status_icon = "✅" if score > slot.threshold else "⚠️"
        print(f"   {status_icon} FOUND: [{chosen_atom.name}] (Score: {score:.3f})")
        print(f"     -> Atom Desc: {chosen_atom.description[:60]}...")
    else:
        print("   ❌ EMPTY (No suitable atoms found in any layer)")
        
    print("-" * 40)