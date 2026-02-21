# src/infrastructure/async_smart_client.py
import os
import json
import hashlib
import asyncio
import time
from typing import (Any, Callable, Dict, List, Optional, 
                    Type, TypeVar, Union)
from pydantic import BaseModel

from openai import (AsyncOpenAI, APIConnectionError, 
                    RateLimitError)
from openai.types.chat import ChatCompletion
from src.debug.telemetry import telemetry, EventType

T = TypeVar("T", bound=BaseModel)

# Тип для трансформации промптов
Transform = Callable[[List[Dict[str, Any]]], List[Dict[str, Any]]]

# TODO assert на размер кэша! Если json эмбеддингов будет слишком жирным,
# его надо чистить и / или сохранить куда-то копию

class AsyncSmartOpenAI:
    def __init__(
        self, 
        api_key: str, 
        base_url: str, 
        cache_dir: str = "cache/openai_global",
        max_retries: int = 5,
        custom_transform: Optional[Transform] = None
    ):
        # Используем асинхронный клиент
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._cache_dir = cache_dir
        self._max_retries = max_retries
        self._custom_transform = custom_transform
        
        # Создание директории можно оставить синхронным, так как это происходит 1 раз при старте
        if not os.path.exists(self._cache_dir):
            os.makedirs(self._cache_dir)

    def _get_cache_key(self, messages: list, model: str, extra: dict) -> str:
        """Создает уникальный хэш (CPU-bound, выполняется синхронно)."""
        payload = {
            "messages": messages,
            "model": model,
            **extra
        }
        # Используем default=str для обработки любых несериализуемых объектов
        raw = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.md5(raw.encode('utf-8')).hexdigest()

    def _load_cache_sync(self, key: str) -> Optional[Dict]:
        """Синхронная внутренняя функция чтения файла."""
        path = os.path.join(self._cache_dir, f"{key}.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                # Повреждённый кэш - удаляем и возвращаем None
                import logging
                logging.warning(f"Corrupted cache file {path}: {e}. Removing...")
                try:
                    os.remove(path)
                except:
                    pass
                return None
        return None

    async def _load_cache(self, key: str) -> Optional[Dict]:
        """Асинхронная обертка: запускает чтение файла в отдельном потоке."""
        return await asyncio.to_thread(self._load_cache_sync, key)

    def _save_cache_sync(self, key: str, data: Any):
        """Синхронная внутренняя функция записи файла."""
        path = os.path.join(self._cache_dir, f"{key}.json")
        with open(path, "w", encoding="utf-8") as f:
            if hasattr(data, "model_dump_json"):
                # Используем model_dump_json() для правильной сериализации всех вложенных объектов
                json_str = data.model_dump_json(indent=2)
                f.write(json_str)
            elif hasattr(data, "to_dict"):
                json_data = data.to_dict()
                json.dump(json_data, f, ensure_ascii=False, indent=2)
            else:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    async def _save_cache(self, key: str, data: Any):
        """Асинхронная обертка: запускает запись файла в отдельном потоке."""
        await asyncio.to_thread(self._save_cache_sync, key, data)

    # --- Внутренняя логика репетиции ---
    
    def _is_multimodal_message(self, message: Dict[str, Any]) -> bool:
        """Проверяет, содержит ли сообщение изображения."""
        content = message.get("content")
        if isinstance(content, list):
            return any(
                part.get("type") in ("image_url", "image") 
                for part in content
            )
        return False

    def _default_repetition_logic(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Встроенная логика репетиции:
        1. Если есть мультимодальность -> дублируем только system.
        2. Если всё текст -> дублируем всё.
        """
        has_multimodal = any(self._is_multimodal_message(m) for m in messages)
        new_messages = []

        if has_multimodal:
            # Правило 1: Дублируем только system
            for m in messages:
                if m["role"] == "system":
                    content = m["content"]
                    if isinstance(content, str):
                        new_messages.append({**m, "content": content + "\n\n" + content})
                    else:
                        # Редкий кейс: system как список
                        new_messages.append({**m, "content": content + content})
                else:
                    new_messages.append(m)
        else:
            # Правило 2: Дублируем всё (текстовый режим)
            for m in messages:
                content = m.get("content")
                if isinstance(content, str):
                    new_messages.append({**m, "content": content + "\n\n" + content})
                elif isinstance(content, list):
                    # Если список, но без картинок (просто разбитый текст)
                    new_messages.append({**m, "content": content + content})
                else:
                    new_messages.append(m)
        
        return new_messages

    async def chat_completion(
        self,
        messages: list,
        model: str,
        response_format: Optional[Type[T]] = None,
        use_prompt_repetition: bool = True,
        **kwargs
    ) -> Union[ChatCompletion, T]:
        """
        Асинхронный универсальный метод.
        
        Args:
            messages: Список сообщений чата
            model: Название модели
            response_format: Опциональный формат структурированного ответа
            use_prompt_repetition: Применить ли трансформацию повторения промпта
            **kwargs: Дополнительные параметры для API
        """
        # 1. Применение репетиции
        messages_to_use = messages
        if use_prompt_repetition:
            if self._custom_transform:
                messages_to_use = self._custom_transform(messages)
            else:
                messages_to_use = self._default_repetition_logic(messages)
        
        # 1. Подготовка ключа кэша
        schema_sig = response_format.model_json_schema() if response_format else "raw_text"
        cache_key = self._get_cache_key(messages, model, {"schema": schema_sig, **kwargs})

        # 2. Проверка кэша (await)
        cached_data = await self._load_cache(cache_key)
        if cached_data:
            # TODO: эта фигня всё ещё не отображается
            telemetry.emit(
                EventType.STEP_INFO, 
                "SmartClient Cache Hit", 
                cached_data
            )
            
            if response_format:
                return response_format.model_validate(cached_data)
            else:
                return ChatCompletion.model_validate(cached_data)

        # 3. Выполнение с ретраями
        # кол-во попыток верное, но модель не сохраняется
        last_error = None
        for attempt in range(self._max_retries):
            try:
                telemetry.emit(EventType.LLM_REQ, f"OpenAI Call (Att: {attempt+1})", {
                    "model": model,
                    "messages": messages_to_use if messages_to_use else []
                })

                start_time = time.time()
                
                if response_format:
                    # Асинхронный вызов .parse()
                    completion = await self._client.chat.completions.parse(
                        model=model,
                        messages=messages_to_use,
                        response_format=response_format,
                        **kwargs
                    )
                    if hasattr(completion, 'choices'):
                        result = completion.choices[0].message.parsed
                    elif hasattr(completion, 'output_parsed'):
                        result = completion.output_parsed
                    else:
                        # видимо, это у новых версий; ну или сервер lm studio api
                        result = completion
                else:
                    # Асинхронный вызов .create()
                    completion = await self._client.chat.completions.create(
                        model=model,
                        messages=messages_to_use,
                        **kwargs
                    )
                    result = completion

                duration = time.time() - start_time

                telemetry.emit(EventType.LLM_RES, f"OpenAI Success ({duration:.2f}s)", {
                        "tokens": completion.usage.total_tokens if hasattr(completion, 'usage') else 0,
                        "output": result.model_dump() if hasattr(result, 'model_dump') else str(result),
                        "raw_completion": completion.model_dump() if hasattr(completion, 'model_dump') else {}
                })

                # 4. Сохранение в кэш (await)
                await self._save_cache(cache_key, result)
                
                return result

            # TODO: можно отправлять другим провайдерам
            except (RateLimitError, APIConnectionError) as e:
                last_error = e
                wait_time = 2 ** attempt
                telemetry.emit(EventType.ERROR, f"Retryable Error: {e}", {"wait": wait_time})
                # ВАЖНО: asyncio.sleep вместо time.sleep, чтобы не блокировать другие задачи
                await asyncio.sleep(wait_time)
            except Exception as e:
                telemetry.emit(EventType.ERROR, f"Critical OpenAI Error", {"error": str(e)})
                raise e

        raise last_error
