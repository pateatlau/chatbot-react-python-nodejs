"""Document management API request/response DTOs (Phase 11)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class DocumentSummary(BaseModel):
    id: uuid.UUID
    filename: str
    mime_type: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    documents: list[DocumentSummary]


class DocumentDetailResponse(BaseModel):
    id: uuid.UUID
    filename: str
    mime_type: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class DocumentUploadResponse(BaseModel):
    document_id: uuid.UUID
    status: str
