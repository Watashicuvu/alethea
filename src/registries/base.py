# src/registries/base.py
from typing import TypeVar, Generic, List, Tuple, Dict, Callable, Optional
from pydantic import BaseModel
from src.ingestion.semantic_mapper import SemanticMapper

T = TypeVar("T", bound=BaseModel)

class OntologyRegistry(Generic[T]):
    def __init__(self, 
                 data_factory: Callable[[], List[T]], 
                 text_extractor: Callable[[T], str]):
        """
        Args:
            data_factory: Функция, возвращающая список моделей (get_standard_atoms...).
            text_extractor: Лямбда, превращающая модель в строку для поиска.
        """
        # 1. Загружаем данные (Оси Координат)
        self._items: List[T] = data_factory()
        self._map: Dict[str, T] = {item.id: item for item in self._items if hasattr(item, 'id')}
        
        # 2. Подготавливаем тексты для векторайзера
        search_corpus = [text_extractor(item) for item in self._items]
        
        # 3. Инициализируем "тупой" маппер
        if search_corpus:
            self.mapper = SemanticMapper(search_corpus)
            print(f"📐 Registry {self.__class__.__name__} initialized with {len(self._items)} axes.")
        else:
            self.mapper = None
            print(f"⚠️ Registry {self.__class__.__name__} is empty!")

    def classify(self, query_text: str, threshold: float = 0.4, top_k: int = 1) -> List[Tuple[T, float]]:
        """Проецирует текст на оси координат."""
        if not self.mapper:
            return []
            
        # Маппер возвращает индексы, мы превращаем их обратно в объекты
        results_indices = self.mapper.search(query_text, top_k=top_k)
        
        final_results: List[T] = []
        for idx, score in results_indices:
            if score >= threshold:
                final_results.append((self._items[idx], score))
                
        return final_results
    
    def get(self, item_id: str) -> Optional[T]:
        return self._map.get(item_id)
        
    def all(self) -> List[T]:
        return self._items
    