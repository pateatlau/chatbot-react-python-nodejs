"""Generic RAG API request/response DTOs (Phase 11)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field, field_validator

from app.core.config import Settings
from app.schemas.chat import ProviderName


def _max_message_length() -> int:
    return Settings().max_message_length


class RAGAskRequest(BaseModel):
    question: str = Field(min_length=1)
    prompt_template: str | None = None
    instructions: str | None = None
    top_k: int | None = Field(default=None, ge=1)
    temperature: float | None = Field(default=None, ge=0, le=2)

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("question must not be blank")
        max_message_length = _max_message_length()
        if len(trimmed) > max_message_length:
            raise ValueError(
                f"question must be at most {max_message_length} characters"
            )
        return trimmed


class RetrievedChunkMetaSchema(BaseModel):
    chunk_id: uuid.UUID | None
    document_id: uuid.UUID | None
    chunk_index: int | None
    score: float


class RAGAskResponse(BaseModel):
    answer: str
    retrieved_chunks: list[RetrievedChunkMetaSchema]
    truncated: bool
    model: str
    provider: ProviderName
    retrieval_latency_ms: int | None = None
    llm_latency_ms: int | None = None
