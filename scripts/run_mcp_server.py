#!/usr/bin/env python3
"""以 stdio 方式启动 Agent Guard 只读 MCP Server。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_guard.mcp import create_mcp_server


if __name__ == "__main__":
    create_mcp_server().run(transport="stdio")
