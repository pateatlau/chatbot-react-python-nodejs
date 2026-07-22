"""Resolve effective ``max_tokens`` for provider calls (V1.1.1 demo protection)."""

from __future__ import annotations

from app.core.caller import CallerContext
from app.core.config import Settings
from app.core.logging import get_logger
from app.providers.anthropic_provider import ANTHROPIC_MAX_TOKENS
from app.schemas.chat import ProviderName

logger = get_logger(__name__)

_PROVIDER_DEFAULT_MAX_TOKENS: dict[ProviderName, int] = {
    "anthropic": ANTHROPIC_MAX_TOKENS,
}


def provider_default_max_tokens(provider_name: ProviderName | None) -> int | None:
    if provider_name is None:
        return None
    return _PROVIDER_DEFAULT_MAX_TOKENS.get(provider_name)


def resolve_max_tokens(
    caller: CallerContext | None,
    settings: Settings,
    *,
    request_max_tokens: int | None = None,
    provider_name: ProviderName | None = None,
) -> int | None:
    """Return ``max_tokens`` for a provider call.

    Guests receive ``min(request/default/provider_default, guest cap)``. Authenticated
    callers are not subject to the guest output token cap.
    """
    provider_default = provider_default_max_tokens(provider_name)
    base = request_max_tokens or settings.default_max_tokens or provider_default

    if caller is None or caller.kind != "guest":
        return base

    cap = settings.effective_guest_max_output_tokens
    if base is None:
        effective = cap
        logger.info(
            "Guest output token cap applied",
            guest_output_token_cap_applied=True,
            capped_max_tokens=effective,
        )
        return effective

    effective = min(base, cap)
    if effective < base:
        logger.info(
            "Guest output token cap applied",
            guest_output_token_cap_applied=True,
            capped_max_tokens=effective,
        )
    return effective
