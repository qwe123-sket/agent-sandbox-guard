from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class PendingApproval:
    tool_name: str
    arguments: dict
    description: str


@dataclass
class HITLController:
    """人工确认控制器。默认自动拒绝，测试时可注入 approve 回调。"""

    auto_approve: bool = False
    _pending: list[PendingApproval] = field(default_factory=list)
    _approver: Callable[[PendingApproval], bool] | None = None

    def set_approver(self, approver: Callable[[PendingApproval], bool]) -> None:
        self._approver = approver

    def requires_hitl(self, tool_name: str, hitl_tools: set[str]) -> bool:
        return tool_name in hitl_tools

    def request_approval(
        self,
        tool_name: str,
        arguments: dict,
        description: str,
    ) -> bool:
        pending = PendingApproval(tool_name, arguments, description)
        self._pending.append(pending)

        if self.auto_approve:
            return True
        if self._approver:
            return self._approver(pending)

        # CLI 模式下由 run_agent.py 接管交互
        return False

    @property
    def pending(self) -> list[PendingApproval]:
        return list(self._pending)
