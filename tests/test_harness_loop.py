from pathlib import Path

from agent_guard.config import AppConfig, load_config, load_policies
from agent_guard.guard import PermissionGuard
from agent_guard.harness import AgentHarness, HarnessConfig
from agent_guard.harness.types import AssistantTurn, ToolCall
from agent_guard.security import HITLController


class FakeLLM:
    def __init__(self, turns):
        self.turns = iter(turns)

    def complete(self, messages, tools=None):
        turn = next(self.turns)
        if isinstance(turn, Exception):
            raise turn
        return turn


def make_guard(tmp_path: Path, role: str = "readonly") -> PermissionGuard:
    base = load_config()
    config = AppConfig(
        project_root=tmp_path,
        sandbox_root=tmp_path / "sandbox",
        workspace_dir=tmp_path / "sandbox" / "workspace",
        data_dir=tmp_path / "sandbox" / "data",
        policies_path=base.policies_path,
        audit_log_path=tmp_path / "logs" / "audit.jsonl",
    )
    return PermissionGuard(
        config=config,
        policies=load_policies(base.policies_path),
        role=role,
        session_id="harness-test",
        hitl=HITLController(auto_approve=True),
    )


def test_loop_executes_tool_and_returns_final_text(tmp_path):
    llm = FakeLLM(
        [
            AssistantTurn(
                content=None,
                tool_calls=[ToolCall("call-1", "list_files", {"directory": "."})],
            ),
            AssistantTurn(content="任务完成"),
        ]
    )
    result = AgentHarness(make_guard(tmp_path), llm).run("列出文件")

    assert result.stop_reason == "completed"
    assert result.tool_calls == 1
    assert result.final_text == "任务完成"
    assert any(event.status == "success" for event in result.trace)


def test_tool_call_budget_stops_loop(tmp_path):
    llm = FakeLLM(
        [
            AssistantTurn(
                content=None,
                tool_calls=[
                    ToolCall("call-1", "list_files", {"directory": "."}),
                    ToolCall("call-2", "list_files", {"directory": "."}),
                ],
            )
        ]
    )
    harness = AgentHarness(
        make_guard(tmp_path),
        llm,
        config=HarnessConfig(max_tool_calls=1),
    )
    result = harness.run("重复列出文件")

    assert result.stop_reason == "tool_budget_exhausted"
    assert result.tool_calls == 1


def test_policy_block_can_stop_loop(tmp_path):
    llm = FakeLLM(
        [
            AssistantTurn(
                content=None,
                tool_calls=[ToolCall("call-1", "delete_file", {"path": "x.txt"})],
            )
        ]
    )
    harness = AgentHarness(
        make_guard(tmp_path),
        llm,
        config=HarnessConfig(stop_on_block=True),
    )
    result = harness.run("删除文件")

    assert result.stop_reason == "blocked_by_policy"
    assert any(event.status == "blocked" for event in result.trace)


def test_consecutive_model_errors_stop_loop(tmp_path):
    llm = FakeLLM([RuntimeError("network"), RuntimeError("network")])
    harness = AgentHarness(
        make_guard(tmp_path),
        llm,
        config=HarnessConfig(max_consecutive_errors=2),
    )
    result = harness.run("执行任务")

    assert result.stop_reason == "consecutive_errors"
    assert sum(event.status == "error" for event in result.trace) == 2
