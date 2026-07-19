"""Centralized error envelope and exception handler tests."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import OperationalError

from app.core.config import get_settings
from app.core.errors import (
    RateLimitExceededError,
    error_response,
    register_exception_handlers,
)
from app.core.security import InvalidGoogleTokenError
from app.main import app
from app.middleware.correlation_id import (
    REQUEST_ID_HEADER,
    correlation_id_middleware,
    resolve_request_id,
)
from app.routers.auth import get_google_verifier, get_user_store
from app.services.chat_service import ProviderNotAllowedError
from tests.fakes import FakeGoogleVerifier, FakeUserStore


def _register_test_middleware(test_app) -> None:
    @test_app.middleware("http")
    async def assign_correlation_id(request, call_next):
        return await correlation_id_middleware(request, call_next)


def _assert_error_envelope(
    body: dict[str, object],
    *,
    code: str,
    status_code: int,
    response_headers: dict[str, str],
) -> None:
    error = body["error"]
    assert isinstance(error, dict)
    assert error["code"] == code
    assert isinstance(error["message"], str) and error["message"]
    request_id = error.get("request_id")
    assert request_id is not None
    uuid.UUID(str(request_id))
    header_request_id = response_headers.get(REQUEST_ID_HEADER) or response_headers.get(
        REQUEST_ID_HEADER.lower()
    )
    assert header_request_id == request_id
    assert status_code >= 400


def test_error_response_includes_request_id() -> None:
    request_id = resolve_request_id("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
    from app.middleware import correlation_id as correlation_module

    token = correlation_module._set_request_id(request_id)
    try:
        response = error_response(400, "validation_error", "bad input")
    finally:
        correlation_module._reset_request_id(token)

    body = response.body
    import json

    payload = json.loads(bytes(body))
    assert payload["error"]["request_id"] == request_id
    assert response.headers[REQUEST_ID_HEADER] == request_id


@pytest.mark.anyio
async def test_validation_error_envelope() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post("/api/chat", json={"messages": []})

    body = response.json()
    _assert_error_envelope(
        body,
        code="validation_error",
        status_code=response.status_code,
        response_headers=dict(response.headers),
    )
    assert response.status_code == 422


@pytest.mark.anyio
async def test_authentication_error_envelope() -> None:
    verifier = FakeGoogleVerifier(error=InvalidGoogleTokenError())
    store = FakeUserStore()
    app.dependency_overrides[get_google_verifier] = lambda: verifier
    app.dependency_overrides[get_user_store] = lambda: store

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.post(
                "/api/auth/google", json={"id_token": "bad-token"}
            )
    finally:
        app.dependency_overrides.clear()

    body = response.json()
    _assert_error_envelope(
        body,
        code="invalid_google_token",
        status_code=response.status_code,
        response_headers=dict(response.headers),
    )
    assert response.status_code == 401


@pytest.mark.anyio
async def test_authorization_error_envelope() -> None:
    from fastapi import FastAPI

    test_app = FastAPI()
    _register_test_middleware(test_app)
    register_exception_handlers(test_app)

    @test_app.get("/forbidden")
    async def _forbidden() -> None:
        raise ProviderNotAllowedError()

    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://testserver"
    ) as client:
        response = await client.get("/forbidden")

    body = response.json()
    _assert_error_envelope(
        body,
        code="provider_not_allowed",
        status_code=response.status_code,
        response_headers=dict(response.headers),
    )
    assert response.status_code == 403


@pytest.mark.anyio
async def test_rate_limit_error_envelope_and_retry_after() -> None:
    from fastapi import FastAPI

    test_app = FastAPI()
    _register_test_middleware(test_app)
    register_exception_handlers(test_app)

    @test_app.get("/limited")
    async def _limited() -> None:
        raise RateLimitExceededError(retry_after_seconds=30)

    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://testserver"
    ) as client:
        response = await client.get("/limited")

    body = response.json()
    _assert_error_envelope(
        body,
        code="rate_limit_exceeded",
        status_code=response.status_code,
        response_headers=dict(response.headers),
    )
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "30"


@pytest.mark.anyio
async def test_database_error_envelope_on_readiness_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connect_cm = AsyncMock()
    connect_cm.__aenter__ = AsyncMock(
        side_effect=OperationalError("SELECT 1", {}, Exception("db down"))
    )
    connect_cm.__aexit__ = AsyncMock(return_value=False)

    failing_engine = MagicMock()
    failing_engine.connect = MagicMock(return_value=connect_cm)

    monkeypatch.setattr("app.routers.health.get_engine", lambda: failing_engine)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/api/health/ready")

    body = response.json()
    _assert_error_envelope(
        body,
        code="database_error",
        status_code=response.status_code,
        response_headers=dict(response.headers),
    )
    assert response.status_code == 503


@pytest.mark.anyio
async def test_internal_error_hides_details_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fastapi import FastAPI

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "production-jwt-secret-with-enough-length")
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+asyncpg://prod:prod@db.example.com/chatbot"
    )
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "1234567890.apps.googleusercontent.com")
    get_settings.cache_clear()

    test_app = FastAPI()
    _register_test_middleware(test_app)
    register_exception_handlers(test_app)

    @test_app.get("/boom")
    async def _boom() -> None:
        raise RuntimeError("super-secret internals")

    # ServerErrorMiddleware always re-raises after sending the 500 response.
    async with AsyncClient(
        transport=ASGITransport(app=test_app, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/boom")

    body = response.json()
    assert response.status_code == 500
    assert body["error"]["code"] == "internal_error"
    assert "super-secret" not in body["error"]["message"]
    assert "RuntimeError" not in body["error"]["message"]
    get_settings.cache_clear()


@pytest.mark.anyio
async def test_internal_error_includes_exception_name_in_development(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fastapi import FastAPI

    monkeypatch.setenv("APP_ENV", "development")
    get_settings.cache_clear()

    test_app = FastAPI()
    _register_test_middleware(test_app)
    register_exception_handlers(test_app)

    @test_app.get("/boom")
    async def _boom() -> None:
        raise RuntimeError("dev details")

    async with AsyncClient(
        transport=ASGITransport(app=test_app, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/boom")

    body = response.json()
    assert response.status_code == 500
    assert body["error"]["code"] == "internal_error"
    assert "RuntimeError" in body["error"]["message"]
    get_settings.cache_clear()
