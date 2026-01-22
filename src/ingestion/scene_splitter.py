import logging
import re
import numpy as np
from typing import List, Tuple, Any, Optional
from pydantic import BaseModel, Field
from rapidfuzz import fuzz

# Импортируем PrivateAttr для хранения объектов (LLM, Embedder) внутри Pydantic моделей
from llama_index.core.bridge.pydantic import PrivateAttr
from llama_index.core.node_parser import NodeParser, SentenceSplitter
from llama_index.core.schema import BaseNode, TextNode, Document
from llama_index.core import PromptTemplate
from src.custom_program import LocalStructuredProgram
from src.config import config

# === МОДЕЛИ ДАННЫХ ===

class SceneBoundary(BaseModel):
    """
    Единая модель границы сцены.
    Сочетает в себе CoT (summary), Anchors (snippets) и Metadata (label).
    """
    # 1. CHAIN OF THOUGHT (Сначала LLM думает о событии)
    event_summary: str = Field(description="Brief summary of the event starting here.")
    
    # 2. METADATA (Заголовок для навигации)
    context_label: str = Field(description="Short title for this section (e.g. 'Alice falls down').")
    
    # 3. ANCHORS (Якоря для поиска в тексте)
    pre_context: str = Field(description="The LAST sentence (verbatim) of the PREVIOUS scene.")
    start_snippet: str = Field(description="The FIRST sentence (verbatim) of the NEW scene.")
    
    # 4. CLASSIFICATION
    scene_type: str = Field(description="PHYSICAL, MEMORY, DREAM, DOCUMENT.")
    reason: str = Field(description="Why split here?")

class SegmentationBatch(BaseModel):
    """
    Контейнер для ответа с поддержкой глобального рассуждения.
    """
    # Глобальный CoT: Анализ структуры всего куска текста ПЕРЕД тем, как выделять границы
    reasoning_chain: str = Field(description="Step-by-step analysis of the narrative flow and structure.")
    boundaries: List[SceneBoundary]

class LocatorResult(BaseModel):
    """Результат работы LLM-снайпера."""
    exact_quote: str = Field(description="The exact verbatim string found in the text.")
    is_found: bool = Field(description="True if the quote was successfully located.")
    confidence: float = Field(description="Certainty level (0.0-1.0).")
    reasoning: str = Field(description="Brief explanation of how the match was found (e.g. 'Corrected spelling error').")


# === СПЛИТТЕРЫ ===

