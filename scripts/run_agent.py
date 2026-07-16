#!/usr/bin/env python3
"""Mock Harness：固定工具序列，演示 HITL 与审计日志。"""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_guard.config import load_config, load_policies
from agent_guard.guard import PermissionGuard
from agent_guard.harness import MockPlanner, ToolCallRequest, run_mock_harness
from agent_guard.security import HITLController, PendingApproval


def cli_approver(pending: PendingApproval) -> bool:
    print("\n[HITL] 待确认操作")
    print(f"  工具: {pending.tool_name}")
    print(f"  参数: {pending.arguments}")
    print(f"  说明: {pending.description}")
    answer = input("是否允许执行? [y/N]: ").strip().lower()
    return answer in {"y", "yes"}


def main() -> None:
    parser = argparse.ArgumentParser(description="运行 Mock Agent Harness")
    parser.add_argument("--role", default="operator", choices=["readonly", "operator", "admin"])
    parser.add_argument("--auto-approve", action="store_true", help="跳过高风险人工确认")
    args = parser.parse_args()

    config = load_config()
    policies = load_policies(config.policies_path)
    hitl = HITLController(auto_approve=args.auto_approve)
    if not args.auto_approve:
        hitl.set_approver(cli_approver)

    guard = PermissionGuard(
        config=config,
        policies=policies,
        role=args.role,
        session_id=str(uuid.uuid4())[:8],
        hitl=hitl,
    )

    planner = MockPlanner(
        [
            ToolCallRequest("list_files", {"directory": "."}),
            ToolCallRequest("write_file", {"path": "demo.txt", "content": "hello sandbox"}),
            ToolCallRequest("read_file", {"path": "demo.txt"}),
            ToolCallRequest("delete_file", {"path": "demo.txt"}),
        ]
    )

    result = run_mock_harness(guard, planner)

    print("\n=== 执行记录 ===")
    for msg in result["trace"]:
        print(f"[{msg.get('role', 'unknown')}] {msg.get('content')}")

    print(f"\n审计日志: {config.audit_log_path}")


if __name__ == "__main__":
    main()
