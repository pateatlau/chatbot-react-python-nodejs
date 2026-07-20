"""Tool handler protocol for the generic tool execution platform."""

from __future__ import annotations

from typing import Protocol

from app.ai.tools.schemas import ToolExecutionContext, ToolResult


class ToolHandler(Protocol):
    """Async handler invoked by ``ToolExecutor`` after validation and authorization."""

    async def execute(
        self,
        args: dict[str, object],
        context: ToolExecutionContext,
    ) -> ToolResult: ...
