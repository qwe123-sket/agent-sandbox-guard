from __future__ import annotations

from dataclasses import asdict, dataclass, field
from time import perf_counter
from typing import Any

from agent_guard.guard import PermissionGuard
from agent_guard.harness.llm import OpenAICompatibleClient
from agent_guard.harness.tools import execute_via_gate, tools_for_role
from agent_guard.harness.types import HarnessConfig, TraceEvent

SYSTEM_PROMPT = """你是一个在 Agent Harness 约束下工作的助手（Gate + Sandbox）。
- 文件操作只能在 sandbox/workspace 内进行，使用相对路径。
- 数据库只能访问沙箱 SQLite，查询用 db_query，写入用 db_write。
- 外部请求用 http_get / http_post。
- 如果工具返回 [权限网关拦截]，向用户说明被安全策略拒绝，不要重复尝试相同越权操作。
- 任务完成后用自然语言总结，不要再调用工具。"""


@dataclass
class HarnessResult:
    messages: list[dict[str, Any]]
    trace: list[TraceEvent] = field(default_factory=list)
    final_text: str = ""
    stop_reason: str = "completed"
    tool_calls: int = 0
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "messages": self.messages,
            "trace": [asdict(event) for event in self.trace],
            "final_text": self.final_text,
            "stop_reason": self.stop_reason,
            "tool_calls": self.tool_calls,
            "duration_ms": round(self.duration_ms, 3),
        }


class AgentHarness:
    """
    最小可用 Harness：
      loop: model → (optional) tool_calls → Gate → Sandbox → 回灌结果
    安全决策不在模型侧，而在 PermissionGuard。
    """

    def __init__(
        self,
        guard: PermissionGuard,
        llm: OpenAICompatibleClient,
        *,
        system_prompt: str = SYSTEM_PROMPT,
        config: HarnessConfig | None = None,
        max_turns: int | None = None,
    ):
        self.guard = guard
        self.llm = llm
        self.system_prompt = system_prompt
        self.config = config or HarnessConfig()
        if max_turns is not None:
            self.config = HarnessConfig(
                max_turns=max_turns,
                max_tool_calls=self.config.max_tool_calls,
                max_consecutive_errors=self.config.max_consecutive_errors,
                run_timeout_s=self.config.run_timeout_s,
                stop_on_block=self.config.stop_on_block,
            )

    def run(self, user_prompt: str) -> HarnessResult:
        started = perf_counter()
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        trace: list[TraceEvent] = [
            TraceEvent(role="user", content=user_prompt),
        ]
        tools = tools_for_role(self.guard)
        final_text = ""
        stop_reason = "completed"
        tool_call_count = 0
        consecutive_errors = 0
        should_stop = False

        for turn_index in range(1, self.config.max_turns + 1):
            if perf_counter() - started >= self.config.run_timeout_s:
                stop_reason = "run_timeout"
                final_text = "达到 Harness 运行时间预算，已停止。"
                break

            llm_started = perf_counter()
            try:
                turn = self.llm.complete(messages, tools=tools or None)
            except Exception as exc:
                consecutive_errors += 1
                trace.append(
                    TraceEvent(
                        role="system",
                        content=f"模型调用失败: {exc}",
                        status="error",
                        turn=turn_index,
                        duration_ms=(perf_counter() - llm_started) * 1000,
                    )
                )
                if consecutive_errors >= self.config.max_consecutive_errors:
                    stop_reason = "consecutive_errors"
                    final_text = "连续模型调用失败，Harness 已停止。"
                    break
                continue

            consecutive_errors = 0
            trace.append(
                TraceEvent(
                    role="llm",
                    content=turn.content or "",
                    status="response",
                    turn=turn_index,
                    duration_ms=(perf_counter() - llm_started) * 1000,
                )
            )

            assistant_msg: dict[str, Any] = {
                "role": "assistant",
                "content": turn.content or "",
            }
            if turn.tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": _dump_args(tc.arguments),
                        },
                    }
                    for tc in turn.tool_calls
                ]
            messages.append(assistant_msg)

            if not turn.tool_calls:
                final_text = turn.content or ""
                if final_text:
                    trace.append(
                        TraceEvent(
                            role="assistant",
                            content=final_text,
                            status="completed",
                            turn=turn_index,
                        )
                    )
                break

            for tc in turn.tool_calls:
                if tool_call_count >= self.config.max_tool_calls:
                    stop_reason = "tool_budget_exhausted"
                    final_text = "达到工具调用预算，Harness 已停止。"
                    should_stop = True
                    break

                tool_call_count += 1
                trace.append(
                    TraceEvent(
                        role="llm",
                        content=f"{tc.name}({tc.arguments})",
                        name=tc.name,
                        status="proposed",
                        turn=turn_index,
                    )
                )
                tool_started = perf_counter()
                result = execute_via_gate(self.guard, tc.name, tc.arguments)
                blocked = result.startswith("[权限网关拦截]")
                trace.append(
                    TraceEvent(
                        role="tool",
                        content=result,
                        name=tc.name,
                        status="blocked" if blocked else "success",
                        turn=turn_index,
                        duration_ms=(perf_counter() - tool_started) * 1000,
                    )
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    }
                )

                if blocked and self.config.stop_on_block:
                    stop_reason = "blocked_by_policy"
                    final_text = "工具调用被安全策略拦截，Harness 已停止。"
                    should_stop = True
                    break

            if should_stop:
                break
        else:
            stop_reason = "max_turns"
            final_text = "达到最大轮次，已停止。"

        return HarnessResult(
            messages=messages,
            trace=trace,
            final_text=final_text,
            stop_reason=stop_reason,
            tool_calls=tool_call_count,
            duration_ms=(perf_counter() - started) * 1000,
        )


def _dump_args(arguments: dict[str, Any]) -> str:
    import json

    return json.dumps(arguments, ensure_ascii=False)
