import asyncio

from agent_guard.mcp import create_mcp_server


def test_mcp_server_exposes_only_readonly_guarded_tools():
    async def inspect_server():
        server = create_mcp_server()
        tools = await server.list_tools()
        names = {tool.name for tool in tools}
        result = await server.call_tool("list_files", {"directory": "."})
        return names, result

    names, result = asyncio.run(inspect_server())

    assert names == {"list_files", "read_file", "db_query"}
    assert result
