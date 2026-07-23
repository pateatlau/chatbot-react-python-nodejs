"""Tests for agent multi-tool execution (Phase 7)."""

from __future__ import annotations

import ast
import asyncio
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import ClassVar
from unittest.mock import AsyncMock

import pytest

from app.ai.agent import StepAction
from app.ai.agent.exceptions import AgentError
from app.ai.agent.executor import (
    ToolRunner,
    aggregate_tool_results,
    resolve_step_batches,
)
from app.ai.agent.executor.result_aggregator import ToolRunRecord
from app.ai.agent.models.events import AgentStreamEventType
from app.ai.agent.models.plan import PlannedStep
from app.ai.agent.retry import ToolRetryPolicy
from app.ai.agent.streaming import InMemoryStreamPublisher
from app.ai.tools.executor import ToolExecutor
from app.ai.tools.registry import ToolRegistry
from app.ai.tools.schemas import (
    ToolCall,
    ToolDefinition,
    ToolExecutionContext,
    ToolResult,
)
from app.ai.tools.stubs.echo import ECHO_TOOL_DEFINITION, echo_handler
from app.core.caller import CallerContext
from app.core.config import Settings


@pytest.fixture(autouse=True)
def _reset_tracking_handlers() -> Iterator[None]:
    yield
    TrackingEchoHandler.call_order.clear()
    FlakyTimeoutHandler.calls = 0


@pytest.fixture
def registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(ECHO_TOOL_DEFINITION, echo_handler())
    return reg


@pytest.fixture
def executor(registry: ToolRegistry) -> ToolExecutor:
    return ToolExecutor(registry=registry, settings=Settings(request_timeout_seconds=5))


@pytest.fixture
def tool_context() -> ToolExecutionContext:
    return ToolExecutionContext(
        caller=CallerContext.for_user(uuid.uuid4()),
        request_id="req-tool-runner",
    )


class TrackingEchoHandler:
    """Record tool invocation order for sequencing assertions."""

    call_order: ClassVar[list[str]] = []

    async def execute(
        self,
        args: dict[str, object],
        context: ToolExecutionContext,
    ) -> ToolResult:
        del context
        message = str(args["message"])
        TrackingEchoHandler.call_order.append(message)
        await asyncio.sleep(0.05)
        return ToolResult(success=True, data={"echo": message})


class FlakyTimeoutHandler:
    """Return a retryable timeout once, then succeed."""

    calls: ClassVar[int] = 0

    async def execute(
        self,
        args: dict[str, object],
        context: ToolExecutionContext,
    ) -> ToolResult:
        del context
        FlakyTimeoutHandler.calls += 1
        if FlakyTimeoutHandler.calls == 1:
            return ToolResult(
                success=False,
                error="Tool execution timed out",
                error_code="timeout",
            )
        return ToolResult(success=True, data={"echo": args["message"]})


def _tool_step(
    *,
    step_id: str,
    message: str,
    call_id: str | None = None,
    depends_on: list[str] | None = None,
) -> PlannedStep:
    return PlannedStep(
        step_id=step_id,
        action=StepAction.TOOL_CALL,
        tool_calls=[
            ToolCall(name="echo", arguments={"message": message}, call_id=call_id)
        ],
        depends_on=depends_on or [],
    )


def test_resolve_step_batches_independent_steps_share_one_batch() -> None:
    steps = [
        _tool_step(step_id="step-a", message="alpha"),
        _tool_step(step_id="step-b", message="beta"),
    ]

    batches = resolve_step_batches(steps)

    assert len(batches) == 1
    assert {step.step_id for step in batches[0]} == {"step-a", "step-b"}


def test_resolve_step_batches_dependency_chain() -> None:
    steps = [
        _tool_step(step_id="step-1", message="first"),
        _tool_step(step_id="step-2", message="second", depends_on=["step-1"]),
    ]

    batches = resolve_step_batches(steps)

    assert len(batches) == 2
    assert batches[0][0].step_id == "step-1"
    assert batches[1][0].step_id == "step-2"


