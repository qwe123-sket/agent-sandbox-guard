from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from agent_guard.guard import PermissionGuard
from agent_guard.harness.types import HarnessConfig, TraceEvent
from agent_guard.security import PolicyViolation


@dataclass
class ToolCallRequest:
    name: str
    arguments: dict[str, Any]


class MockPlanner:
    """无 LLM 时的确定性规划器，便于复现攻击用例。"""

    def __init__(self, planned_calls: list[ToolCallRequest] | None = None):
        self.planned_calls = planned_calls or []
        self._index = 0

    def next_call(self) -> ToolCallRequest | None:
        if self._index >= len(self.planned_calls):
            return None
        call = self.planned_calls[self._index]
        self._index += 1
        return call


def run_mock_harness(
    guard: PermissionGuard,
    planner: MockPlanner,
    config: HarnessConfig | None = None,
) -> dict[str, Any]:
    """
    Mock Harness loop：plan → Gate → Sandbox，不经过 LLM / LangGraph。
    返回结构含 trace，供攻击回归使用。
    """
    config = config or HarnessConfig()
    started = perf_counter()
    events: list[TraceEvent] = []
    last_result: Any = None
    stop_reason = "completed"
    tool_calls = 0

    while True:
        if perf_counter() - started >= config.run_timeout_s:
            stop_reason = "run_timeout"
            break
        if tool_calls >= config.max_tool_calls:
            stop_reason = "tool_budget_exhausted"
            break

        call = planner.next_call()
        if call is None:
            break
        tool_calls += 1

        events.append(
            TraceEvent(
                role="planner",
                content=f"准备调用 {call.name}",
                name=call.name,
                status="proposed",
                turn=tool_calls,
            )
        )

        tool_started = perf_counter()
        try:
            result = guard.execute(call.name, call.arguments)
            content = f"{call.name} 成功: {result}"
            decision = "success"
            last_result = result
        except PolicyViolation as exc:
            result = str(exc)
            content = f"{call.name} 被拦截: {result}"
            decision = "blocked"
            last_result = result
        except Exception as exc:
            result = str(exc)
            content = f"{call.name} 执行失败: {result}"
            decision = "error"
            last_result = result

        events.append(
            TraceEvent(
                role="tool",
                content=content,
                name=call.name,
                status=decision,
                turn=tool_calls,
                duration_ms=(perf_counter() - tool_started) * 1000,
            )
        )
        if decision == "blocked" and config.stop_on_block:
            stop_reason = "blocked_by_policy"
            break

    trace = [asdict(event) for event in events]
    return {
        "trace": trace,
        "last_result": last_result,
        "events": events,
        "stop_reason": stop_reason,
        "tool_calls": tool_calls,
        "duration_ms": round((perf_counter() - started) * 1000, 3),
    }
