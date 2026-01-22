from typing import Dict, Optional, List, Any
from rapidfuzz import fuzz, process
from pydantic import BaseModel, Field
from llama_index.core import PromptTemplate
from qdrant_client import models

from src.config import config
from src.custom_program import LocalStructuredProgram

class ResolutionResult(BaseModel):
    selected_id: Optional[str] = Field(description="The UUID of the entity that matches the query best. Return None if unsure.")
    reasoning: str = Field(description="Brief explanation (e.g. 'The text mentions her blonde hair, matching Alice').")

class EntityResolver:
    """
    Умный резолвер имен в UUID.
    Pipeline: Cache -> Fuzzy -> Semantic (Qdrant) -> LLM (Context).
    """
    def __init__(self, ctx):
        self.ctx = ctx
        self._registry_cache: Dict[str, str] = {} # canonical_name -> uuid
        self._reverse_registry: Dict[str, str] = {} # uuid -> canonical_name (для контекста LLM)
        
        # === LLM PROGRAM ===
        self.llm_prompt = PromptTemplate(
            "You are a Contextual Entity Resolver.\n"
            "Identify who '{query}' refers to in the provided text snippet.\n\n"
            "CONTEXT TEXT:\n...{context}...\n\n"
            "CANDIDATES (Known Entities):\n"
            "{candidates_list}\n\n"
            "INSTRUCTIONS:\n"
            "1. Analyze the context to identify the specific individual.\n"
            "2. Match with the Candidates list.\n"
            "3. If '{query}' is a pronoun (She/He) or generic (The guard), use context clues.\n"
            "4. If no candidate matches or it's a new entity, return None.\n"
        )
        
        self.resolver_program = LocalStructuredProgram(
            output_cls=ResolutionResult,
            llm=self.ctx.llm,
            prompt=self.llm_prompt,
            verbose=True,
            api_key=config.llm.api_key,
            base_url=config.llm.base_url
        )

    def load_registry(self, registry: Dict[str, str]):
        """Загружает реестр имен из Pass 2."""
        self._registry_cache = {k.lower(): v for k, v in registry.items()}
        # Создаем обратный индекс для формирования списка кандидатов
        self._reverse_registry = {v: k for k, v in registry.items()}

    def resolve_name(self, name_query: str, context_loc_id: Optional[str] = None) -> Optional[str]:
        """
        Главный метод разрешения.
        """
        clean_name = name_query.lower().strip()
        if len(clean_name) < 2: return None

        # 1. EXACT & PARTIAL MATCH (In Memory)
        # Самый быстрый этап. Ищем в загруженном реестре текущего документа.
        if clean_name in self._registry_cache:
            return self._registry_cache[clean_name]

        # Проверка на вхождение ("Hatter" in "The Mad Hatter")
        # process.extractOne вернет лучший матч
        best_match = process.extractOne(
            clean_name, 
            self._registry_cache.keys(), 
            scorer=fuzz.ratio,
            score_cutoff=85
        )
        if best_match:
            match_name, score, _ = best_match
            return self._registry_cache[match_name]

        # 2. CONTEXTUAL SEARCH (In Location)
        # Если не нашли в памяти, возможно это "Стражник", и нам нужен именно "Стражник в этой локации".
        if context_loc_id:
            loc_specific_id = self.ctx.repos.entities.find_entity_in_location(
                context_loc_id, clean_name
            )
            if loc_specific_id:
                return loc_specific_id

        # 3. GLOBAL FUZZY SEARCH (Database)
        # Ищем по всей базе Neo4j (для глобальных NPC, встреченных в других книгах)
        global_id = self.ctx.repos.entities.fuzzy_search_molecule(clean_name, threshold=0.85)
        if global_id:
            return global_id
            
        return None

    def resolve(self, name_query: str, context_text: str, scene_cast_uids: List[str] = []) -> Optional[str]:
        """
        Главный метод.
        Args:
            name_query: Имя/Фраза из текста ("The girl", "She", "Excalibur")
            context_text: Текст вокруг (параграф или сцена)
            scene_cast_uids: Список UUID тех, кто точно есть в сцене (для приоритета)
        """
        clean_name = name_query.lower().strip()
        if len(clean_name) < 2: return None
        if clean_name in ["someone", "anyone", "no one"]: return None

        # 1. FAST LOOKUP (Registry)
        if clean_name in self._registry_cache:
            return self._registry_cache[clean_name]

        # 2. FUZZY MATCH (Registry)
        # Ищем среди известных имен
        best_match = process.extractOne(
            clean_name, 
            self._registry_cache.keys(), 
            scorer=fuzz.ratio,
            score_cutoff=85
        )
        if best_match:
            match_name, score, _ = best_match
            print(f"   ⚡ Fuzzy Resolved: '{name_query}' -> {match_name}")
            return self._registry_cache[match_name]

        # 3. SEMANTIC SEARCH (Qdrant)
        # "The golden blade" -> "Excalibur"
        # Ищем по коллекции молекул (у нас там есть черновики из Pass 2)
        sem_id = self._semantic_search(name_query)
        if sem_id:
            print(f"   🧠 Semantic Resolved: '{name_query}' -> {sem_id}")
            return sem_id

        # 4. LLM CONTEXTUAL RESOLUTION (Fallback)
        # Если это местоимение или сложное описание ("The one who knocked")
        # ИЛИ если Fuzzy/Semantic не дали результата, но имя выглядит важным
        if len(context_text) > 10:
            return self._resolve_with_llm(name_query, context_text, scene_cast_uids)

        return None

    def _semantic_search(self, query: str) -> Optional[str]:
        """Поиск по смыслу в Qdrant (molecules)."""
        if not self.ctx.qdrant.collection_exists("molecules"):
            return None
            
        vec = self.ctx.embedder.get_text_embedding(query)
        
        # Ищем Top-1
        res = self.ctx.qdrant.query_points(
            collection_name="molecules",
            query=vec,
            limit=1
        )
        
        # Порог должен быть высоким, чтобы не цеплять случайные вещи
        if res.points and res.points[0].score > 0.88:
            return res.points[0].id
        return None

    def _resolve_with_llm(self, query: str, context: str, priority_uids: List[str]) -> Optional[str]:
        """
        Спрашиваем LLM, кто это.
        Приоритет отдаем entity из scene_cast (список кандидатов).
        """
        # 1. Формируем список кандидатов для промпта
        # Сначала приоритетные (кто в сцене), потом остальные (если мало приоритетных)
        candidates_desc = []
        
        # Добавляем Cast
        for uid in priority_uids:
            name = self._reverse_registry.get(uid, "Unknown")
            # Можно добавить краткое описание, если оно есть в metadata синтезатора
            desc = self._get_entity_desc(uid)
            candidates_desc.append(f"- {name} (ID: {uid}): {desc}")
        
        # Если приоритетных мало, добавляем из глобального реестра (до лимита токенов)
        if len(candidates_desc) < 5:
            for name, uid in list(self._registry_cache.items())[:10]: # Берем первые 10 для примера
                if uid not in priority_uids:
                     candidates_desc.append(f"- {name} (ID: {uid})")

        candidates_str = "\n".join(candidates_desc)
        
        # 2. Вызываем LLM
        try:
            # Обрезаем контекст для экономии (вокруг события)
            safe_context = context[-2000:] if len(context) > 2000 else context
            
            res = self.resolver_program(
                query=query,
                context=safe_context,
                candidates_list=candidates_str
            )
            
            if res.selected_id and res.selected_id.lower() != "none":
                print(f"      🤖 LLM Resolved: '{query}' -> {res.selected_id} ({res.reasoning})")
                return res.selected_id
                
        except Exception as e:
            # logging.error(f"LLM Resolution failed: {e}")
            pass
            
        return None

    def _get_entity_desc(self, uid: str) -> str:
        """Хелпер: достает category/subtype из метаданных синтезатора."""
        if hasattr(self.ctx, 'synthesizer'):
            meta = self.ctx.synthesizer._metadata.get(uid, {})
            return f"{meta.get('category', 'Entity')} {meta.get('subtype', '')}"
        return "Entity"
    