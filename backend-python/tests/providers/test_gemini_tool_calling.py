"""Gemini provider tool-calling adapter tests."""

from __future__ import annotations

from typing import Any

import pytest

from app.providers.base import ProviderToolCall
from app.providers.gemini_provider import GeminiProvider
from app.schemas.chat import ChatMessageSchema

pytestmark = pytest.mark.anyio


class _FakeFunctionCall:
    def __init__(self) -> None:
        self.id = "call_gemini"
        self.name = "web_search"
        self.args = {"query": "weather"}


class _FakePart:
    def __init__(self, *, function_call: Any | None = None, text: str | None = None):
        self.function_call = function_call
        self.text = text


class _FakeContent:
    def __init__(self, parts: list[Any]) -> None:
        self.parts = parts


class _FakeCandidate:
    def __init__(self, parts: list[Any]) -> None:
        self.content = _FakeContent(parts)
        self.finish_reason = "STOP"


class _FakeGeminiResponse:
    def __init__(self, parts: list[Any]) -> None:
        self.candidates = [_FakeCandidate(parts)]
        self.usage_metadata = None


async def test_gemini_complete_chat_with_tools_parses_tool_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = GeminiProvider(api_key="test-key")
    monkeypatch.setattr(
        provider,
        "_generate_content_with_tools",
        lambda **kwargs: _FakeGeminiResponse(
            [_FakePart(function_call=_FakeFunctionCall())]
        ),
    )

    completion = await provider.complete_chat_with_tools(
        [ChatMessageSchema(role="user", content="What's the weather?")],
        model="gemini-2.0-flash",
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "Search the web",
                    "parameters": {"type": "object"},
                },
            }
        ],
    )

    assert completion.tool_calls == [
        ProviderToolCall(
            id="call_gemini", name="web_search", arguments={"query": "weather"}
        )
    ]
    assert completion.content is None


async def test_gemini_complete_chat_with_tools_handles_direct_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = GeminiProvider(api_key="test-key")
    monkeypatch.setattr(
        provider,
        "_generate_content_with_tools",
        lambda **kwargs: _FakeGeminiResponse([_FakePart(text="Direct answer")]),
    )

    completion = await provider.complete_chat_with_tools(
        [ChatMessageSchema(role="user", content="Hello")],
        model="gemini-2.0-flash",
        tools=[],
    )

    assert completion.tool_calls == []
    assert completion.content == "Direct answer"


async def test_gemini_complete_chat_with_tools_handles_malformed_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = GeminiProvider(api_key="test-key")

    class _BadFunctionCall:
        id = "call_bad"
        name = "web_search"
        args = "not-a-dict"

    monkeypatch.setattr(
        provider,
        "_generate_content_with_tools",
        lambda **kwargs: _FakeGeminiResponse(
            [_FakePart(function_call=_BadFunctionCall())]
        ),
    )

    completion = await provider.complete_chat_with_tools(
        [ChatMessageSchema(role="user", content="Search")],
        model="gemini-2.0-flash",
        tools=[],
    )

    assert completion.tool_calls == [
        ProviderToolCall(id="call_bad", name="web_search", arguments={})
    ]
