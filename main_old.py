# main.py
from src.config import PipelineOptions
from src.ingestion.pipeline import IngestionEngine


if __name__ == "__main__":
    # 1. Настраиваем, какие "линзы" включить
    opts = PipelineOptions(
        # все флаги по дефу включены (и по факту флаги не оч работают сейчас)
    )

    # 2. Запускаем
    engine = IngestionEngine(options=opts)

    # кажется, только при первом запуске (ну статику; а динамику для каждого источника)
    # так что, по идее, тут в цикле нужно брать источники и присваивать им
    # имена для индексирования 
    engine.index_registries('Alice')
    
    # почему-то здесь тоже происходит что-то долгое перед обработкой
    # (регистрация и калибровка), хотя это должно создаваться один раз 
    engine.process_directory("./assets/lore")
    
    # 3. Пост-процессинг
    engine.run_post_processing()
