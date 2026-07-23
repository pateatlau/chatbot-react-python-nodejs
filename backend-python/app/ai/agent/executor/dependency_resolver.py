"""Resolve planned tool steps into dependency-ordered execution batches (Phase 7)."""

from __future__ import annotations

from collections import deque

from app.ai.agent.exceptions import AgentError
from app.ai.agent.models.plan import PlannedStep, StepAction


def resolve_step_batches(steps: list[PlannedStep]) -> list[list[PlannedStep]]:
    """Group tool-call steps into batches that respect ``depends_on`` ordering.

    Steps within the same batch have no unresolved cross-step dependencies and
    may run concurrently when parallel execution is enabled. Steps in later
    batches depend on at least one step from an earlier batch.
    """
    tool_steps = [step for step in steps if step.action == StepAction.TOOL_CALL]
    if not tool_steps:
        return []

    step_by_id = {step.step_id: step for step in tool_steps}
    if len(step_by_id) != len(tool_steps):
        raise AgentError("Planned tool steps must have unique step_id values")

    for step in tool_steps:
        for dependency_id in step.depends_on:
            if dependency_id not in step_by_id:
                raise AgentError(
                    f"Planned step '{step.step_id}' depends on unknown step "
                    f"'{dependency_id}'"
                )

    # Kahn's algorithm: each batch is one topological level.
    pending_dependencies: dict[str, set[str]] = {
        step.step_id: set(step.depends_on) for step in tool_steps
    }
    dependents: dict[str, set[str]] = {step.step_id: set() for step in tool_steps}
    for step in tool_steps:
        for dependency_id in step.depends_on:
            dependents[dependency_id].add(step.step_id)

    ready = deque(
        sorted(
            step_id
            for step_id, dependencies in pending_dependencies.items()
            if not dependencies
        )
    )
    batches: list[list[PlannedStep]] = []
    visited = 0

    while ready:
        current_ids = list(ready)
        ready.clear()
        batch = [step_by_id[step_id] for step_id in current_ids]
        batches.append(batch)
        visited += len(batch)

        for step_id in current_ids:
            for dependent_id in sorted(dependents[step_id]):
                pending_dependencies[dependent_id].discard(step_id)
                if not pending_dependencies[dependent_id]:
                    ready.append(dependent_id)

    if visited != len(tool_steps):
        raise AgentError("Circular dependency detected among planned tool steps")

    return batches
