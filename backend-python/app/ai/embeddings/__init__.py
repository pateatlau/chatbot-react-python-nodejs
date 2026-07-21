"""Embedding provider adapters."""

from app.ai.embeddings.factory import create_embedding_provider
from app.ai.embeddings.openai import OpenAIEmbeddingProvider

__all__ = ["OpenAIEmbeddingProvider", "create_embedding_provider"]
