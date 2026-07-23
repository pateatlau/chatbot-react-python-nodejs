"""CORS helpers and request-origin context.

Starlette's ``BaseHTTPMiddleware`` (used by several HTTP middlewares here) can
return error responses that bypass ``CORSMiddleware``'s ASGI ``send`` wrapper.
We capture the request ``Origin`` early and re-apply allowed CORS headers on
centralized ``error_response`` payloads so browsers still see a valid CORS
response when the API returns 4xx/5xx envelopes.
"""

from __future__ import annotations

import re
from contextvars import ContextVar, Token
from typing import TypeVar

from starlette.responses import Response

from app.core.config import get_settings

_request_origin: ContextVar[str | None] = ContextVar("request_origin", default=None)

ResponseT = TypeVar("ResponseT", bound=Response)

REQUEST_ID_HEADER = "X-Request-ID"

CORS_EXPOSE_HEADER_NAMES = (
    "X-Guest-Token",
    "X-Guest-Quota-Remaining",
    REQUEST_ID_HEADER,
)

# Matches local Vite (any port) and preview servers during development.
DEV_ORIGIN_REGEX = re.compile(r"https?://(localhost|127\.0\.0\.1)(:\d+)?$")


def bind_request_origin(origin: str | None) -> Token[str | None]:
    return _request_origin.set(origin.strip() if origin else None)


def reset_request_origin(token: Token[str | None]) -> None:
    _request_origin.reset(token)


def get_request_origin() -> str | None:
    return _request_origin.get()


def is_origin_allowed(origin: str) -> bool:
    settings = get_settings()
    if origin in settings.cors_allowed_origins_list:
        return True
    if settings.is_development and DEV_ORIGIN_REGEX.fullmatch(origin):
        return True
    return False


def apply_cors_headers(response: ResponseT) -> ResponseT:
    """Attach CORS headers when the stored request origin is allowed."""
    origin = get_request_origin()
    if origin is None or not is_origin_allowed(origin):
        return response

    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Expose-Headers"] = ", ".join(
        CORS_EXPOSE_HEADER_NAMES
    )
    response.headers["Vary"] = "Origin"
    return response
