from typing import AsyncIterator

from openai import AsyncOpenAI

from app.providers.base import ProviderChunk
from app.schemas.chat import ChatMessageSchema


class OpenAIProvider:
    """LLMProvider adapter backed by the OpenAI Chat Completions API."""

    def __init__(self, api_key: str | None) -> None:
        self._client = AsyncOpenAI(api_key=api_key)

    async def stream_chat(
        self,
        messages: list[ChatMessageSchema],
        model: str,
        temperature: float = 0.7,
    ) -> AsyncIterator[ProviderChunk]:
        stream = await self._client.chat.completions.create(
            model=model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            temperature=temperature,
            stream=True,
        )
        async for event in stream:
            choice = event.choices[0]
            yield ProviderChunk(
                content=choice.delta.content or "",
                finish_reason=choice.finish_reason,
            )

    async def complete_chat(
        self,
        messages: list[ChatMessageSchema],
        model: str,
        temperature: float = 0.7,
    ) -> str:
        response = await self._client.chat.completions.create(
            model=model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            temperature=temperature,
            stream=False,
        )
        return response.choices[0].message.content or ""
