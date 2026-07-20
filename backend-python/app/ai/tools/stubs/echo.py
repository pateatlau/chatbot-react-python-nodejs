"""Stub echo tool handler for unit tests (not registered at application startup)."""

from __future__ import annotations

import asyncio

from app.ai.interfaces.tool_handler import ToolHandler
from app.ai.tools.schemas import (
    ToolDefinition,
    ToolExecutionContext,
    ToolResult,
)

ECHO_TOOL_NAME = "echo"

ECHO_TOOL_DEFINITION = ToolDefinition(
    name=ECHO_TOOL_NAME,
    description="Echo a message back to the caller",
    parameters={
        "type": "object",
        "properties": {
            "message": {"type": "string"},
        },
        "required": ["message"],
    },
)


class EchoToolHandler:
    """Return ``{"echo": message}`` for lifecycle tests."""

    async def execute(
        self,
        args: dict[str, object],
        context: ToolExecutionContext,
    ) -> ToolResult:
        del context
        message = args["message"]
        return ToolResult(success=True, data={"echo": message})


class SlowEchoToolHandler:
    """Sleep longer than the configured timeout to exercise timeout handling."""

    def __init__(self, *, sleep_seconds: float) -> None:
        self._sleep_seconds = sleep_seconds

    async def execute(
        self,
        args: dict[str, object],
        context: ToolExecutionContext,
    ) -> ToolResult:
        del args, context
        await asyncio.sleep(self._sleep_seconds)
        return ToolResult(success=True, data={"echo": "slow"})


def echo_handler() -> ToolHandler:
    return EchoToolHandler()
