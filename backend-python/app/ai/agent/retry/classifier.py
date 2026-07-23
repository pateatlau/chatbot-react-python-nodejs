"""Agent-specific retry classification (Part I retry table)."""

from __future__ import annotations

from pydantic import ValidationError

from app.ai.agent.exceptions import (
    AgentError,
    AgentIterationLimitError,
    AgentTimeoutError,
)
from app.ai.tools.schemas import ToolResult
from app.core.retry import is_retryable_exception

# ToolExecutor / handler error codes eligible for agent tool retry (Part I table).
_RETRYABLE_TOOL_ERROR_CODES = frozenset(
    {"timeout", "rate_limit", "service_unavailable"}
)


def is_non_retryable_agent_error(exc: BaseException) -> bool:
    """Return True when the failure must not be retried in the agent runtime."""
    if isinstance(exc, (AgentIterationLimitError, AgentTimeoutError)):
        return True
    if isinstance(exc, AgentError):
        return True
    if isinstance(exc, ValidationError):
        return True
    if isinstance(exc, (PermissionError, LookupError, FileNotFoundError)):
        return True
    return False


def is_retryable_agent_error(exc: BaseException) -> bool:
    """Return True for transient failures (timeout, connection, 429, etc.)."""
    if is_non_retryable_agent_error(exc):
        return False
    return is_retryable_exception(exc)


def is_retryable_tool_result(result: ToolResult) -> bool:
    """Return True when a normalized tool failure should be retried."""
    if result.success:
        return False
    if result.error_code in _RETRYABLE_TOOL_ERROR_CODES:
        return True
    return False
