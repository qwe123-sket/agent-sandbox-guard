#!/usr/bin/env python3
"""使用 DeepSeek（OpenAI 兼容）驱动 Agent，工具执行仍经 PermissionGuard。"""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from langchain_core.messages import HumanMessage, SystemMessage

from agent_guard.agent.llm import create_chat_model, load_llm_settings
from agent_guard.agent.llm_graph import SYSTEM_PROMPT, build_llm_agent_graph
from agent_guard.config import load_config, load_policies
from agent_guard.guard import PermissionGuard
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


def print_trace(messages) -> None:
    print("\n=== 对话与工具 trace ===")
    for msg in messages:
        role = getattr(msg, "type", msg.__class__.__name__)
        if isinstance(msg, HumanMessage):
            print(f"[user] {msg.content}")
        elif isinstance(msg, SystemMessage):
            continue
        elif hasattr(msg, "tool_calls") and msg.tool_calls:
            for call in msg.tool_calls:
                print(f"[llm -> tool] {call['name']}({call['args']})")
            if msg.content:
                print(f"[assistant] {msg.content}")
        elif hasattr(msg, "content"):
            prefix = "tool" if role == "tool" else "assistant"
            print(f"[{prefix}] {msg.content}")


def main() -> None:
    parser = argparse.ArgumentParser(description="LLM Agent（DeepSeek + PermissionGuard）")
    parser.add_argument("--role", default="operator", choices=["readonly", "operator", "admin"])
    parser.add_argument("--prompt", default=DEFAULT_PROMPT, help="发给 LLM 的任务描述")
    parser.add_argument("--auto-approve", action="store_true", help="跳过高风险人工确认")
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

    llm = create_chat_model(llm_settings)
    graph = build_llm_agent_graph(guard, llm)

    print(f"模型: {llm_settings.model} @ {llm_settings.base_url}")
    print(f"角色: {args.role}")
    print(f"任务: {args.prompt}\n")

    result = graph.invoke(
        {
            "messages": [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=args.prompt),
            ]
        }
    )

    print_trace(result["messages"])
    print(f"\n审计日志: {config.audit_log_path}")


if __name__ == "__main__":
    main()
