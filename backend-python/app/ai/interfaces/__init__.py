"""AI framework protocols added incrementally per phase."""

from __future__ import annotations

from typing import TYPE_CHECKING

__all__ = ["EmbeddingProvider", "ToolHandler"]

if TYPE_CHECKING:
    from app.ai.interfaces.embedding_provider import EmbeddingProvider
    from app.ai.interfaces.tool_handler import ToolHandler


def __getattr__(name: str) -> object:
    if name == "EmbeddingProvider":
        from app.ai.interfaces.embedding_provider import EmbeddingProvider

        return EmbeddingProvider
    if name == "ToolHandler":
        from app.ai.interfaces.tool_handler import ToolHandler

        return ToolHandler
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
