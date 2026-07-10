from typing import cast

import pytest
from httpx import ASGITransport, AsyncClient
from pytest import MonkeyPatch

from app.core.config import Settings
from app.main import app
from app.schemas.chat import ChatMessageSchema
from app.providers.factory import ProviderFactory
from tests.fakes import FakeProvider


class ErroringProvider(FakeProvider):
    async def complete_chat(
        self,
        messages: list[ChatMessageSchema],
        model: str,
        temperature: float = 0.7,
    ) -> str:
        del messages, model, temperature
        raise RuntimeError("provider exploded")


def _mock_provider_factory(provider: FakeProvider):
    def get_provider(
        name: str | None = None, settings: Settings | None = None
    ) -> FakeProvider:
        del name, settings
        return provider

    return staticmethod(get_provider)


@pytest.mark.anyio
async def test_chat_endpoint_returns_assistant_response(
    monkeypatch: MonkeyPatch,
) -> None:
    fake_provider = FakeProvider("Fake completion response")

    monkeypatch.setattr(
        ProviderFactory,
        "get_provider",
        _mock_provider_factory(fake_provider),
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post(
            "/api/chat",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "provider": "openai",
                "model": "gpt-4o-mini",
            },
        )

    body = response.json()
    assert response.status_code == 200
    assert body["role"] == "assistant"
    assert body["content"] == "Fake completion response"
    assert body["provider"] == "openai"
    assert body["model"] == "gpt-4o-mini"


@pytest.mark.anyio
async def test_chat_endpoint_returns_validation_error_for_empty_messages() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post("/api/chat", json={"messages": []})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.anyio
async def test_chat_endpoint_normalizes_provider_errors(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ProviderFactory,
        "get_provider",
        _mock_provider_factory(cast(FakeProvider, ErroringProvider())),
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post(
            "/api/chat",
            json={"messages": [{"role": "user", "content": "Hello"}]},
        )

    assert response.status_code == 502
    assert response.json() == {
        "error": {
            "code": "provider_error",
            "message": "Upstream provider failed.",
        }
    }