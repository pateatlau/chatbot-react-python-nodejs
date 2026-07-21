"""Embedding provider factory (single OpenAI backend in V1)."""

from __future__ import annotations

from openai import AsyncOpenAI

from app.ai.embeddings.openai import OpenAIEmbeddingProvider
from app.ai.interfaces.embedding_provider import EmbeddingProvider
from app.core.config import Settings


def create_embedding_provider(settings: Settings) -> EmbeddingProvider:
    """Construct the configured embedding provider.

    V2: add a Redis-backed embedding cache layer here before returning the provider.
    """
    supported_providers = {"openai"}
    if settings.embedding_provider not in supported_providers:
        supported = ", ".join(sorted(supported_providers))
        raise ValueError(
            f"Unsupported EMBEDDING_PROVIDER '{settings.embedding_provider}'. "
            f"Supported providers: {supported}."
        )

    if settings.embedding_provider == "openai":
        if not settings.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY is required when EMBEDDING_PROVIDER=openai. "
                "Set it in backend-python/.env (see .env.example)."
            )
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        return OpenAIEmbeddingProvider(client=client, settings=settings)

    raise ValueError(f"Unsupported EMBEDDING_PROVIDER '{settings.embedding_provider}'.")
