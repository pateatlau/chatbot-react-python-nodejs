"""Correlation ID middleware and propagation tests."""

from __future__ import annotations

import io
import json
import logging
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings, get_settings
from app.core.logging import setup_logging
from app.main import app
from app.middleware.correlation_id import REQUEST_ID_HEADER, resolve_request_id
from app.providers.factory import ProviderFactory
from tests.fakes import FakeProvider


def _mock_provider_factory(provider: FakeProvider):
    def get_provider(
        name: str | None = None, settings: Settings | None = None
    ) -> FakeProvider:
        del name, settings
        return provider

    return staticmethod(get_provider)


def test_resolve_request_id_accepts_valid_uuid() -> None:
    incoming = "550e8400-e29b-41d4-a716-446655440000"
    assert resolve_request_id(incoming) == incoming


def test_resolve_request_id_generates_when_header_missing() -> None:
    generated = resolve_request_id(None)
    uuid.UUID(generated)


def test_resolve_request_id_generates_when_header_invalid() -> None:
    generated = resolve_request_id("not-a-uuid")
    uuid.UUID(generated)


@pytest.mark.anyio
async def test_response_includes_generated_request_id_when_header_absent() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    request_id = response.headers.get(REQUEST_ID_HEADER)
    assert request_id is not None
    uuid.UUID(request_id)


@pytest.mark.anyio
async def test_response_preserves_valid_incoming_request_id() -> None:
    incoming = "550e8400-e29b-41d4-a716-446655440000"
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get(
            "/api/health", headers={REQUEST_ID_HEADER: incoming}
        )

    assert response.headers.get(REQUEST_ID_HEADER) == incoming


@pytest.mark.anyio
async def test_error_response_includes_request_id_header_and_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    get_settings.cache_clear()

    incoming = "6ba7b810-9dad-11d1-80b4-00c04fd430c8"
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post(
            "/api/chat",
            json={"messages": []},
            headers={REQUEST_ID_HEADER: incoming},
        )

    assert response.status_code == 422
    assert response.headers.get(REQUEST_ID_HEADER) == incoming
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["request_id"] == incoming


@pytest.mark.anyio
async def test_request_id_appears_in_structured_logs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    settings = Settings(app_env="production", log_level="INFO")
    setup_logging(settings, handler=handler)

    incoming = "6ba7b810-9dad-11d1-80b4-00c04fd430c8"
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        await client.get("/api/health", headers={REQUEST_ID_HEADER: incoming})

    logged_request_ids = {
        json.loads(line)["request_id"]
        for line in stream.getvalue().splitlines()
        if line.strip() and "request_id" in json.loads(line)
    }
    assert incoming in logged_request_ids


@pytest.mark.anyio
async def test_streaming_response_includes_request_id_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    get_settings.cache_clear()
    monkeypatch.setattr(
        ProviderFactory,
        "get_provider",
        _mock_provider_factory(FakeProvider("streamed")),
    )

    incoming = "6ba7b810-9dad-11d1-80b4-00c04fd430c8"
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        async with client.stream(
            "POST",
            "/api/chat/stream",
            json={"messages": [{"role": "user", "content": "hello"}]},
            headers={REQUEST_ID_HEADER: incoming},
        ) as response:
            assert response.status_code == 200
            assert response.headers.get(REQUEST_ID_HEADER) == incoming
            chunks: list[str] = []
            async for chunk in response.aiter_text():
                chunks.append(chunk)

    assert any("event: start" in chunk for chunk in chunks)
