from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from agent_guard.config import load_config, load_policies
from agent_guard.guard import PermissionGuard
from agent_guard.security import HITLController


def create_mcp_server(project_root: Path | None = None) -> FastMCP:
    """创建只读 MCP Server；所有工具仍经过 PermissionGuard。"""
    config = load_config(project_root)
    policies = load_policies(config.policies_path)
    guard = PermissionGuard(
        config=config,
        policies=policies,
        role="readonly",
        session_id="mcp-readonly",
        hitl=HITLController(auto_approve=False),
    )
    server = FastMCP(
        "agent-guard",
        instructions=(
            "只读 Agent 工具服务。每次调用均经过角色白名单、参数校验和审计。"
        ),
    )

    @server.tool()
    def list_files(directory: str = ".") -> str:
        """列出沙箱 workspace 指定目录下的文件。"""
        return str(guard.execute("list_files", {"directory": directory}))

    @server.tool()
    def read_file(path: str) -> str:
        """读取沙箱 workspace 内的相对路径文件。"""
        return str(guard.execute("read_file", {"path": path}))

    @server.tool()
    def db_query(sql: str) -> str:
        """对沙箱 SQLite 执行只读 SELECT 查询。"""
        return str(guard.execute("db_query", {"sql": sql}))

    return server
