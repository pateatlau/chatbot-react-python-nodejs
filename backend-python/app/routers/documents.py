"""Document management HTTP endpoints (Phase 11)."""

from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, Depends, File, UploadFile

from app.ai.deps import get_knowledge_service
from app.core.caller import CallerContext, require_authenticated_caller
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.logging import bind_context, get_logger
from app.db.models import Document
from app.schemas.documents import (
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentSummary,
    DocumentUploadResponse,
)
from app.services.document_service import DocumentServiceError
from app.services.knowledge_service import KnowledgeService
from app.services.quota_service import UploadQuotaExceededError

router = APIRouter()
logger = get_logger(__name__)


def _to_summary(document: Document) -> DocumentSummary:
    return DocumentSummary(
        id=document.id,
        filename=document.filename,
        mime_type=document.mime_type,
        status=document.status,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


def _to_detail(document: Document) -> DocumentDetailResponse:
    return DocumentDetailResponse(
        id=document.id,
        filename=document.filename,
        mime_type=document.mime_type,
        status=document.status,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


@router.post("/api/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    caller: CallerContext = Depends(require_authenticated_caller),
    settings: Settings = Depends(get_settings),
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
) -> DocumentUploadResponse:
    assert caller.user_id is not None
    bind_context(user_id=str(caller.user_id))
    logger.info(
        "Document upload accepted",
        route="/api/documents/upload",
        method="POST",
    )

    file_bytes = await file.read()
    filename = file.filename or "upload"
    mime_type = file.content_type

    try:
        document_id = await asyncio.wait_for(
            knowledge_service.ingest_document(
                caller.user_id,
                file_bytes,
                filename,
                mime_type,
            ),
            timeout=settings.request_timeout_seconds,
        )
    except asyncio.TimeoutError as exc:
        raise AppError(
            code="request_timeout",
            message=(
                f"Document ingestion exceeded the {settings.request_timeout_seconds} "
                "second timeout."
            ),
            status_code=408,
        ) from exc
    except UploadQuotaExceededError:
        raise
    except DocumentServiceError:
        raise
    except Exception as exc:
        if isinstance(exc, AppError):
            raise
        raise AppError(
            code="ingestion_failed",
            message="Document ingestion failed.",
            status_code=500,
        ) from exc

    document = await knowledge_service.get_document(caller.user_id, document_id)
    return DocumentUploadResponse(document_id=document.id, status=document.status)


@router.get("/api/documents", response_model=DocumentListResponse)
async def list_documents(
    caller: CallerContext = Depends(require_authenticated_caller),
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
) -> DocumentListResponse:
    assert caller.user_id is not None
    bind_context(user_id=str(caller.user_id))
    documents = await knowledge_service.list_documents(caller.user_id)
    return DocumentListResponse(documents=[_to_summary(doc) for doc in documents])


@router.get("/api/documents/{document_id}", response_model=DocumentDetailResponse)
async def get_document(
    document_id: uuid.UUID,
    caller: CallerContext = Depends(require_authenticated_caller),
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
) -> DocumentDetailResponse:
    assert caller.user_id is not None
    bind_context(user_id=str(caller.user_id))
    document = await knowledge_service.get_document(caller.user_id, document_id)
    return _to_detail(document)


@router.delete("/api/documents/{document_id}", status_code=204)
async def delete_document(
    document_id: uuid.UUID,
    caller: CallerContext = Depends(require_authenticated_caller),
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
) -> None:
    assert caller.user_id is not None
    bind_context(user_id=str(caller.user_id))
    await knowledge_service.delete_document(caller.user_id, document_id)
