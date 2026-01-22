from typing import List, Optional, Any
from pydantic import BaseModel, Field
from llama_index.core import PromptTemplate
from src.custom_program import LocalStructuredProgram
from src.config import config
from llama_index.llms.openai_like import OpenAILike

class ClassificationResult(BaseModel):
    selected_id: Optional[str] = Field(description="The exact ID of the best matching candidate, or None.")
    reasoning: str = Field(description="Short explanation why this fits best.")

class HybridClassifier:
    def __init__(self, llm: OpenAILike):
        self.llm = llm
        
        # Промпт для выбора из кандидатов
        self.selection_prompt = PromptTemplate(
            "You are a semantic classifier. Your task is to map a specific text segment to an Ontology Category.\n"
            "QUERY TEXT: \"{text}\"\n\n"
            "CANDIDATES (ID: Description):\n"
            "{candidates_text}\n\n"
            "INSTRUCTIONS:\n"
            "1. Analyze the nuance of the Query.\n"
            "2. Compare with the Candidates.\n"
            "3. Select the ID that BEST fits the mechanics/archetype of the action.\n"
            "4. If none fit well (e.g. text is irrelevant noise), return None.\n"
        )
        
        self.program = LocalStructuredProgram(
            output_cls=ClassificationResult,
            llm=self.llm,
            prompt=self.selection_prompt,
            verbose=True,
            api_key = config.llm.api_key,
            base_url = config.llm.base_url,
        )

    def classify(self, 
                 query_text: str, 
                 registry: Any, 
                 threshold_high: float = 0.88, 
                 threshold_low: float = 0.45,
                 top_k: int = 5) -> Optional[str]:
        """
        Гибридный классификатор:
        1. Векторный поиск (быстро).
        2. Если Top-1 очень похож (> threshold_high) -> берем его.
        3. Если Top-1 сомнителен (> threshold_low) -> зовем LLM выбрать из Top-K.
        4. Иначе -> None.
        """
        # 1. Vector Search (Registry должен иметь метод classify возвращающий список (Obj, Score))
        # Получаем кандидатов (Registry возвращает [(Item, score), ...])
        vector_candidates = registry.classify(query_text, threshold=0.1, top_k=top_k)
        
        if not vector_candidates:
            return None

        best_obj, best_score = vector_candidates[0]

        # 2. Fast Path (High Confidence)
        # Если вектор говорит, что это 90% совпадение, верим ему, экономим LLM вызов.
        if best_score > threshold_high:
            print(f"      🚀 Fast Match: {best_obj.id} ({best_score:.2f})")
            return best_obj.id

        # 3. LLM Refinement (Ambiguous Zone)
        # Если совпадение среднее (например, 0.6), возможно LLM поймет контекст лучше.
        if best_score > threshold_low:
            # Формируем список для LLM
            candidates_str = "\n".join([
                f"- {item.id}: {self._get_desc(item)}" 
                for item, score in vector_candidates
            ])
            
            try:
                result: ClassificationResult = self.program(
                    text=query_text,
                    candidates_text=candidates_str
                )
                if result.selected_id and result.selected_id.lower() != "none":
                    # Проверяем, что LLM не выдумала ID (он должен быть в списке кандидатов)
                    valid_ids = {item.id for item, _ in vector_candidates}
                    if result.selected_id in valid_ids:
                        print(f"      🧠 LLM Refinement: '{query_text[:30]}...' -> {result.selected_id}")
                        return result.selected_id
            except Exception as e:
                print(f"Classifier Error: {e}")
                # Fallback: возвращаем лучший векторный результат, если LLM упала
                return best_obj.id

        return None

    def _get_desc(self, item: Any) -> str:
        """Хелпер для вытаскивания описания из разных типов объектов."""
        if hasattr(item, "description"):
            return item.description
        if hasattr(item, "summary"):
            return item.summary
        return str(item)
    