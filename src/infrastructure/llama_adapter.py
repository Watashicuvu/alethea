# src/infrastructure/llama_adapter.py
from typing import Any, List, Optional, Dict

from llama_index.core.llms import (
    CustomLLM, 
    ChatMessage, 
    ChatResponse, 
    CompletionResponse,
    CompletionResponseGen,
    ChatResponseGen,
    LLMMetadata
)
from llama_index.core.llms.callbacks import llm_chat_callback, llm_completion_callback
from src.infrastructure.smart_client import SmartOpenAI

class SmartLlamaLLM(CustomLLM):
    """
    Адаптер, который позволяет LlamaIndex использовать наш SmartOpenAI
    для всех операций (индексация, ретривал, синтез).
    """
    # Pydantic-поля (CustomLLM наследуется от BaseModel)
    model_name: str
    smart_client: SmartOpenAI  # Наш инстанс SmartOpenAI
    context_window: int = 128000
    num_output: int = 4096

    @property
    def metadata(self) -> LLMMetadata:
        """Сообщаем LlamaIndex характеристики модели."""
        return LLMMetadata(
            context_window=self.context_window,
            num_output=self.num_output,
            model_name=self.model_name,
            is_chat_model=True,
        )

    @llm_chat_callback()
    def chat(self, messages: List[ChatMessage], **kwargs: Any) -> ChatResponse:
        """
        Перехватываем вызов чата от LlamaIndex и направляем в SmartClient.
        """
        # 1. Конвертируем формат сообщений LlamaIndex -> OpenAI
        openai_messages = [
            {"role": m.role.value, "content": m.content} 
            for m in messages
        ]

        # 2. Вызываем наш умный клиент (он сделает кэш, ретрай, телеметрию)
        response_obj = self.smart_client.chat_completion(
            messages=openai_messages,
            model=self.model_name,
            response_format=None, # LlamaIndex ожидает текст, а не JSON-схему здесь
            **kwargs
        )

        # 3. Конвертируем ответ OpenAI -> LlamaIndex
        content = response_obj.choices[0].message.content
        return ChatResponse(
            message=ChatMessage(role="assistant", content=content),
            raw=response_obj
        )

    @llm_completion_callback()
    def complete(self, prompt: str, formatted: bool = False, **kwargs: Any) -> CompletionResponse:
        """
        LlamaIndex иногда использует complete вместо chat.
        """
        return self.chat([ChatMessage(role="user", content=prompt)], **kwargs).message.content

    # --- Streaming (если нужно, можно реализовать, пока заглушки) ---
    @llm_chat_callback()
    def stream_chat(self, messages: List[ChatMessage], **kwargs: Any) -> ChatResponseGen:
        raise NotImplementedError("SmartLlamaLLM does not support streaming yet (caching complexity).")

    @llm_completion_callback()
    def stream_complete(self, prompt: str, formatted: bool = False, **kwargs: Any) -> CompletionResponseGen:
        raise NotImplementedError("SmartLlamaLLM does not support streaming yet.")
    