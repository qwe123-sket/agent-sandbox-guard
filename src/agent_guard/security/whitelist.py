from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse


class PolicyViolation(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@dataclass
class ToolWhitelist:
    allowed_tools: set[str]
    blocked_paths: list[str]

    @classmethod
    def from_role(cls, policies: dict, role: str) -> "ToolWhitelist":
        role_cfg = policies["roles"].get(role)
        if not role_cfg:
            raise PolicyViolation("unknown_role", f"未知角色: {role}")
        return cls(
            allowed_tools=set(role_cfg["allowed_tools"]),
            blocked_paths=list(role_cfg.get("blocked_paths", [])),
        )

    def check_tool(self, tool_name: str) -> None:
        if tool_name not in self.allowed_tools:
            raise PolicyViolation(
                "tool_not_allowed",
                f"角色无权调用工具: {tool_name}",
            )

    def check_path_argument(self, path: str) -> None:
        for pattern in self.blocked_paths:
            if pattern in path:
                raise PolicyViolation(
                    "path_blocked",
                    f"路径被策略拒绝: {path}",
                )


class ParameterValidator:
    def __init__(self, policies: dict):
        self.rules = policies.get("parameter_rules", {})

    def validate(self, tool_name: str, arguments: dict[str, Any]) -> None:
        tool_rules = self.rules.get(tool_name, {})
        for field, rule in tool_rules.items():
            if field not in arguments:
                continue
            value = arguments[field]
            self._validate_field(tool_name, field, value, rule)

    def _validate_field(
        self,
        tool_name: str,
        field: str,
        value: Any,
        rule: dict,
    ) -> None:
        expected_type = rule.get("type")
        if expected_type == "string" and not isinstance(value, str):
            raise PolicyViolation(
                "invalid_type",
                f"{tool_name}.{field} 必须是字符串",
            )

        if isinstance(value, str):
            max_len = rule.get("max_length")
            if max_len and len(value) > max_len:
                raise PolicyViolation(
                    "value_too_long",
                    f"{tool_name}.{field} 超过长度限制",
                )
            for pattern in rule.get("deny_patterns", []):
                if re.search(pattern, value):
                    raise PolicyViolation(
                        "pattern_denied",
                        f"{tool_name}.{field} 命中拒绝规则",
                    )

        if field == "url" and isinstance(value, str):
            parsed = urlparse(value)
            allow_schemes = rule.get("allow_schemes", [])
            if allow_schemes and parsed.scheme not in allow_schemes:
                raise PolicyViolation(
                    "scheme_denied",
                    f"URL 协议不允许: {parsed.scheme}",
                )
            deny_hosts = rule.get("deny_hosts", [])
            if parsed.hostname in deny_hosts:
                raise PolicyViolation(
                    "host_denied",
                    f"URL host 被拒绝: {parsed.hostname}",
                )
