# src/infrastructure/async_llama_adapter.py
import asyncio
from typing import Any, Sequence

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

# Импортируем наш новый Async клиент (предполагаем, что он в infrastructure)
from src.infrastructure.async_smart_client import AsyncSmartOpenAI 

# TODO: Ко всем вызовам методов нужно добавлять a !

class AsyncSmartLlamaLLM(CustomLLM):
    """
    Асинхронный адаптер для LlamaIndex.
    Использует AsyncSmartOpenAI для всех операций.
    """
    model_name: str
    smart_client: AsyncSmartOpenAI
    context_window: int = 128000
    num_output: int = 4096

    @property
    def metadata(self) -> LLMMetadata:
        return LLMMetadata(
            context_window=self.context_window,
            num_output=self.num_output,
            model_name=self.model_name,
            is_chat_model=True,
        )

    # --- АСИНХРОННАЯ РЕАЛИЗАЦИЯ (Главная часть) ---

    @llm_chat_callback()
    async def achat(self, messages: Sequence[ChatMessage], **kwargs: Any) -> ChatResponse:
        """
        Асинхронный чат. LlamaIndex будет вызывать именно этот метод,
        если вы используете 'await query_engine.aquery(...)'.
        """
        # 1. Конвертация LlamaIndex -> OpenAI формат
        openai_messages = [
            {"role": m.role.value, "content": m.content} 
            for m in messages
        ]

        # 2. Асинхронный вызов Smart Client
        # Здесь await, так как chat_completion теперь async
        response_obj = await self.smart_client.chat_completion(
            messages=openai_messages,
            model=self.model_name,
            response_format=None, 
            **kwargs
        )

        # 3. Конвертация OpenAI -> LlamaIndex
        content = response_obj.choices[0].message.content
        return ChatResponse(
            message=ChatMessage(role="assistant", content=content),
            raw=response_obj
        )

    @llm_completion_callback()
    async def acomplete(self, prompt: str, formatted: bool = False, **kwargs: Any) -> CompletionResponse:
        """
        Асинхронное дополнение (completion).
        """
        response = await self.achat([ChatMessage(role="user", content=prompt)], **kwargs)
        return CompletionResponse(text=response.message.content, raw=response.raw)

    # --- СИНХРОННАЯ РЕАЛИЗАЦИЯ (Мост/Совместимость) ---
    
    @llm_chat_callback()
    def chat(self, messages: Sequence[ChatMessage], **kwargs: Any) -> ChatResponse:
        """
        Обертка для синхронного вызова. 
        Внимание: Не используйте это внутри уже запущенного event loop'а!
        """
        return asyncio.run(self.achat(messages, **kwargs))

    @llm_completion_callback()
    def complete(self, prompt: str, formatted: bool = False, **kwargs: Any) -> CompletionResponse:
        return asyncio.run(self.acomplete(prompt, **kwargs))

    # --- Streaming (Заглушки) ---
    
    @llm_chat_callback()
    async def stream_chat(self, messages: Sequence[ChatMessage], **kwargs: Any) -> ChatResponseGen:
        raise NotImplementedError("Streaming not supported due to caching architecture.")

    @llm_completion_callback()
    async def stream_complete(self, prompt: str, formatted: bool = False, **kwargs: Any) -> CompletionResponseGen:
        raise NotImplementedError("Streaming not supported due to caching architecture.")