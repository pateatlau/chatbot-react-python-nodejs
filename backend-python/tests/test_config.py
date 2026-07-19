"""Settings validation and environment-aware startup behavior."""

from __future__ import annotations

import logging

import pytest

from app.core.config import Settings, get_settings
from app.core.logging import get_logger


@pytest.fixture(autouse=True)
def _clear_settings_cache():  # pyright: ignore[reportUnusedFunction]
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_development_settings_load_with_example_placeholders() -> None:
    settings = Settings(
        llm_provider="openai",
        openai_api_key="sk-placeholder",
        app_env="development",
        rate_limit_anonymous_per_minute=30,
        rate_limit_authenticated_per_minute=120,
    )
    settings.validate_startup()
    assert settings.is_development
    assert settings.request_body_limit_bytes == 16 * 1024
    assert settings.log_level == "INFO"
    assert settings.rate_limit_anonymous_per_minute == 30
    assert settings.rate_limit_authenticated_per_minute == 120


def test_missing_provider_key_raises() -> None:
    settings = Settings(llm_provider="openai", openai_api_key=None)
    with pytest.raises(ValueError, match="OPENAI_API_KEY is not set"):
        settings.validate_startup()


def test_production_rejects_default_jwt_secret() -> None:
    settings = Settings(
        app_env="production",
        llm_provider="openai",
        openai_api_key="sk-live",
        jwt_secret="dev-insecure-jwt-secret-change-me",
        database_url="postgresql+asyncpg://prod:prod@db.example.com:5432/chatbot",
        google_client_id="1234567890.apps.googleusercontent.com",
    )
    with pytest.raises(ValueError, match="JWT_SECRET must be explicitly set"):
        settings.validate_startup()


def test_production_rejects_default_database_url() -> None:
    settings = Settings(
        app_env="production",
        llm_provider="openai",
        openai_api_key="sk-live",
        jwt_secret="production-jwt-secret-with-enough-length",
        google_client_id="1234567890.apps.googleusercontent.com",
    )
    with pytest.raises(ValueError, match="DATABASE_URL must be explicitly set"):
        settings.validate_startup()


def test_production_requires_google_client_id() -> None:
    settings = Settings(
        app_env="production",
        llm_provider="openai",
        openai_api_key="sk-live",
        jwt_secret="production-jwt-secret-with-enough-length",
        database_url="postgresql+asyncpg://prod:prod@db.example.com:5432/chatbot",
        google_client_id="",
    )
    with pytest.raises(ValueError, match="GOOGLE_CLIENT_ID must be set"):
        settings.validate_startup()


def test_production_accepts_valid_configuration() -> None:
    settings = Settings(
        app_env="production",
        llm_provider="openai",
        openai_api_key="sk-live",
        jwt_secret="production-jwt-secret-with-enough-length",
        database_url="postgresql+asyncpg://prod:prod@db.example.com:5432/chatbot",
        google_client_id="1234567890.apps.googleusercontent.com",
    )
    settings.validate_startup()


def test_invalid_log_level_rejected() -> None:
    with pytest.raises(ValueError, match="LOG_LEVEL must be one of"):
        Settings.model_validate({"log_level": "VERBOSE"})


def test_log_level_is_normalized_to_uppercase() -> None:
    settings = Settings.model_validate({"log_level": "debug"})
    assert settings.log_level == "DEBUG"


def test_request_body_limit_message_uses_configured_limit() -> None:
    settings = Settings(request_body_limit_bytes=8192)
    assert "8192 byte limit" in settings.request_body_limit_message()


def test_development_warnings_for_insecure_defaults(
    caplog: pytest.LogCaptureFixture,
) -> None:
    settings = Settings(
        app_env="development",
        llm_provider="openai",
        openai_api_key="sk-placeholder",
        jwt_secret="dev-insecure-jwt-secret-change-me",
        google_client_id="",
    )
    logger = get_logger("test.config")
    with caplog.at_level(logging.WARNING, logger="test.config"):
        settings.log_development_warnings(logger)

    messages = " ".join(record.message for record in caplog.records)
    assert "JWT_SECRET" in messages
    assert "GOOGLE_CLIENT_ID" in messages
    assert "DATABASE_URL" in messages


def test_get_settings_caches_result() -> None:
    first = get_settings()
    second = get_settings()
    assert first is second
