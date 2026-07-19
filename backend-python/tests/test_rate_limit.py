"""HTTP rate limiting middleware tests."""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.core.security import create_access_token
from app.main import app
from app.middleware.correlation_id import REQUEST_ID_HEADER
from app.middleware.rate_limit import reset_rate_limiter


@pytest.mark.anyio
async def test_health_endpoints_exempt_from_rate_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RATE_LIMIT_ANONYMOUS_PER_MINUTE", "1")
    get_settings.cache_clear()
    reset_rate_limiter()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        health = await client.get("/api/health")
        ready = await client.get("/api/health/ready")
        for _ in range(4):
            await client.get("/api/health")
            await client.get("/api/health/ready")

    assert health.status_code == 200
    assert ready.status_code in {200, 503}


@pytest.mark.anyio
async def test_anonymous_rate_limit_enforced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RATE_LIMIT_ANONYMOUS_PER_MINUTE", "3")
    get_settings.cache_clear()
    reset_rate_limiter()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        for _ in range(3):
            allowed = await client.get("/")
            assert allowed.status_code == 200

        blocked = await client.get("/")

    assert blocked.status_code == 429
    body = blocked.json()
    assert body["error"]["code"] == "rate_limit_exceeded"
    assert body["error"]["request_id"] is not None
    retry_after = int(blocked.headers["Retry-After"])
    assert 1 <= retry_after <= 60
    assert blocked.headers.get(REQUEST_ID_HEADER) or blocked.headers.get(
        REQUEST_ID_HEADER.lower()
    )


@pytest.mark.anyio
async def test_authenticated_callers_have_higher_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RATE_LIMIT_ANONYMOUS_PER_MINUTE", "2")
    monkeypatch.setenv("RATE_LIMIT_AUTHENTICATED_PER_MINUTE", "4")
    get_settings.cache_clear()
    reset_rate_limiter()

    settings = get_settings()
    user_id = uuid.uuid4()
    token = create_access_token(user_id=user_id, settings=settings)
    auth_headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        for _ in range(2):
            anonymous = await client.get("/")
            assert anonymous.status_code == 200

        blocked_anonymous = await client.get("/")
        assert blocked_anonymous.status_code == 429

        reset_rate_limiter()

        for _ in range(4):
            authenticated = await client.get("/", headers=auth_headers)
            assert authenticated.status_code == 200

        blocked_authenticated = await client.get("/", headers=auth_headers)

    assert blocked_authenticated.status_code == 429
    assert blocked_authenticated.json()["error"]["code"] == "rate_limit_exceeded"
