from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from agent_guard.guard import PermissionGuard
from agent_guard.security import PolicyViolation


class AgentState(TypedDict):
    trace: list[dict[str, Any]]
    pending_tool: dict[str, Any] | None
    last_result: Any
    call_index: int


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


def build_agent_graph(guard: PermissionGuard, planner: MockPlanner):
    def plan_node(state: AgentState) -> AgentState:
        call = planner.next_call()
        if call is None:
            return {"pending_tool": None}
        trace = list(state.get("trace", []))
        trace.append({"role": "planner", "content": f"准备调用 {call.name}"})
        return {
            "pending_tool": {"name": call.name, "arguments": call.arguments},
            "trace": trace,
        }

    def execute_node(state: AgentState) -> AgentState:
        pending = state.get("pending_tool")
        if not pending:
            return {"last_result": None}

        try:
            result = guard.execute(pending["name"], pending["arguments"])
            content = f"{pending['name']} 成功: {result}"
            decision = "success"
        except PolicyViolation as exc:
            result = str(exc)
            content = f"{pending['name']} 被拦截: {result}"
            decision = "blocked"
        except Exception as exc:
            result = str(exc)
            content = f"{pending['name']} 执行失败: {result}"
            decision = "error"

        trace = list(state.get("trace", []))
        trace.append(
            {
                "role": "tool",
                "content": content,
                "name": pending["name"],
                "status": decision,
            }
        )
        return {"last_result": result, "trace": trace}

    def should_continue(state: AgentState) -> str:
        if state.get("pending_tool") is None:
            return "end"
        return "execute"

    graph = StateGraph(AgentState)
    graph.add_node("plan", plan_node)
    graph.add_node("execute", execute_node)
    graph.set_entry_point("plan")
    graph.add_conditional_edges("plan", should_continue, {"execute": "execute", "end": END})
    graph.add_edge("execute", "plan")
    return graph.compile()
