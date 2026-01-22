# src/ingestion/semantic_mapper.py
import numpy as np
from typing import List, Tuple
from openai import OpenAI
from src.config import config  # Импортируем глобальный конфиг

class SemanticMapper:
    """
    Маппер, использующий OpenAILike-compatible API (локальный LLM) для эмбеддингов.
    """
    def __init__(self, corpus: List[str]):
        # Инициализация клиента
        self.client = OpenAI(
            base_url=config.vector.base_url,
            api_key=config.vector.api_key
        )
        self.model_name = config.vector.model_name
        
        # Кэшируем векторы строк (матрица N x D)
        self.vectors = self._get_embeddings(corpus)

    def _get_embeddings(self, texts: List[str]) -> np.ndarray:
        """Получает эмбеддинги пакетом и нормализует их."""
        if not texts:
            return np.array([])
            
        # Запрос к API
        # Важно: некоторые локальные серверы могут не поддерживать большие батчи.
        # Если будет ошибка, нужно разбить на чанки.
        response = self.client.embeddings.create(
            input=texts,
            model=self.model_name
        )
        
        # Извлекаем векторы (гарантируем порядок)
        embeddings = [data.embedding for data in response.data]
        vec_matrix = np.array(embeddings)
        
        # L2-нормализация (для косинусного сходства через Dot Product)
        # norm = ||v||
        norm = np.linalg.norm(vec_matrix, axis=1, keepdims=True)
        # Избегаем деления на ноль
        normalized_matrix = vec_matrix / (norm + 1e-9)
        
        return normalized_matrix

    def search(self, query: str, top_k: int = 3) -> List[Tuple[int, float]]:
        """Возвращает ИНДЕКСЫ лучших совпадений и их score."""
        # 1. Векторизуем запрос
        query_vec = self._get_embeddings([query])[0] # shape (D,)
        
        # 2. Считаем косинусное сходство
        # Так как векторы нормализованы, CosSim(A, B) = A . B
        scores = np.dot(self.vectors, query_vec)
        
        # 3. Сортируем (от большего к меньшему)
        top_indices = np.argsort(-scores)[:top_k]
        
        results = []
        for idx in top_indices:
            # Конвертируем numpy types в стандартные python
            results.append((int(idx), float(scores[idx])))
            
        return results
    