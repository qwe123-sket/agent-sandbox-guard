from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class AuditRecord:
    timestamp: str
    session_id: str
    role: str
    tool_name: str
    arguments: dict[str, Any]
    decision: str
    reason: str = ""
    result_preview: str = ""

    @classmethod
    def now(
        cls,
        session_id: str,
        role: str,
        tool_name: str,
        arguments: dict[str, Any],
        decision: str,
        reason: str = "",
        result_preview: str = "",
    ) -> "AuditRecord":
        return cls(
            timestamp=datetime.now(timezone.utc).isoformat(),
            session_id=session_id,
            role=role,
            tool_name=tool_name,
            arguments=arguments,
            decision=decision,
            reason=reason,
            result_preview=result_preview,
        )


class AuditLogger:
    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, record: AuditRecord) -> None:
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")

    def read_all(self) -> list[dict]:
        if not self.log_path.exists():
            return []
        lines = self.log_path.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines if line.strip()]