def test_resolve_step_batches_ignores_non_tool_steps() -> None:
    steps = [
        PlannedStep(step_id="finalize", action=StepAction.FINALIZE),
        _tool_step(step_id="step-1", message="only-tool"),
    ]

    batches = resolve_step_batches(steps)

    assert len(batches) == 1
    assert batches[0][0].step_id == "step-1"


def test_resolve_step_batches_rejects_unknown_dependency() -> None:
    step = _tool_step(step_id="step-1", message="x", depends_on=["missing"])

    with pytest.raises(AgentError, match="unknown step"):
        resolve_step_batches([step])


def test_resolve_step_batches_rejects_circular_dependencies() -> None:
    steps = [
        _tool_step(step_id="step-a", message="a", depends_on=["step-b"]),
        _tool_step(step_id="step-b", message="b", depends_on=["step-a"]),
    ]

    with pytest.raises(AgentError, match="Circular dependency"):
        resolve_step_batches(steps)


def test_aggregate_tool_results_tools_used_and_success_flags() -> None:
    records = [
        ToolRunRecord(
            step_id="s1",
            call=ToolCall(name="echo", arguments={"message": "a"}),
            result=ToolResult(success=True, data={"echo": "a"}),
        ),
        ToolRunRecord(
            step_id="s1",
            call=ToolCall(name="echo", arguments={"message": "b"}),
            result=ToolResult(success=False, error="fail", error_code="handler_error"),
        ),
        ToolRunRecord(
            step_id="s2",
            call=ToolCall(name="search", arguments={"q": "x"}),
            result=ToolResult(success=True, data={"hits": []}),
        ),
    ]

    aggregated = aggregate_tool_results(records)

    assert aggregated.tools_used == ["echo", "search"]
    assert aggregated.all_succeeded is False
    assert aggregated.any_succeeded is True
    assert len(aggregated.results_for_step("s1")) == 2


@pytest.mark.anyio
async def test_tool_runner_single_tool_success(
    executor: ToolExecutor,
    tool_context: ToolExecutionContext,
) -> None:
    publisher = InMemoryStreamPublisher()
    runner = ToolRunner(tool_executor=executor, stream_publisher=publisher)
    steps = [_tool_step(step_id="step-1", message="hello", call_id="call-1")]

    result = await runner.run_tool_steps(
        steps,
        execution_id="exec-single",
        tool_context=tool_context,
    )

    assert result.all_succeeded is True
    assert result.tools_used == ["echo"]
    assert result.records[0].result.data == {"echo": "hello"}
    assert len(publisher.events) == 2
    assert publisher.events[0].type == AgentStreamEventType.TOOL_START
    assert publisher.events[1].type == AgentStreamEventType.TOOL_END


@pytest.mark.anyio
async def test_tool_runner_parallel_tools_within_step(
    tool_context: ToolExecutionContext,
) -> None:
    registry = ToolRegistry()
    registry.register(ECHO_TOOL_DEFINITION, TrackingEchoHandler())
    executor = ToolExecutor(
        registry=registry, settings=Settings(request_timeout_seconds=5)
    )
    runner = ToolRunner(
        tool_executor=executor,
        parallel_tools_enabled=True,
    )
    step = PlannedStep(
        step_id="parallel-step",
        action=StepAction.TOOL_CALL,
        tool_calls=[
            ToolCall(name="echo", arguments={"message": "alpha"}, call_id="call-a"),
            ToolCall(name="echo", arguments={"message": "beta"}, call_id="call-b"),
        ],
    )

    result = await runner.run_tool_steps(
        [step],
        execution_id="exec-parallel",
        tool_context=tool_context,
    )

    assert result.all_succeeded is True
    assert len(result.records) == 2
    assert {record.call.arguments["message"] for record in result.records} == {
        "alpha",
        "beta",
    }


