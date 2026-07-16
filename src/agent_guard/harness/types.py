from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class AssistantTurn:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)


@dataclass(frozen=True)
class HarnessConfig:
    """Harness 运行预算；限制模型循环，避免失控或无限消耗。"""

    max_turns: int = 12
    max_tool_calls: int = 24
    max_consecutive_errors: int = 2
    run_timeout_s: float = 120.0
    stop_on_block: bool = False


@dataclass
class TraceEvent:
    role: str
    content: str
    name: str | None = None
    status: str | None = None
    turn: int = 0
    duration_ms: float = 0.0
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
