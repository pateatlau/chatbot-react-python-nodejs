"""OpenAI embedding provider with batching, retry, and latency metrics."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from openai import APIConnectionError, APIStatusError, AsyncOpenAI, RateLimitError

from app.core.config import Settings
from app.core.logging import get_logger
from app.core.retry import is_retryable_exception, retry_async

if TYPE_CHECKING:
    from openai.types import Embedding

_logger = get_logger(__name__)


def _is_retryable_openai_error(exc: BaseException) -> bool:
    if isinstance(exc, (RateLimitError, APIConnectionError)):
        return True
    if isinstance(exc, APIStatusError) and exc.status_code in {429, 503}:
        return True
    return is_retryable_exception(exc)


class OpenAIEmbeddingProvider:
    """EmbeddingProvider backed by the OpenAI embeddings API."""

    def __init__(
        self,
        *,
        client: AsyncOpenAI,
        settings: Settings,
    ) -> None:
        self._client = client
        self._settings = settings

    @property
    def dimensions(self) -> int:
        return self._settings.embedding_dimensions

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        batch_size = self._settings.embedding_batch_size
        all_embeddings: list[list[float]] = []

        for offset in range(0, len(texts), batch_size):
            batch = texts[offset : offset + batch_size]
            batch_embeddings = await self._embed_batch(batch)
            all_embeddings.extend(batch_embeddings)

        return all_embeddings

    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        start = time.perf_counter()

        async def _request() -> list[list[float]]:
            response = await self._client.embeddings.create(
                model=self._settings.embedding_model,
                input=texts,
                dimensions=self._settings.embedding_dimensions,
            )
            vectors = _normalize_embeddings(response.data, expected_count=len(texts))
            validate_embedding_dimensions(
                vectors,
                expected_dimensions=self._settings.embedding_dimensions,
            )
            return vectors

        try:
            embeddings = await retry_async(
                _request,
                is_retryable=_is_retryable_openai_error,
            )
        except APIStatusError as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            _logger.warning(
                "OpenAI embedding provider HTTP error",
                embedding_latency_ms=latency_ms,
                embedding_count=len(texts),
                status_code=exc.status_code,
            )
            raise ValueError(
                "OpenAI embedding provider returned an error "
                f"(status {exc.status_code})."
            ) from exc
        except Exception:
            latency_ms = int((time.perf_counter() - start) * 1000)
            _logger.warning(
                "OpenAI embedding provider failure",
                embedding_latency_ms=latency_ms,
                embedding_count=len(texts),
                exc_info=True,
            )
            raise

        latency_ms = int((time.perf_counter() - start) * 1000)
        _logger.info(
            "OpenAI embeddings batch completed",
            embedding_latency_ms=latency_ms,
            embedding_count=len(texts),
        )
        return embeddings


def _normalize_embeddings(
    data: list[Embedding],
    *,
    expected_count: int,
) -> list[list[float]]:
    if len(data) != expected_count:
        raise ValueError(
            f"Embedding API returned {len(data)} vectors; expected {expected_count}."
        )

    ordered = sorted(data, key=lambda item: item.index)
    return [list(item.embedding) for item in ordered]


def validate_embedding_dimensions(
    vectors: list[list[float]],
    *,
    expected_dimensions: int,
) -> None:
    """Raise when any vector length does not match configured dimensions."""
    for index, vector in enumerate(vectors):
        if len(vector) != expected_dimensions:
            raise ValueError(
                "Embedding dimension mismatch at index "
                f"{index}: expected {expected_dimensions}, got {len(vector)}."
            )
