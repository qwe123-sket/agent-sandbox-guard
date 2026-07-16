#!/usr/bin/env python3
"""DeepSeek + Agent Harness：模型规划，PermissionGuard 决定是否执行工具。"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_guard.config import load_config, load_policies
from agent_guard.guard import PermissionGuard
from agent_guard.harness import (
    SYSTEM_PROMPT,
    AgentHarness,
    HarnessConfig,
    create_llm_client,
    load_llm_settings,
)
from agent_guard.security import HITLController, PendingApproval

DEFAULT_PROMPT = (
    "先看看 workspace 里有什么文件，"
    "创建 memo.txt 并写入一句问候语，"
    "读回内容确认写入成功。"
)


def cli_approver(pending: PendingApproval) -> bool:
    print("\n[HITL] 待确认操作")
    print(f"  工具: {pending.tool_name}")
    print(f"  参数: {pending.arguments}")
    print(f"  说明: {pending.description}")
    answer = input("是否允许执行? [y/N]: ").strip().lower()
    return answer in {"y", "yes"}


def print_trace(result) -> None:
    print("\n=== Harness trace ===")
    for ev in result.trace:
        prefix = ev.role
        if ev.status:
            prefix = f"{ev.role}/{ev.status}"
        print(f"[{prefix}] {ev.content}")
    if result.final_text:
        print(f"\n[final] {result.final_text}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent Harness（DeepSeek + PermissionGuard）")
    parser.add_argument("--role", default="operator", choices=["readonly", "operator", "admin"])
    parser.add_argument("--prompt", default=DEFAULT_PROMPT, help="发给 LLM 的任务描述")
    parser.add_argument("--auto-approve", action="store_true", help="跳过高风险人工确认")
    parser.add_argument("--max-turns", type=int, default=12)
    parser.add_argument("--max-tool-calls", type=int, default=24)
    parser.add_argument("--timeout", type=float, default=120.0, help="运行时间预算（秒）")
    parser.add_argument("--stop-on-block", action="store_true")
    parser.add_argument("--trace-output", type=Path, help="将结构化 trace 写入 JSON")
    args = parser.parse_args()

    config = load_config()
    policies = load_policies(config.policies_path)
    llm_settings = load_llm_settings()
    hitl = HITLController(auto_approve=args.auto_approve)
    if not args.auto_approve:
        hitl.set_approver(cli_approver)

    guard = PermissionGuard(
        config=config,
        policies=policies,
        role=args.role,
        session_id=f"llm-{uuid.uuid4().hex[:8]}",
        hitl=hitl,
    )

    llm = create_llm_client(llm_settings)
    harness = AgentHarness(
        guard,
        llm,
        system_prompt=SYSTEM_PROMPT,
        config=HarnessConfig(
            max_turns=args.max_turns,
            max_tool_calls=args.max_tool_calls,
            run_timeout_s=args.timeout,
            stop_on_block=args.stop_on_block,
        ),
    )

    print(f"模型: {llm_settings.model} @ {llm_settings.base_url}")
    print(f"角色: {args.role}")
    print(f"任务: {args.prompt}\n")

    result = harness.run(args.prompt)
    print_trace(result)
    print(
        f"\n停止原因: {result.stop_reason} | "
        f"工具调用: {result.tool_calls} | 耗时: {result.duration_ms:.1f}ms"
    )
    if args.trace_output:
        args.trace_output.parent.mkdir(parents=True, exist_ok=True)
        args.trace_output.write_text(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Trace: {args.trace_output}")
    print(f"\n审计日志: {config.audit_log_path}")


if __name__ == "__main__":
    main()
