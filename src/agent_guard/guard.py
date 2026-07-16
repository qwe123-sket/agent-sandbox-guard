from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from agent_guard.config import AppConfig
from agent_guard.sandbox import SandboxContext
from agent_guard.sandbox import api_client, database, filesystem
from agent_guard.security import (
    AuditLogger,
    AuditRecord,
    HITLController,
    ParameterValidator,
    PolicyViolation,
    ToolWhitelist,
)


@dataclass
class ToolDefinition:
    name: str
    description: str
    risk_level: str
    handler: Callable[[SandboxContext, dict[str, Any]], Any]


def build_tool_registry() -> dict[str, ToolDefinition]:
    return {
        "read_file": ToolDefinition(
            name="read_file",
            description="读取 workspace 内文件",
            risk_level="low",
            handler=lambda ctx, args: filesystem.read_file(ctx, args["path"]),
        ),
        "write_file": ToolDefinition(
            name="write_file",
            description="写入 workspace 内文件",
            risk_level="medium",
            handler=lambda ctx, args: filesystem.write_file(
                ctx, args["path"], args["content"]
            ),
        ),
        "delete_file": ToolDefinition(
            name="delete_file",
            description="删除 workspace 内文件",
            risk_level="high",
            handler=lambda ctx, args: filesystem.delete_file(ctx, args["path"]),
        ),
        "list_files": ToolDefinition(
            name="list_files",
            description="列出 workspace 目录",
            risk_level="low",
            handler=lambda ctx, args: filesystem.list_files(
                ctx, args.get("directory", ".")
            ),
        ),
        "db_query": ToolDefinition(
            name="db_query",
            description="只读 SQL 查询",
            risk_level="low",
            handler=lambda ctx, args: database.query(ctx, args["sql"]),
        ),
        "db_write": ToolDefinition(
            name="db_write",
            description="写入 SQL（INSERT/UPDATE）",
            risk_level="high",
            handler=lambda ctx, args: database.execute(ctx, args["sql"]),
        ),
        "http_get": ToolDefinition(
            name="http_get",
            description="发起 GET 请求",
            risk_level="medium",
            handler=lambda ctx, args: api_client.http_get(args["url"]),
        ),
        "http_post": ToolDefinition(
            name="http_post",
            description="发起 POST 请求",
            risk_level="high",
            handler=lambda ctx, args: api_client.http_post(
                args["url"], args.get("json_body")
            ),
        ),
    }


@dataclass
class GuardDecision:
    allowed: bool
    reason: str = ""
    needs_approval: bool = False


class PermissionGuard:
    """Harness Gate：工具调用执行前的统一权限网关（白名单 / 校验 / HITL / 审计）。"""

    def __init__(
        self,
        config: AppConfig,
        policies: dict,
        role: str,
        session_id: str,
        hitl: HITLController | None = None,
    ):
        self.config = config
        self.policies = policies
        self.role = role
        self.session_id = session_id
        self.whitelist = ToolWhitelist.from_role(policies, role)
        self.validator = ParameterValidator(policies)
        self.hitl = hitl or HITLController()
        self.audit = AuditLogger(config.audit_log_path)
        self.hitl_tools = set(policies.get("hitl_required", []))
        self.registry = build_tool_registry()
        self.sandbox = SandboxContext(config.workspace_dir, config.data_dir)

    def preflight(self, tool_name: str, arguments: dict[str, Any]) -> GuardDecision:
        try:
            self.whitelist.check_tool(tool_name)
            if "path" in arguments:
                self.whitelist.check_path_argument(arguments["path"])
            self.validator.validate(tool_name, arguments)
        except PolicyViolation as exc:
            self._log(tool_name, arguments, "denied", str(exc))
            return GuardDecision(allowed=False, reason=str(exc))

        if self.hitl.requires_hitl(tool_name, self.hitl_tools):
            approved = self.hitl.request_approval(
                tool_name,
                arguments,
                description=f"高风险操作: {tool_name}",
            )
            if not approved:
                self._log(tool_name, arguments, "pending_hitl", "等待人工确认")
                return GuardDecision(
                    allowed=False,
                    reason="需要人工确认",
                    needs_approval=True,
                )

        return GuardDecision(allowed=True)

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        decision = self.preflight(tool_name, arguments)
        if not decision.allowed:
            raise PolicyViolation("blocked", decision.reason)

        tool = self.registry.get(tool_name)
        if not tool:
            raise PolicyViolation("unknown_tool", f"未注册工具: {tool_name}")

        try:
            result = tool.handler(self.sandbox, arguments)
            preview = str(result)[:200]
            self._log(tool_name, arguments, "allowed", result_preview=preview)
            return result
        except Exception as exc:
            self._log(tool_name, arguments, "error", str(exc))
            raise

    def _log(
        self,
        tool_name: str,
        arguments: dict,
        decision: str,
        reason: str = "",
        result_preview: str = "",
    ) -> None:
        record = AuditRecord.now(
            session_id=self.session_id,
            role=self.role,
            tool_name=tool_name,
            arguments=arguments,
            decision=decision,
            reason=reason,
            result_preview=result_preview,
        )
        self.audit.write(record)
