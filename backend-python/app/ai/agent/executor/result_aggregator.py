"""Aggregate multi-tool execution results (Phase 7)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.ai.tools.schemas import ToolCall, ToolResult


class ToolRunRecord(BaseModel):
    """One tool invocation result bound to its planned step."""

    step_id: str = Field(min_length=1)
    call: ToolCall
    result: ToolResult


class AggregatedToolResults(BaseModel):
    """Combined outcome of running one or more planned tool steps."""

    records: list[ToolRunRecord] = Field(default_factory=list)

    @property
    def tools_used(self) -> list[str]:
        """Unique tool names in execution order."""
        seen: set[str] = set()
        names: list[str] = []
        for record in self.records:
            if record.call.name not in seen:
                seen.add(record.call.name)
                names.append(record.call.name)
        return names

    @property
    def all_succeeded(self) -> bool:
        return all(record.result.success for record in self.records)

    @property
    def any_succeeded(self) -> bool:
        return any(record.result.success for record in self.records)

    def results_for_step(self, step_id: str) -> list[ToolRunRecord]:
        return [record for record in self.records if record.step_id == step_id]


def aggregate_tool_results(records: list[ToolRunRecord]) -> AggregatedToolResults:
    """Build an :class:`AggregatedToolResults` view from ordered run records."""
    return AggregatedToolResults(records=list(records))
