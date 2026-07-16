from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from agent_guard.harness.types import AssistantTurn, ToolCall


@dataclass(frozen=True)
class LLMSettings:
    api_key: str
    base_url: str
    model: str
    temperature: float = 0.0
    timeout_s: float = 30.0
    max_retries: int = 2


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
        timeout_s=float(os.getenv("OPENAI_TIMEOUT_SECONDS", "30")),
        max_retries=int(os.getenv("OPENAI_MAX_RETRIES", "2")),
    )


class OpenAICompatibleClient:
    """OpenAI 兼容 Chat Completions（DeepSeek 等），无 LangChain/LangGraph。"""

    def __init__(self, settings: LLMSettings):
        from openai import OpenAI

        self.settings = settings
        self._client = OpenAI(
            api_key=settings.api_key,
            base_url=settings.base_url,
            timeout=settings.timeout_s,
            max_retries=settings.max_retries,
        )

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> AssistantTurn:
        kwargs: dict[str, Any] = {
            "model": self.settings.model,
            "messages": messages,
            "temperature": self.settings.temperature,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        resp = self._client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message
        tool_calls: list[ToolCall] = []
        for tc in msg.tool_calls or []:
            raw = tc.function.arguments or "{}"
            try:
                args = json.loads(raw)
            except json.JSONDecodeError:
                args = {}
            if not isinstance(args, dict):
                args = {}
            tool_calls.append(
                ToolCall(id=tc.id, name=tc.function.name, arguments=args)
            )
        return AssistantTurn(content=msg.content, tool_calls=tool_calls)


def create_llm_client(settings: LLMSettings) -> OpenAICompatibleClient:
    return OpenAICompatibleClient(settings)
