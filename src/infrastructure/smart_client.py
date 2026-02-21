# src/infrastructure/smart_client.py
import os
import json
import hashlib
import time
import logging
from typing import Any, Dict, Optional, Type, TypeVar, Union
from pydantic import BaseModel

from openai import OpenAI, APIConnectionError, RateLimitError
from openai.types.chat import ChatCompletion
from src.debug.telemetry import telemetry, EventType # Подключаем нашу телеметрию

T = TypeVar("T", bound=BaseModel)

class SmartOpenAI:
    def __init__(
        self, 
        api_key: str, 
        base_url: str, 
        cache_dir: str = "cache/openai_global",
        max_retries: int = 5
    ):
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._cache_dir = cache_dir
        self._max_retries = max_retries
        
        if not os.path.exists(self._cache_dir):
            os.makedirs(self._cache_dir)

    def _get_cache_key(self, messages: list, model: str, extra: dict) -> str:
        """Создает уникальный хэш на основе входных данных."""
        # Сериализуем всё, что влияет на генерацию
        payload = {
            "messages": messages,
            "model": model,
            **extra
        }
        raw = json.dumps(payload, sort_keys=True)
        return hashlib.md5(raw.encode('utf-8')).hexdigest()

    def _load_cache(self, key: str) -> Optional[Dict]:
        path = os.path.join(self._cache_dir, f"{key}.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def _save_cache(self, key: str, data: Any):
        path = os.path.join(self._cache_dir, f"{key}.json")
        with open(path, "w", encoding="utf-8") as f:
            # Если это Pydantic модель или OpenAI объект, сериализуем
            if hasattr(data, "model_dump"):
                json_data = data.model_dump(mode='json')
            elif hasattr(data, "to_dict"): # OpenAI v1 objects
                json_data = data.to_dict()
            else:
                json_data = data
                
            json.dump(json_data, f, ensure_ascii=False, indent=2)

    def chat_completion(
        self,
        messages: list,
        model: str,
        response_format: Optional[Type[T]] = None,
        **kwargs
    ) -> Union[ChatCompletion, T]:
        """
        Универсальный метод:
        - Если передан response_format (Pydantic класс) -> возвращает объект этого класса (Structured Output).
        - Если нет -> возвращает обычный ChatCompletion.
        - Включает Кэш, Ретраи и Телеметрию.
        """
        
        # 1. Подготовка ключа кэша
        # Если response_format это класс, берем его schema_json для уникальности
        schema_sig = response_format.model_json_schema() if response_format else "raw_text"
        cache_key = self._get_cache_key(messages, model, {"schema": schema_sig, **kwargs})

        # 2. Проверка кэша
        cached_data = self._load_cache(cache_key)
        if cached_data:
            # 📡 TELEMETRY: Cache Hit
            telemetry.emit(EventType.STEP_INFO, "SmartClient Cache Hit", {"key": cache_key})
            
            if response_format:
                # Восстанавливаем Pydantic объект из JSON
                return response_format.model_validate(cached_data)
            else:
                # Восстанавливаем OpenAI объект (немного упрощенно, обычно достаточно словаря)
                # Для полной совместимости можно использовать openai.types.chat.ChatCompletion.model_validate
                return ChatCompletion.model_validate(cached_data)

        # 3. Выполнение с ретраями
        last_error = None
        for attempt in range(self._max_retries):
            try:
                # 📡 TELEMETRY: Request
                telemetry.emit(EventType.LLM_REQ, f"OpenAI Call (Att: {attempt+1})", {
                    "model": model,
                    "messages": messages[-1] if messages else []
                })

                start_time = time.time()
                
                if response_format:
                    # Используем новый .parse() интерфейс OpenAI
                    completion = self._client.chat.completions.parse(
                        model=model,
                        messages=messages,
                        response_format=response_format,
                        **kwargs
                    )
                    if hasattr(completion, 'choices'):
                        result = completion.choices[0].message.parsed
                    elif hasattr(completion, 'output_parsed'):
                        result = completion.output_parsed
                    else:
                        result = completion
                else:
                    # Обычный режим
                    completion = self._client.chat.completions.create(
                        model=model,
                        messages=messages,
                        **kwargs
                    )
                    result = completion

                duration = time.time() - start_time

                # 📡 TELEMETRY: Success
                telemetry.emit(EventType.LLM_RES, f"OpenAI Success ({duration:.2f}s)", {
                    "tokens": completion.usage.total_tokens if completion.usage else 0
                })

                # 4. Сохранение в кэш
                self._save_cache(cache_key, result)
                
                return result

            except (RateLimitError, APIConnectionError) as e:
                last_error = e
                wait_time = 2 ** attempt # Экспоненциальная задержка
                telemetry.emit(EventType.ERROR, f"Retryable Error: {e}", {"wait": wait_time})
                time.sleep(wait_time)
            except Exception as e:
                # Критические ошибки (например, 400 Bad Request) не ретраим
                telemetry.emit(EventType.ERROR, f"Critical OpenAI Error", {"error": str(e)})
                raise e

        raise last_error
    