class AdaptiveMicroSplitter(NodeParser):
    """
    Умный сплиттер для микро-чанкинга.
    """
    # 1. Объявляем конфигурационные поля (Pydantic Fields)
    min_tokens: int = Field(default=500, description="Minimum chunk size")
    max_tokens: int = Field(default=2000, description="Maximum chunk size")
    base_threshold: float = Field(default=0.4, description="Semantic split threshold")
    
    # 2. Объявляем приватные атрибуты для сложных объектов
    # Они не будут валидироваться Pydantic, но доступны через self._embedder
    _embedder: Any = PrivateAttr()
    _tokenizer: Any = PrivateAttr()
    _sentence_splitter: SentenceSplitter = PrivateAttr()

    def __init__(
        self, 
        embedder, 
        tokenizer, 
        min_tokens: int = 500, 
        max_tokens: int = 2000,
        base_threshold: float = 0.4,
        **kwargs
    ):
        # Передаем поля в super().__init__ для валидации
        super().__init__(
            min_tokens=min_tokens,
            max_tokens=max_tokens,
            base_threshold=base_threshold,
            **kwargs
        )
        
        # Сохраняем объекты в приватные атрибуты (через underscore)
        self._embedder = embedder
        self._tokenizer = tokenizer
        
        # Инициализируем внутренний сплиттер
        self._sentence_splitter = SentenceSplitter(chunk_size=max_tokens)

    def _map_sentence_offsets(self, original_text: str, sentences: List[str]) -> List[Tuple[int, int]]:
        offsets = []
        cursor = 0
        for sent in sentences:
            start = original_text.find(sent, cursor)
            if start == -1:
                start = cursor 
            end = start + len(sent)
            offsets.append((start, end))
            cursor = end 
        return offsets

    def _calc_distances(self, embeddings: List[List[float]]) -> List[float]:
        distances = []
        for i in range(len(embeddings) - 1):
            vec_a = np.array(embeddings[i])
            vec_b = np.array(embeddings[i+1])
            similarity = np.dot(vec_a, vec_b)
            distances.append(1.0 - similarity)
        return distances

    def get_nodes_from_documents(self, documents: List[Document], **kwargs) -> List[BaseNode]:
        final_nodes = []
        
        for doc in documents:
            full_text = doc.text
            # Обращаемся к приватному атрибуту
            sentences = self._sentence_splitter.split_text(full_text)
            if not sentences: continue
            
            sent_spans = self._map_sentence_offsets(full_text, sentences)
            
            print(f"   🔬 Adaptive Split: Analyzing {len(sentences)} sentences...")

            try:
                # Обращаемся к приватному атрибуту
                embeddings = self._embedder.get_text_embedding_batch(sentences)
            except:
                embeddings = [self._embedder.get_text_embedding(s) for s in sentences]

            if len(embeddings) < 2:
                node = TextNode(text=full_text)
                node.metadata["start_char_idx"] = 0
                node.metadata["end_char_idx"] = len(full_text)
                final_nodes.append(node)
                continue

            distances = self._calc_distances(embeddings)
            
            chunk_start_idx = 0  
            current_tokens = 0
            
            i = 0
            while i < len(sentences):
                # Обращаемся к приватному атрибуту
                token_count = len(self._tokenizer(sentences[i])) if self._tokenizer else len(sentences[i]) // 4
                current_tokens += token_count
                
                is_last_sentence = (i == len(sentences) - 1)
                should_split = False
                dist = distances[i] if i < len(distances) else 0.0
                
                if current_tokens >= self.max_tokens:
                    should_split = True
                
                elif current_tokens >= self.min_tokens:
                    progress = (current_tokens - self.min_tokens) / (self.max_tokens - self.min_tokens)
                    dynamic_threshold = self.base_threshold * (1.2 - (0.7 * progress))
                    if dist > dynamic_threshold:
                        should_split = True

                if should_split or is_last_sentence:
                    real_start = sent_spans[chunk_start_idx][0]
                    real_end = sent_spans[i][1]
                    
                    chunk_text = full_text[real_start:real_end]
                    
                    node = TextNode(text=chunk_text)
                    node.metadata["start_char_idx"] = real_start
                    node.metadata["end_char_idx"] = real_end
                    
                    final_nodes.append(node)
                    
                    chunk_start_idx = i + 1
                    current_tokens = 0
                
                i += 1
                
        return final_nodes

    def _parse_nodes(self, nodes: List[BaseNode], **kwargs) -> List[BaseNode]:
        return self.get_nodes_from_documents([Document(text=n.get_content()) for n in nodes])


