from __future__ import annotations

from typing import Any

from agent_guard.guard import PermissionGuard
from agent_guard.security import PolicyViolation

# OpenAI-compatible tool schemas exposed to the model (role-filtered at bind time).
TOOL_SPECS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取 sandbox/workspace 内的文件。path 为相对路径。",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "向 sandbox/workspace 写入文件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": "删除 sandbox/workspace 内的文件。高风险操作。",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "列出 sandbox/workspace 下某目录的文件。",
            "parameters": {
                "type": "object",
                "properties": {"directory": {"type": "string"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "db_query",
            "description": "对沙箱 SQLite 执行只读 SELECT 查询。",
            "parameters": {
                "type": "object",
                "properties": {"sql": {"type": "string"}},
                "required": ["sql"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "db_write",
            "description": "对沙箱 SQLite 执行 INSERT/UPDATE。高风险操作。",
            "parameters": {
                "type": "object",
                "properties": {"sql": {"type": "string"}},
                "required": ["sql"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "http_get",
            "description": "对外发起 HTTP GET 请求。",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "http_post",
            "description": "对外发起 HTTP POST 请求。高风险操作。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "json_body": {"type": "object"},
                },
                "required": ["url"],
            },
        },
    },
]


def tools_for_role(guard: PermissionGuard) -> list[dict[str, Any]]:
    allowed = set(guard.whitelist.allowed_tools)
    return [spec for spec in TOOL_SPECS if spec["function"]["name"] in allowed]


def execute_via_gate(guard: PermissionGuard, name: str, arguments: dict[str, Any]) -> str:
    """唯一执行入口：模型提议 → Gate 决策 → Sandbox 副作用。"""
    try:
        result = guard.execute(name, arguments)
        return str(result)
    except PolicyViolation as exc:
        return f"[权限网关拦截] {exc}"
    except Exception as exc:
        return f"[执行失败] {exc}"
