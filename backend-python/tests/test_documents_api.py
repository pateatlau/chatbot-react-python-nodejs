"""Document management API integration tests (Phase 11)."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.ai.deps import get_knowledge_service
from app.ai.documents.pipeline import IngestionPipeline
from app.ai.vectorstores.pgvector import PgVectorStore
from app.core.config import Settings, get_settings
from app.core.caller import CallerContext, get_current_caller
from app.core.security import create_access_token
from app.db.identity import SqlUserStore
from app.main import DOCUMENT_UPLOAD_PATH, app, enforce_request_size
from app.services.knowledge_service import KnowledgeService
from app.services.quota_service import QuotaService
from tests.fakes import FakeUploadQuotaStore
from fastapi import Request, Response
from starlette.types import Message, Scope

FIXTURES = Path(__file__).resolve().parent / "data" / "documents"
DIMENSIONS = 1536


class _FakeEmbeddingProvider:
    dimensions = DIMENSIONS

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [
            [float(index % DIMENSIONS), 0.0] + [0.0] * (DIMENSIONS - 2)
            for index, _ in enumerate(texts)
        ]


async def _pgvector_available(session) -> bool:
    try:
        result = await session.scalar(
            text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
        )
        return result == 1
    except Exception:
        return False


async def _make_user(session) -> uuid.UUID:
    user = await SqlUserStore(session).create(
        sub=f"docs-api-{uuid.uuid4()}",
        email=None,
        name=None,
        picture=None,
    )
    return user.id


def _auth_headers(user_id: uuid.UUID) -> dict[str, str]:
    token = create_access_token(user_id=user_id, settings=get_settings())
    return {"Authorization": f"Bearer {token}"}


def _knowledge_service(
    session, *, settings: Settings | None = None
) -> KnowledgeService:
    resolved_settings = settings or Settings(openai_api_key="test-key")
    pipeline = IngestionPipeline(
        resolved_settings, embedding_provider=_FakeEmbeddingProvider()
    )
    vector_store = PgVectorStore(session, resolved_settings)
    quota_service = QuotaService(
        store=_NoopGuestQuotaStore(),
        upload_store=FakeUploadQuotaStore(),
        settings=resolved_settings,
    )
    return KnowledgeService(
        session=session,
        settings=resolved_settings,
        pipeline=pipeline,
        vector_store=vector_store,
        quota_service=quota_service,
    )


class _NoopGuestQuotaStore:
    async def get_message_count(self, guest_id: object, window_start: object) -> int:
        del guest_id, window_start
        return 0

    async def increment(
        self,
        guest_id: object,
        window_start: object,
        *,
        tokens: int = 0,
    ) -> None:
        del guest_id, window_start, tokens


@pytest.fixture
async def pgvector_session(db_session):
    if not await _pgvector_available(db_session):
        pytest.skip("pgvector extension not available — run alembic upgrade head")
    yield db_session


@pytest.fixture(autouse=True)
def _clear_dependency_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def knowledge_service_override(pgvector_session):
    def _override() -> KnowledgeService:
        return _knowledge_service(pgvector_session)

    app.dependency_overrides[get_knowledge_service] = _override


@pytest.mark.anyio
async def test_documents_api_lifecycle(
    pgvector_session,
    knowledge_service_override,
) -> None:
    user_id = await _make_user(pgvector_session)
    headers = _auth_headers(user_id)
    file_bytes = (FIXTURES / "sample.txt").read_bytes()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        upload = await client.post(
            "/api/documents/upload",
            files={"file": ("sample.txt", file_bytes, "text/plain")},
            headers=headers,
        )
        assert upload.status_code == 200
        upload_body = upload.json()
        document_id = upload_body["document_id"]
        assert upload_body["status"] == "ready"

        listed = await client.get("/api/documents", headers=headers)
        assert listed.status_code == 200
        documents = listed.json()["documents"]
        assert len(documents) == 1
        assert documents[0]["id"] == document_id
        assert documents[0]["filename"] == "sample.txt"
        assert documents[0]["status"] == "ready"

        detail = await client.get(f"/api/documents/{document_id}", headers=headers)
        assert detail.status_code == 200
        assert detail.json()["id"] == document_id
        assert detail.json()["status"] == "ready"

        deleted = await client.delete(f"/api/documents/{document_id}", headers=headers)
        assert deleted.status_code == 204

        missing = await client.get(f"/api/documents/{document_id}", headers=headers)
        assert missing.status_code == 404
        assert missing.json()["error"]["code"] == "document_not_found"


@pytest.fixture
def guest_caller_override():
    async def _override() -> CallerContext:
        return CallerContext.anonymous(guest_id=uuid.uuid4())

    app.dependency_overrides[get_current_caller] = _override
    yield
    app.dependency_overrides.pop(get_current_caller, None)


@pytest.mark.anyio
async def test_documents_api_guest_upload_returns_401(guest_caller_override) -> None:
    file_bytes = (FIXTURES / "sample.txt").read_bytes()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post(
            "/api/documents/upload",
            files={"file": ("sample.txt", file_bytes, "text/plain")},
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/documents"),
        ("GET", f"/api/documents/{uuid.uuid4()}"),
        ("DELETE", f"/api/documents/{uuid.uuid4()}"),
    ],
)
async def test_documents_api_guest_list_get_delete_returns_401(
    guest_caller_override,
    method: str,
    path: str,
) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.request(method, path)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"


@pytest.mark.anyio
async def test_documents_api_cross_user_get_and_delete_return_404(
    pgvector_session,
    knowledge_service_override,
) -> None:
    owner_id = await _make_user(pgvector_session)
    other_id = await _make_user(pgvector_session)
    service = _knowledge_service(pgvector_session)
    document_id = await service.ingest_document(
        user_id=owner_id,
        file_bytes=(FIXTURES / "sample.txt").read_bytes(),
        filename="sample.txt",
        mime_type="text/plain",
    )
    other_headers = _auth_headers(other_id)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        get_response = await client.get(
            f"/api/documents/{document_id}",
            headers=other_headers,
        )
        delete_response = await client.delete(
            f"/api/documents/{document_id}",
            headers=other_headers,
        )

    assert get_response.status_code == 404
    assert get_response.json()["error"]["code"] == "document_not_found"
    assert delete_response.status_code == 404
    assert delete_response.json()["error"]["code"] == "document_not_found"


@pytest.mark.anyio
async def test_documents_api_oversized_upload_returns_413(
    pgvector_session,
    knowledge_service_override,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = await _make_user(pgvector_session)
    headers = _auth_headers(user_id)
    monkeypatch.setenv("DOCUMENT_UPLOAD_MAX_BYTES", "32")
    get_settings.cache_clear()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post(
            "/api/documents/upload",
            files={"file": ("large.txt", b"x" * 64, "text/plain")},
            headers=headers,
        )

    get_settings.cache_clear()
    assert response.status_code == 413
    body = response.json()
    assert body["error"]["code"] == "document_too_large"
    assert "32" in body["error"]["message"]
    assert body["error"]["request_id"] is not None


@pytest.mark.anyio
async def test_documents_api_unsupported_file_type_returns_validation_error(
    pgvector_session,
    knowledge_service_override,
) -> None:
    user_id = await _make_user(pgvector_session)
    headers = _auth_headers(user_id)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post(
            "/api/documents/upload",
            files={"file": ("page.html", b"<html></html>", "text/html")},
            headers=headers,
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.anyio
async def test_chat_route_still_enforces_16kb_body_limit() -> None:
    body_limit = get_settings().request_body_limit_bytes
    oversized_body = b"x" * (body_limit + 1)
    messages: list[Message] = [
        {"type": "http.request", "body": oversized_body, "more_body": False}
    ]

    async def receive() -> Message:
        if messages:
            return messages.pop(0)
        return {"type": "http.disconnect"}

    scope: Scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/chat",
        "raw_path": b"/api/chat",
        "query_string": b"",
        "headers": [(b"content-type", b"application/json")],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }
    request = Request(scope, receive)

    async def call_next(limited_request: Request) -> Response:
        await limited_request.body()
        return Response(status_code=204)

    response = await enforce_request_size(request, call_next)

    assert response.status_code == 413
    body = json.loads(bytes(response.body))
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["message"] == get_settings().request_body_limit_message()


@pytest.mark.anyio
async def test_document_upload_route_uses_upload_limit_not_chat_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat_limit = get_settings().request_body_limit_bytes
    upload_limit = chat_limit + 1024
    monkeypatch.setenv("DOCUMENT_UPLOAD_MAX_BYTES", str(upload_limit))
    get_settings.cache_clear()

    body = b"x" * (chat_limit + 512)
    messages: list[Message] = [
        {"type": "http.request", "body": body, "more_body": False}
    ]

    async def receive() -> Message:
        if messages:
            return messages.pop(0)
        return {"type": "http.disconnect"}

    scope: Scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": DOCUMENT_UPLOAD_PATH,
        "raw_path": DOCUMENT_UPLOAD_PATH.encode(),
        "query_string": b"",
        "headers": [(b"content-type", b"multipart/form-data")],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }
    request = Request(scope, receive)

    async def call_next(_: Request) -> Response:
        return Response(status_code=204)

    response = await enforce_request_size(request, call_next)

    get_settings.cache_clear()
    assert response.status_code == 204


@pytest.mark.anyio
async def test_upload_quota_allows_uploads_under_limit(
    pgvector_session,
    knowledge_service_override,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTHENTICATED_DAILY_UPLOAD_QUOTA", "2")
    get_settings.cache_clear()
    settings = Settings(openai_api_key="test-key", authenticated_daily_upload_quota=2)

    user_id = await _make_user(pgvector_session)
    headers = _auth_headers(user_id)
    file_bytes = (FIXTURES / "sample.txt").read_bytes()

    def _override() -> KnowledgeService:
        return _knowledge_service(pgvector_session, settings=settings)

    app.dependency_overrides[get_knowledge_service] = _override

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        first = await client.post(
            "/api/documents/upload",
            files={"file": ("sample.txt", file_bytes, "text/plain")},
            headers=headers,
        )
        assert first.status_code == 200

    get_settings.cache_clear()


@pytest.mark.anyio
async def test_upload_quota_denies_after_limit(
    pgvector_session,
    knowledge_service_override,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTHENTICATED_DAILY_UPLOAD_QUOTA", "1")
    get_settings.cache_clear()
    settings = Settings(openai_api_key="test-key", authenticated_daily_upload_quota=1)

    user_id = await _make_user(pgvector_session)
    headers = _auth_headers(user_id)
    file_bytes = (FIXTURES / "sample.txt").read_bytes()
    shared_service = _knowledge_service(pgvector_session, settings=settings)

    def _override() -> KnowledgeService:
        return shared_service

    app.dependency_overrides[get_knowledge_service] = _override

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        first = await client.post(
            "/api/documents/upload",
            files={"file": ("sample.txt", file_bytes, "text/plain")},
            headers=headers,
        )
        assert first.status_code == 200

        second = await client.post(
            "/api/documents/upload",
            files={"file": ("sample.txt", file_bytes, "text/plain")},
            headers=headers,
        )
        assert second.status_code == 429
        assert second.json()["error"]["code"] == "quota_exceeded"

    get_settings.cache_clear()