@pytest.mark.anyio
async def test_tool_runner_sequential_when_parallel_disabled(
    tool_context: ToolExecutionContext,
) -> None:
    registry = ToolRegistry()
    registry.register(ECHO_TOOL_DEFINITION, TrackingEchoHandler())
    executor = ToolExecutor(
        registry=registry, settings=Settings(request_timeout_seconds=5)
    )
    runner = ToolRunner(tool_executor=executor, parallel_tools_enabled=False)
    step = PlannedStep(
        step_id="sequential-step",
        action=StepAction.TOOL_CALL,
        tool_calls=[
            ToolCall(name="echo", arguments={"message": "first"}, call_id="call-1"),
            ToolCall(name="echo", arguments={"message": "second"}, call_id="call-2"),
        ],
    )

    await runner.run_tool_steps(
        [step],
        execution_id="exec-sequential",
        tool_context=tool_context,
    )

    assert TrackingEchoHandler.call_order == ["first", "second"]


@pytest.mark.anyio
async def test_tool_runner_dependency_chain_runs_in_order(
    tool_context: ToolExecutionContext,
) -> None:
    registry = ToolRegistry()
    registry.register(ECHO_TOOL_DEFINITION, TrackingEchoHandler())
    executor = ToolExecutor(
        registry=registry, settings=Settings(request_timeout_seconds=5)
    )
    runner = ToolRunner(tool_executor=executor, parallel_tools_enabled=True)
    steps = [
        _tool_step(step_id="step-1", message="first"),
        _tool_step(step_id="step-2", message="second", depends_on=["step-1"]),
    ]

    await runner.run_tool_steps(
        steps,
        execution_id="exec-chain",
        tool_context=tool_context,
    )

    assert TrackingEchoHandler.call_order == ["first", "second"]


@pytest.mark.anyio
async def test_tool_runner_retries_transient_tool_failure(
    tool_context: ToolExecutionContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="echo",
            description="Flaky echo",
            parameters=ECHO_TOOL_DEFINITION.parameters,
        ),
        FlakyTimeoutHandler(),
    )
    executor = ToolExecutor(
        registry=registry, settings=Settings(request_timeout_seconds=5)
    )
    runner = ToolRunner(
        tool_executor=executor,
        retry_policy=ToolRetryPolicy(max_retries=3),
    )
    monkeypatch.setattr("app.core.retry.asyncio.sleep", AsyncMock())

    result = await runner.run_tool_steps(
        [_tool_step(step_id="retry-step", message="recover")],
        execution_id="exec-retry",
        tool_context=tool_context,
    )

    assert FlakyTimeoutHandler.calls == 2
    assert result.all_succeeded is True
    assert result.records[0].result.data == {"echo": "recover"}


@pytest.mark.anyio
async def test_tool_runner_generates_call_id_when_missing(
    executor: ToolExecutor,
    tool_context: ToolExecutionContext,
) -> None:
    publisher = InMemoryStreamPublisher()
    runner = ToolRunner(tool_executor=executor, stream_publisher=publisher)
    step = _tool_step(step_id="generated-id", message="hello")

    result = await runner.run_tool_steps(
        [step],
        execution_id="exec-generated",
        tool_context=tool_context,
    )

    assert result.records[0].call.call_id is not None
    assert result.records[0].call.call_id.startswith("generated-id-")


def test_executor_modules_have_no_transport_or_domain_imports() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    module_paths = [
        repo_root / "app/ai/agent/executor/dependency_resolver.py",
        repo_root / "app/ai/agent/executor/result_aggregator.py",
        repo_root / "app/ai/agent/executor/tool_runner.py",
    ]
    forbidden_roots = ("app.services", "app.db", "app.schemas.chat", "fastapi")

    for module_path in module_paths:
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        imported_modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        }
        imported_modules.update(
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )
        for forbidden in forbidden_roots:
            assert not any(
                module == forbidden or module.startswith(f"{forbidden}.")
                for module in imported_modules
            ), f"{module_path.name} must not import {forbidden}"
