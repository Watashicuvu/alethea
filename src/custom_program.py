import os
import hashlib
import json
from typing import Type, Any, Dict, Optional, TypeVar, List
from pydantic import BaseModel, create_model, Field
from llama_index.core.types import BasePydanticProgram
from llama_index.core.prompts import BasePromptTemplate
from llama_index.core.llms import LLM
from openai import OpenAI
from openai.types.chat.chat_completion_user_message_param import ChatCompletionUserMessageParam
from openai.types.chat.chat_completion_system_message_param import ChatCompletionSystemMessageParam

Model = TypeVar("Model", bound=BaseModel)

class LocalStructuredProgram(BasePydanticProgram[Model]):
    def __init__(
        self,
        output_cls: Type[Model],
        prompt: BasePromptTemplate,
        llm: LLM,
        api_key: str,
        base_url: str,
        verbose: bool = False,
        cache_dir: Optional[str] = "cache/llm_responses",
        stats_file: Optional[str] = "token_usage.json",  # <--- NEW: Файл статистики
        max_retries: int = 3
    ):
        self._output_cls = output_cls
        self._prompt = prompt
        self._llm = llm
        self._verbose = verbose
        self._model_name = llm.metadata.model_name
        self._cache_dir = cache_dir
        self._stats_file = stats_file
        self._max_retries = max_retries

        # Создаем папку кэша
        if self._cache_dir and not os.path.exists(self._cache_dir):
            os.makedirs(self._cache_dir)

        self._client = OpenAI(api_key=api_key, base_url=base_url)

    def _get_cache_path(self, prompt_str: str) -> str:
        """Создает уникальное имя файла на основе контента промпта."""
        content_hash = hashlib.md5((prompt_str + self._model_name).encode('utf-8')).hexdigest()
        return os.path.join(self._cache_dir, f"{content_hash}.json")

    def _update_usage(self, usage, schema_name: str):
        """
        Аккумулирует статистику токенов в JSON файл.
        Сгруппировано по имени схемы (output_cls).
        """
        if not usage or not self._stats_file:
            return

        # Пытаемся прочитать существующий файл
        data = {}
        if os.path.exists(self._stats_file):
            try:
                with open(self._stats_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, IOError):
                data = {}

        # Инициализируем структуру для этой схемы, если её нет
        # Используем имя схемы как ключ (разрез по выходной схеме)
        key = schema_name
        if key not in data:
            data[key] = {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_calls": 0,
                "model": self._model_name # Сохраняем имя модели для справки
            }

        # Обновляем счетчики
        data[key]["input_tokens"] += usage.prompt_tokens
        data[key]["output_tokens"] += usage.completion_tokens
        data[key]["total_calls"] += 1
        
        # Если модель сменилась, можно обновить поле (или хранить сложнее, но пока так)
        data[key]["model"] = self._model_name

        # Записываем обратно
        try:
            with open(self._stats_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except IOError as e:
            if self._verbose:
                print(f"⚠️ Ошибка записи статистики: {e}")

    def _identify_missing_fields(self, model_instance: BaseModel) -> Dict[str, Any]:
        """Находит поля, которые явно равны None."""
        missing = {}
        for name, field_info in model_instance.model_fields.items():
            value = getattr(model_instance, name)
            if value is None:
                missing[name] = (field_info.annotation, field_info)
        return missing

    def _create_repair_schema(self, missing_fields: Dict[str, Any]) -> Type[BaseModel]:
        """Создает временную Pydantic модель для исправления."""
        fields = {
            "reason": (str, Field(..., description="Explanation why these fields were missing or logic for deducing them."))
        }
        for name, (type_annotation, field_info) in missing_fields.items():
            fields[name] = (type_annotation, field_info)
        
        return create_model(f"Repair{self._output_cls.__name__}", **fields)

    def _merge_repair(self, original: Model, repair: BaseModel):
        """Вливает исправленные данные в оригинальный объект."""
        data = repair.model_dump(exclude={"reason"})
        for k, v in data.items():
            if v is not None:
                setattr(original, k, v)
                if self._verbose:
                    print(f"   └── Patched '{k}'")

    @property
    def output_cls(self) -> Type[Model]:
        return self._output_cls

    def __call__(
        self,
        llm_kwargs: Optional[Dict[str, Any]] = None,
        *args: Any,
        **kwargs: Any,
    ) -> Model:
        llm_kwargs = llm_kwargs or {}
        
        # 1. Форматируем промпт
        user_prompt_str = self._prompt.format(**kwargs)
        schema_name = self._output_cls.__name__

        # === CACHE HIT LOGIC ===
        if self._cache_dir:
            cache_path = self._get_cache_path(user_prompt_str)
            if os.path.exists(cache_path):
                if self._verbose:
                    print(f"⚡ [Cache Hit] {schema_name}")
                with open(cache_path, "r", encoding="utf-8") as f:
                    return self._output_cls.model_validate(json.load(f))
        # =======================

        messages = [
            ChatCompletionSystemMessageParam(role='system', content='You are a helpful assistant.'),
            ChatCompletionUserMessageParam(role='user', content=user_prompt_str),
        ]

        if self._verbose:
            print(f"--- [LLM Call] {schema_name} ---")

        try:
            # 1. Основной вызов (Main Call)
            completion = self._client.chat.completions.parse(
                model=self._model_name,
                messages=messages,
                response_format=self._output_cls,
                temperature=0.1,
                **llm_kwargs
            )
            
            # --- LOG USAGE (Main) ---
            if completion.usage:
                self._update_usage(completion.usage, schema_name)
            # ------------------------

            current_obj = completion.choices[0].message.parsed
            
            # 2. Цикл исправлений (Repair Loop)
            for attempt in range(self._max_retries):
                missing_fields = self._identify_missing_fields(current_obj)
                
                if not missing_fields:
                    break
                
                if self._verbose:
                    print(f"⚠️  [Repair {attempt+1}] Fixing nulls: {list(missing_fields.keys())}")

                RepairModel = self._create_repair_schema(missing_fields)
                
                # Добавляем контекст в историю чата
                messages.append(ChatCompletionSystemMessageParam(
                    role='assistant', 
                    content=current_obj.model_dump_json()
                ))
                
                repair_prompt = (
                    f"Fields {list(missing_fields.keys())} are null. "
                    "Analyze the text again. 1. Write a 'reason'. 2. Fill the missing fields."
                )
                
                messages.append(ChatCompletionUserMessageParam(
                    role='user', 
                    content=repair_prompt
                ))

                # Вызов исправления
                repair_completion = self._client.chat.completions.parse(
                    model=self._model_name,
                    messages=messages,
                    response_format=RepairModel,
                    temperature=0.1,
                    **llm_kwargs
                )

                # --- LOG USAGE (Repair) ---
                if repair_completion.usage:
                    # Можно добавить суффикс, например schema_name + "_REPAIR", 
                    # но обычно полезнее видеть общую стоимость задачи.
                    self._update_usage(repair_completion.usage, schema_name)
                # --------------------------
                
                repair_obj = repair_completion.choices[0].message.parsed
                self._merge_repair(current_obj, repair_obj)

            # === CACHE WRITE LOGIC ===
            if self._cache_dir:
                cache_path = self._get_cache_path(user_prompt_str)
                with open(cache_path, "w", encoding="utf-8") as f:
                    f.write(current_obj.model_dump_json(indent=2))
                if self._verbose:
                    print(f"💾 [Saved] {cache_path}")
            # =========================
            
            return current_obj

        except Exception as e:
            if self._verbose:
                print(f"❌ Error: {e}")
            raise e
        