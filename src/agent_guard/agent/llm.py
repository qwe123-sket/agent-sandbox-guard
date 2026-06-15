from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, create_model

from agent_guard.guard import PermissionGuard
from agent_guard.security import PolicyViolation


@dataclass(frozen=True)
class LLMSettings:
    api_key: str
    base_url: str
    model: str
    temperature: float = 0.0


def load_llm_settings(project_root=None) -> LLMSettings:
    from dotenv import load_dotenv

    from agent_guard.config import load_config

    config = load_config(project_root)
    load_dotenv(config.project_root / ".env")

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "未找到 OPENAI_API_KEY。请复制 .env.example 为 .env 并填入 DeepSeek 密钥。"
        )

    return LLMSettings(
        api_key=api_key,
        base_url=os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com").strip(),
        model=os.getenv("OPENAI_MODEL", "deepseek-chat").strip(),
        temperature=float(os.getenv("OPENAI_TEMPERATURE", "0")),
    )


def create_chat_model(settings: LLMSettings):
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=settings.model,
        api_key=settings.api_key,
        base_url=settings.base_url,
        temperature=settings.temperature,
    )


def _args_schema(name: str, fields: dict[str, tuple[type, Any, bool]]) -> type[BaseModel]:
    model_fields = {}
    for field_name, (field_type, default, required) in fields.items():
        if required:
            model_fields[field_name] = (field_type, Field(...))
        else:
            model_fields[field_name] = (field_type, Field(default=default))
    return create_model(f"{name}_args", **model_fields)


def build_guarded_tools(guard: PermissionGuard) -> list[StructuredTool]:
    """仅暴露当前角色白名单内的工具，执行仍走 PermissionGuard。"""

    def _run(tool_name: str, arguments: dict[str, Any]) -> str:
        try:
            result = guard.execute(tool_name, arguments)
            return str(result)
        except PolicyViolation as exc:
            return f"[权限网关拦截] {exc}"
        except Exception as exc:
            return f"[执行失败] {exc}"

    specs: list[tuple[str, str, dict[str, tuple[type, Any, bool]]]] = [
        (
            "read_file",
            "读取 sandbox/workspace 内的文件。path 为相对路径。",
            {"path": (str, "", True)},
        ),
        (
            "write_file",
            "向 sandbox/workspace 写入文件。",
            {"path": (str, "", True), "content": (str, "", True)},
        ),
        (
            "delete_file",
            "删除 sandbox/workspace 内的文件。高风险操作。",
            {"path": (str, "", True)},
        ),
        (
            "list_files",
            "列出 sandbox/workspace 下某目录的文件。",
            {"directory": (str, ".", False)},
        ),
        (
            "db_query",
            "对沙箱 SQLite 执行只读 SELECT 查询。",
            {"sql": (str, "", True)},
        ),
        (
            "db_write",
            "对沙箱 SQLite 执行 INSERT/UPDATE。高风险操作。",
            {"sql": (str, "", True)},
        ),
        (
            "http_get",
            "对外发起 HTTP GET 请求。",
            {"url": (str, "", True)},
        ),
        (
            "http_post",
            "对外发起 HTTP POST 请求。高风险操作。",
            {"url": (str, "", True), "json_body": (dict, None, False)},
        ),
    ]

    tools: list[StructuredTool] = []
    for name, description, field_spec in specs:
        if name not in guard.whitelist.allowed_tools:
            continue

        def make_func(tool_name: str):
            def _invoke(**kwargs: Any) -> str:
                return _run(tool_name, kwargs)

            return _invoke

        tools.append(
            StructuredTool(
                name=name,
                description=description,
                func=make_func(name),
                args_schema=_args_schema(name, field_spec),
            )
        )
    return tools