class SemanticSceneSplitter(NodeParser):
    # Конфигурация
    window_size: int = Field(default=25_000, description="Context window size")
    min_scene_len: int = Field(default=1_000, description="Min chars per scene")
    
    # Приватные сервисы
    _llm: Any = PrivateAttr()
    _segment_program: LocalStructuredProgram = PrivateAttr()
    _locator_program: LocalStructuredProgram = PrivateAttr()

    def __init__(self, llm, window_size: int = 25_000, **kwargs):
        super().__init__(window_size=window_size, **kwargs)
        self._llm = llm
        
        # 1. ПРОГРАММА СЕГМЕНТАЦИИ (Событийно-ориентированная)
        seg_prompt = PromptTemplate(
            "Analyze the text stream for Narrative Events.\n"
            "Identify where the scene significantly changes (Location, Time, or Mood shift).\n\n"
            "STRATEGY:\n"
            "1. Analyze the narrative flow (reasoning_chain).\n"
            "2. Identify the EXACT sentences that separate events.\n"
            "3. Generate a descriptive Title (context_label) for each new section.\n\n"
            "OUTPUT FORMAT:\n"
            "- 'reasoning_chain': Step-by-step thinking process.\n"
            "- 'pre_context': The last sentence of the old scene.\n"
            "- 'start_snippet': The first sentence of the new scene.\n"
            "- 'context_label': A short name for the scene.\n"
            "- 'event_summary': What happens in this scene.\n\n"
            "TEXT STREAM:\n{text}\n"
        )
        self._segment_program = LocalStructuredProgram(
            output_cls=SegmentationBatch,
            llm=self._llm,
            prompt=seg_prompt,
            verbose=True,
            api_key=config.llm.api_key,
            base_url=config.llm.base_url
        )

        # 2. ПРОГРАММА-ЛОКАТОР (Fallback)
        # Если Fuzzy не нашел цитату, этот агент найдет её точное написание
        loc_prompt = PromptTemplate(
            "I have a quote that might be slightly hallucinated or misformatted.\n"
            "Find the equivalent text in the provided Source Passage.\n\n"
            "HALLUCINATED QUOTE: \"{quote}\"\n\n"
            "SOURCE PASSAGE:\n{text}\n\n"
            "TASK:\n"
            "1. Find the best matching substring in the Source Passage.\n"
            "2. Return the EXACT text from the source.\n"
            "3. If absolutely not found, set is_found=False.\n"
        )
        self._locator_program = LocalStructuredProgram(
            output_cls=LocatorResult, 
            llm=self._llm,
            prompt=loc_prompt,
            verbose=True,
            api_key=config.llm.api_key,
            base_url=config.llm.base_url
        )

    def _normalize(self, text: str) -> str:
        """Убирает пунктуацию и лишние пробелы для сравнения."""
        return re.sub(r'\W+', ' ', text).lower().strip()

    def _skeleton_find(self, source_text: str, snippet: str, start_offset: int) -> int:
        """
        Ищет вхождение, игнорируя всё, кроме букв и цифр.
        Возвращает РЕАЛЬНЫЙ индекс начала в source_text.
        """
        # 1. Создаем "скелеты" (только alnum, lowercase)
        # Нам нужно сохранить маппинг индексов скелета на индексы оригинала
        
        # Оптимизация: работаем только с окном поиска, а не всем текстом
        search_window = source_text[start_offset : start_offset + 5000]
        if not search_window: return -1
        
        snippet_skeleton = "".join(c for c in snippet if c.isalnum()).lower()
        if not snippet_skeleton: return -1

        # 2. Строим скелет окна и карту индексов
        window_skeleton = []
        map_back = [] # index in skeleton -> index in window
        
        for i, char in enumerate(search_window):
            if char.isalnum():
                window_skeleton.append(char.lower())
                map_back.append(i)
                
        window_skeleton_str = "".join(window_skeleton)
        
        # 3. Ищем скелет сниппета внутри скелета окна
        skeleton_idx = window_skeleton_str.find(snippet_skeleton)
        
        if skeleton_idx != -1:
            # 4. Восстанавливаем реальный индекс
            real_local_idx = map_back[skeleton_idx]
            return start_offset + real_local_idx
            
        return -1


    def _robust_find_index(self, window_text: str, snippet: str, search_start: int) -> int:
            """
            Попытка 1: Exact
            Попытка 2: Skeleton (No punctuation)
            Попытка 3: Fuzzy
            Попытка 4: LLM Locator
            """
            # 0. Sanity Check
            if not snippet or len(snippet) < 3: return -1
            
            # Ограничиваем окно (оптимизация)
            # Но для skeleton_find передаем offset, он сам обрежет
            
            # 1. EXACT MATCH
            exact = window_text.find(snippet, search_start, search_start + 5000)
            if exact != -1:
                return exact

            # 2. SKELETON MATCH (New!)
            # Решает проблему: "Alice said," vs "Alice said" vs "Alice   said"
            skel_idx = self._skeleton_find(window_text, snippet, search_start)
            if skel_idx != -1:
                print(f"      💀 Skeleton match found for: '{snippet[:15]}...'")
                return skel_idx

            # 3. FUZZY SEARCH (Alignment)
            # Ограничиваемся куском текста
            search_chunk = window_text[search_start : search_start + 5000]
            
            alignment = fuzz.partial_ratio_alignment(
                snippet.lower(), 
                search_chunk.lower(),
                score_cutoff=85 
            )
            
            if alignment and alignment.score >= 85:
                # Проверяем, что совпадение не слишком короткое
                match_len = alignment.src_end - alignment.src_start
                if match_len > len(snippet) * 0.6:
                    return search_start + alignment.dest_start

            # 4. LLM FALLBACK (Locator)
            print(f"      ⚠️ All algos failed for: '{snippet[:30]}...'. Calling Locator.")
            
            try:
                res: LocatorResult = self._locator_program(
                    quote=snippet,
                    text=search_chunk[:2000] # Даем LLM только начало зоны поиска
                )
                
                if res.is_found and res.exact_quote:
                    clean_quote = res.exact_quote.strip()
                    
                    # После того как LLM вернула "исправленную" цитату,
                    # СНОВА прогоняем её через Skeleton Search (вдруг LLM опять ошиблась в пробеле)
                    
                    # Попытка А: Точный поиск ответа LLM
                    retry_exact = window_text.find(clean_quote, search_start, search_start + 5000)
                    if retry_exact != -1:
                        print(f"      ✅ Locator Fixed: Exact match found.")
                        return retry_exact
                    
                    # Попытка Б: Скелетный поиск ответа LLM
                    retry_skel = self._skeleton_find(window_text, clean_quote, search_start)
                    if retry_skel != -1:
                        print(f"      ✅ Locator Fixed: Skeleton match found.")
                        return retry_skel
                        
                print(f"      ❌ Locator returned text '{res.exact_quote[:20]}...' but still not found.")

            except Exception as e:
                print(f"      ❌ Locator crashed: {e}")
                
            return -1

    def get_nodes_from_documents(self, documents: List[Document], **kwargs) -> List[BaseNode]:
        final_nodes = []
        
        for doc in documents:
            full_text = doc.text
            total_len = len(full_text)
            global_cursor = 0
            
            print(f"✂️  Smart Splitter: Processing {total_len} chars...")

            while global_cursor < total_len:
                window_end = min(global_cursor + self.window_size, total_len)
                window_text = full_text[global_cursor : window_end]
                
                if len(window_text) < self.min_scene_len:
                    # Хвост
                    final_nodes.append(self._create_node(window_text, "PHYSICAL", "End", global_cursor))
                    break

                try:
                    # 1. Extract Boundaries
                    response: SegmentationBatch = self._segment_program(text=window_text)
                    
                    if not response.boundaries:
                        # Нет сцен? Весь кусок - одна сцена.
                        print("   ⏩ No split detected. Advancing full window.")
                        final_nodes.append(self._create_node(window_text, "PHYSICAL", "Continuous", global_cursor))
                        global_cursor += len(window_text) # Или window_size - overlap
                        continue

                    local_cursor = 0
                    last_found_global = global_cursor
                    
                    current_meta = final_nodes[-1].metadata if final_nodes else {
                        "scene_type": "PHYSICAL", "context_label": "Intro",
                        "event_summary": 'Start of narrative'
                    }

                    for b in response.boundaries:
                        # 2. Robust Find
                        # Ищем start_snippet
                        found_idx = self._robust_find_index(window_text, b.start_snippet, local_cursor)
                        
                        # Если не нашли по start_snippet, попробуем по pre_context (конец предыдущей)
                        if found_idx == -1:
                             # Ищем конец предыдущего предложения
                             pre_idx = self._robust_find_index(window_text, b.pre_context, local_cursor)
                             if pre_idx != -1:
                                 # Если нашли конец предыдущей, то начало новой = конец предыдущей + длина
                                 found_idx = pre_idx + len(b.pre_context)
                                 print(f"      ⚓ Anchored via Pre-Context: '{b.pre_context[:20]}...'")

                        if found_idx == -1:
                            print(f"      🚫 Skipped boundary (Not found): {b.start_snippet[:30]}...")
                            continue
                        
                        # Валидация: не слишком ли близко?
                        if found_idx < 50:
                            # Обновляем мету, но не режем (слишком начало окна)
                            current_meta.update({"scene_type": b.scene_type, "context_label": b.context_label})
                            continue

                        # 3. Create Node (С логикой слияния)
                        scene_text = window_text[local_cursor:found_idx]
                        
                        abs_start = global_cursor + local_cursor
                        abs_end = global_cursor + found_idx
                        
                        # --- НОВАЯ ЛОГИКА ---
                        is_too_short = len(scene_text) < self.min_scene_len
                        
                        if is_too_short and final_nodes:
                            # MERGE WITH PREVIOUS: Сцена слишком мелкая, это просто "хвост" предыдущей.
                            print(f"      🔗 Merging short chunk ({len(scene_text)} chars) into previous scene.")
                            
                            # Обновляем предыдущую ноду
                            prev_node = final_nodes[-1]
                            
                            # Доклеиваем текст (LlamaIndex TextNode позволяет менять .text)
                            new_text = prev_node.get_content() + "\n" + scene_text # Добавляем разделитель
                            prev_node.set_content(new_text)
                            
                            # Обновляем метаданные конца
                            prev_node.metadata["end_char_idx"] = abs_end
                            
                            # (Опционально) Можно обновить summary в метаданных, добавив инфо о хвосте
                            prev_node.metadata["event_summary"] = prev_node.metadata.get('event_summary', '') + f" Also: {current_meta.get('event_summary', '')}"

                        elif len(scene_text) > 0:
                            # CREATE NEW: Сцена нормальная или это самая первая сцена
                            node = TextNode(text=scene_text)
                            node.metadata["scene_type"] = current_meta.get("scene_type", "PHYSICAL")
                            node.metadata["context_label"] = current_meta.get("context_label", "Narrative")
                            node.metadata["event_summary"] = current_meta.get("event_summary", "")
                            node.metadata["start_char_idx"] = abs_start
                            node.metadata["end_char_idx"] = abs_end
                            
                            final_nodes.append(node)

                        # Update State
                        local_cursor = found_idx
                        last_found_global = global_cursor + found_idx
                        
                        # Prepare for next
                        # Теперь мы берем данные из только что найденной границы `b`
                        # И эти данные пойдут в МЕТАДАННЫЕ следующего куска текста
                        try:
                            current_meta = {
                                "scene_type": b.scene_type, 
                                # Теперь b.context_label существует и не вызовет ошибку
                                "context_label": b.context_label,
                                "event_summary": b.event_summary if hasattr(b, 'event_summary') else ''
                            }
                        except:
                            print('не сохранил')
                            pass

                    # 4. Advance Global Cursor
                    # Сдвигаем на последнюю найденную границу
                    if last_found_global > global_cursor:
                        print(f"   🔄 Advancing cursor to {last_found_global}")
                        global_cursor = last_found_global
                    else:
                        # Если ничего не нашли, безопасный сдвиг
                        print("   ⚠️ No valid boundaries anchored. Advancing safe step (70%).")
                        safe_step = int(self.window_size * 0.7)
                        # Сохраняем кусок, чтобы не потерять
                        text_chunk = window_text[:safe_step]
                        final_nodes.append(self._create_node(text_chunk, "PHYSICAL", "Flow", global_cursor))
                        global_cursor += safe_step

                except Exception as e:
                    logging.error(f"Critical Split Error: {e}", exc_info=True)
                    global_cursor += int(self.window_size * 0.5)

        return final_nodes

    def _create_node(self, text, type_, label, start_idx):
        n = TextNode(text=text)
        n.metadata["scene_type"] = type_
        n.metadata["context_label"] = label
        n.metadata["start_char_idx"] = start_idx
        n.metadata["end_char_idx"] = start_idx + len(text)
        return n

    def _parse_nodes(self, nodes: List[BaseNode], **kwargs) -> List[BaseNode]:
        return self.get_nodes_from_documents([Document(text=n.get_content()) for n in nodes])
