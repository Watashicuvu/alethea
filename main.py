import logging
import sys
from typing import Any, List, Dict

# Настраиваем логирование, чтобы видеть прогресс этапов
logging.basicConfig(
    stream=sys.stdout, 
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)

from src.config import PipelineOptions
from src.pipeline.engine import IngestionEngine

# Конфигурация источников (Книг / Миров)
DATA_SOURCES: List[Dict[str, Any]] = [
    # {
    #     "id": "alice_wonderland",
    #     "path": "/Users/yakub/Downloads/alethea/assets/lore",
    #     "description": "Lewis Carroll's Alice in Wonderland",
    #     "index_ontology": True  # Загружаем правила игры (делаем это 1 раз для первого мира)
    # },
    {
        "id": "call_of_cthulhu",
        "path": "/Users/yakub/Downloads/alethea/assets/lorebooks/classic/call_c",
        "description": "Call of Cthulhu of Lafcraft",
        "index_ontology": True  # Загружаем правила игры (делаем это 1 раз для первого мира)
    },
    {
        "id": "call_of_wild",
        "path": "/Users/yakub/Downloads/alethea/assets/lorebooks/classic/london_call",
        "description": "London, call of wild",
        "index_ontology": True  # Загружаем правила игры (делаем это 1 раз для первого мира)
    },
    {
        "id": "strength_of",
        "path": "/Users/yakub/Downloads/alethea/assets/lorebooks/classic/london_strength",
        "description": "London, strength",
        "index_ontology": True  # Загружаем правила игры (делаем это 1 раз для первого мира)
    },
    {
        "id": "scp_6",
        "path": "/Users/yakub/Downloads/alethea/assets/lorebooks/gen/scp",
        "description": "London, strength",
        "index_ontology": True  # Загружаем правила игры (делаем это 1 раз для первого мира)
    },
    # {
    #     "id": "neuromancer",
    #     "path": "./assets/lore/neuromancer", 
    #     "description": "William Gibson's Neuromancer",
    #     "index_ontology": False # Используем те же правила, но другой мир
    # }
]

def main():
    print("🚀 Initializing Ingestion Engine...")
    
    # 1. Инициализация Движка
    # Здесь загружаются тяжелые модели (LLM, Embedder) и создаются подключения к БД
    options = PipelineOptions(
        project_atoms=True,
        project_events=True,
        detect_arcs=True
    )
    engine = IngestionEngine(options=options)

    # 2. Подготовка Инфраструктуры (создание коллекций в Qdrant/индексов в Neo4j)
    # Этот метод нужно добавить в IngestionEngine (см. ниже)
    engine.setup_infrastructure()

    # 3. Цикл обработки источников
    for source in DATA_SOURCES:
        src_id = source["id"]
        src_path = source["path"]
        
        print(f"\n\n{'='*80}")
        print(f"🌀 PROCESSING SOURCE: {src_id} ({source['description']})")
        print(f"{'='*80}")

        try:
            # А. Сброс контекста (Очистка памяти от предыдущей книги)
            # Критически важно, чтобы Алиса не встретилась с Кейсом.
            engine.reset_context()

            # Б. Индексация правил (если нужно)
            if source.get("index_ontology"):
                engine.index_registries(source_id="core_rules_v1")

            # В. Основной процесс (Extraction -> Ingestion)
            # Читает файлы, строит скелет, нарезает, извлекает сущности
            engine.process_directory(input_dir=src_path, source_id=src_id)

            # Г. Синтез мира (Synthesis)
            # Склеивает сущности, считает баланс, пишет хронику
            engine.run_post_processing(source_id=src_id)

            print(f"✅ COMPLETED: {src_id}")

        except Exception as e:
            logging.error(f"❌ FAILED processing {src_id}: {e}", exc_info=True)
            # Не падаем, пробуем следующую книгу
            continue

    print("\n🏁 All tasks finished. Exiting.")

if __name__ == "__main__":
    main()
    