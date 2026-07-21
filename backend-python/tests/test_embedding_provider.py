"""Unit tests for embedding providers (mocked OpenAI API)."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from openai import APIStatusError, AsyncOpenAI, RateLimitError

from app.ai.embeddings.factory import create_embedding_provider
from app.ai.embeddings.openai import (
    OpenAIEmbeddingProvider,
    validate_embedding_dimensions,
)
from app.core.config import Settings


def _embedding_item(index: int, vector: list[float]) -> SimpleNamespace:
    return SimpleNamespace(index=index, embedding=vector)


def _make_response(items: list[SimpleNamespace]) -> SimpleNamespace:
    return SimpleNamespace(data=items)


def _vector(dimensions: int, seed: float = 0.1) -> list[float]:
    return [seed + (index * 0.001) for index in range(dimensions)]


def _provider(
    *,
    settings: Settings | None = None,
    client: AsyncMock | None = None,
) -> OpenAIEmbeddingProvider:
    resolved = settings or Settings(
        openai_api_key="test-key",
        embedding_dimensions=4,
        embedding_batch_size=2,
    )
    return OpenAIEmbeddingProvider(
        client=client or AsyncMock(spec=AsyncOpenAI),
        settings=resolved,
    )


@pytest.mark.anyio
async def test_embed_texts_returns_vectors_with_configured_dimensions() -> None:
    client = AsyncMock(spec=AsyncOpenAI)
    client.embeddings.create = AsyncMock(
        return_value=_make_response([_embedding_item(0, _vector(4))])
    )
    provider = _provider(client=client)

    vectors = await provider.embed_texts(["hello"])

    assert len(vectors) == 1
    assert len(vectors[0]) == provider.dimensions == 4
    client.embeddings.create.assert_awaited_once()


@pytest.mark.anyio
async def test_embed_texts_empty_list_skips_api_call() -> None:
    client = AsyncMock(spec=AsyncOpenAI)
    client.embeddings.create = AsyncMock()
    provider = _provider(client=client)

    assert await provider.embed_texts([]) == []
    client.embeddings.create.assert_not_called()


@pytest.mark.anyio
async def test_embed_texts_single_text_returns_one_vector() -> None:
    client = AsyncMock(spec=AsyncOpenAI)
    client.embeddings.create = AsyncMock(
        return_value=_make_response([_embedding_item(0, _vector(4, seed=0.2))])
    )
    provider = _provider(client=client)

    vectors = await provider.embed_texts(["single"])

    assert len(vectors) == 1


@pytest.mark.anyio
async def test_embed_texts_batches_when_input_exceeds_batch_size() -> None:
    client = AsyncMock(spec=AsyncOpenAI)
    client.embeddings.create = AsyncMock(
        side_effect=[
            _make_response(
                [
                    _embedding_item(0, _vector(4, seed=0.1)),
                    _embedding_item(1, _vector(4, seed=0.2)),
                ]
            ),
            _make_response(
                [
                    _embedding_item(0, _vector(4, seed=0.3)),
                    _embedding_item(1, _vector(4, seed=0.4)),
                ]
            ),
            _make_response([_embedding_item(0, _vector(4, seed=0.5))]),
        ]
    )
    provider = _provider(client=client)

    vectors = await provider.embed_texts(["a", "b", "c", "d", "e"])

    assert len(vectors) == 5
    assert client.embeddings.create.await_count == 3


@pytest.mark.anyio
async def test_embed_texts_retries_on_rate_limit_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = AsyncMock(spec=AsyncOpenAI)
    request = httpx.Request("POST", "https://api.openai.com/v1/embeddings")
    response = httpx.Response(429, request=request)
    rate_limit_error = RateLimitError(
        "rate limit",
        response=response,
        body=None,
    )
    client.embeddings.create = AsyncMock(
        side_effect=[
            rate_limit_error,
            _make_response([_embedding_item(0, _vector(4))]),
        ]
    )
    provider = _provider(client=client)

    sleep_calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr("app.core.retry.asyncio.sleep", fake_sleep)

    vectors = await provider.embed_texts(["retry me"])

    assert len(vectors) == 1
    assert client.embeddings.create.await_count == 2
    assert sleep_calls


@pytest.mark.anyio
async def test_embed_texts_retries_on_503_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = AsyncMock(spec=AsyncOpenAI)
    request = httpx.Request("POST", "https://api.openai.com/v1/embeddings")
    response = httpx.Response(503, request=request)
    service_unavailable = APIStatusError(
        "service unavailable",
        response=response,
        body=None,
    )
    client.embeddings.create = AsyncMock(
        side_effect=[
            service_unavailable,
            _make_response([_embedding_item(0, _vector(4))]),
        ]
    )
    provider = _provider(client=client)
    monkeypatch.setattr("app.core.retry.asyncio.sleep", AsyncMock())

    vectors = await provider.embed_texts(["retry 503"])

    assert len(vectors) == 1
    assert client.embeddings.create.await_count == 2


def test_validate_embedding_dimensions_raises_on_mismatch() -> None:
    with pytest.raises(ValueError, match="Embedding dimension mismatch"):
        validate_embedding_dimensions([[0.1, 0.2]], expected_dimensions=4)


@pytest.mark.anyio
async def test_embed_texts_raises_on_dimension_mismatch_from_api() -> None:
    client = AsyncMock(spec=AsyncOpenAI)
    client.embeddings.create = AsyncMock(
        return_value=_make_response([_embedding_item(0, [0.1, 0.2])])
    )
    provider = _provider(client=client)

    with pytest.raises(ValueError, match="Embedding dimension mismatch"):
        await provider.embed_texts(["bad dimensions"])


@pytest.mark.anyio
async def test_embedding_latency_ms_emitted_on_successful_batch(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="app.ai.embeddings.openai")
    client = AsyncMock(spec=AsyncOpenAI)
    client.embeddings.create = AsyncMock(
        return_value=_make_response([_embedding_item(0, _vector(4))])
    )
    provider = _provider(client=client)

    await provider.embed_texts(["latency"])

    records = [
        record
        for record in caplog.records
        if record.name == "app.ai.embeddings.openai"
        and "OpenAI embeddings batch completed" in record.message
    ]
    assert len(records) == 1
    assert getattr(records[0], "embedding_latency_ms") is not None
    assert getattr(records[0], "embedding_count") == 1
    assert "latency" not in caplog.text


@pytest.mark.anyio
async def test_embed_texts_does_not_log_input_text_or_vectors(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="app.ai.embeddings.openai")
    secret_text = "super-secret-chunk-content"
    secret_vector = _vector(4, seed=0.9)
    client = AsyncMock(spec=AsyncOpenAI)
    client.embeddings.create = AsyncMock(
        return_value=_make_response([_embedding_item(0, secret_vector)])
    )
    provider = _provider(client=client)

    await provider.embed_texts([secret_text])

    assert secret_text not in caplog.text
    assert str(secret_vector) not in caplog.text


def test_create_embedding_provider_openai() -> None:
    settings = Settings(openai_api_key="test-key", embedding_provider="openai")
    provider = create_embedding_provider(settings)
    assert provider.dimensions == settings.embedding_dimensions


def test_create_embedding_provider_requires_openai_api_key() -> None:
    settings = Settings(openai_api_key=None, embedding_provider="openai")
    with pytest.raises(ValueError, match="OPENAI_API_KEY is required"):
        create_embedding_provider(settings)


def test_create_embedding_provider_rejects_unsupported_provider() -> None:
    settings = Settings(
        openai_api_key="test-key",
        embedding_provider="gemini",
    )
    with pytest.raises(ValueError, match="Unsupported EMBEDDING_PROVIDER"):
        create_embedding_provider(settings)
