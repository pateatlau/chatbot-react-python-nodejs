"""LLM step helpers for the agent execution loop (Phase 8)."""

from __future__ import annotations

import asyncio
from typing import Any, cast

from app.ai.agent.interfaces.streaming import StreamPublisher
from app.ai.agent.models.config import AgentConfig
from app.ai.agent.models.events import AgentStreamEvent
from app.ai.agent.models.messages import AgentMessage
from app.ai.agent.models.request import AgentRequest
from app.ai.agent.retry import llm_retry_policy_from_config, retry_operation
from app.ai.agent.scratchpad.scratchpad import Scratchpad
from app.providers.base import LLMProvider, ProviderCompletion


async def stream_final_answer(
    provider: LLMProvider,
    *,
    request: AgentRequest,
    scratchpad: Scratchpad,
    execution_id: str,
    publisher: StreamPublisher,
) -> str:
    """Generate and stream the final answer via the provider."""
    messages = _scratchpad_to_chat_messages(scratchpad)
    content_parts: list[str] = []
    stream = provider.stream_chat(
        cast(Any, messages),
        request.model,
        request.temperature,
        max_tokens=request.max_tokens,
    )
    async for chunk in stream:
        token = chunk.get("content") or ""
        if token:
            await publisher.publish(AgentStreamEvent.token(execution_id, content=token))
            content_parts.append(token)
    return "".join(content_parts)


async def emit_final_content_as_tokens(
    *,
    content: str,
    execution_id: str,
    publisher: StreamPublisher,
) -> None:
    """Publish precomputed final answer text as token events."""
    if not content:
        return

    words = content.split(" ")
    for index, word in enumerate(words):
        token = word if index == len(words) - 1 else f"{word} "
        await publisher.publish(AgentStreamEvent.token(execution_id, content=token))


async def complete_llm_step(
    provider: LLMProvider,
    *,
    request: AgentRequest,
    scratchpad: Scratchpad,
) -> ProviderCompletion:
    """Run a non-streaming LLM completion for an intermediate step."""
    messages = _scratchpad_to_chat_messages(scratchpad)
    config = request.config or AgentConfig()

    async def operation() -> ProviderCompletion:
        call = provider.complete_chat(
            cast(Any, messages),
            request.model,
            request.temperature,
            max_tokens=request.max_tokens,
        )
        if config.timeout_seconds is None:
            return await call
        return await asyncio.wait_for(call, timeout=config.timeout_seconds)

    policy = llm_retry_policy_from_config(config)
    return await retry_operation(operation, policy)


def _scratchpad_to_chat_messages(scratchpad: Scratchpad) -> list[AgentMessage]:
    """Convert scratchpad conversational entries for provider chat calls."""
    messages: list[AgentMessage] = []
    for message in scratchpad.to_message_context():
        if isinstance(message, AgentMessage):
            if message.role in ("system", "user", "assistant"):
                messages.append(message)
    return messages
