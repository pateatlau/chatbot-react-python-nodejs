"""Embedding provider protocol for document and query vectorization."""

from __future__ import annotations

from typing import Protocol


class EmbeddingProvider(Protocol):
    """Generate dense vectors for text inputs (one vector per input, same order)."""

    @property
    def dimensions(self) -> int: ...

    async def embed_texts(self, texts: list[str]) -> list[list[float]]: ...
