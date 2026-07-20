"""Authorization policy for tool invocation."""

from __future__ import annotations

from app.ai.tools.schemas import ToolDefinition, ToolExecutionContext


class ToolAuthorizer:
    """V1 policy: authenticated users may invoke tools; guests are denied."""

    def authorize(
        self,
        tool: ToolDefinition,
        context: ToolExecutionContext,
    ) -> str | None:
        del tool
        if context.caller.kind == "user":
            return None
        return "Tool invocation requires an authenticated user"
