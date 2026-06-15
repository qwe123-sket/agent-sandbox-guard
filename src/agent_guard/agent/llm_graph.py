from __future__ import annotations

from typing import Annotated, Literal, TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

from agent_guard.agent.llm import build_guarded_tools
from agent_guard.guard import PermissionGuard

SYSTEM_PROMPT = """你是一个在受限沙箱中工作的助手。
- 文件操作只能在 sandbox/workspace 内进行，使用相对路径。
- 数据库只能访问沙箱 SQLite，查询用 db_query，写入用 db_write。
- 外部请求用 http_get / http_post。
- 如果工具返回 [权限网关拦截]，向用户说明被安全策略拒绝，不要重复尝试相同越权操作。
- 任务完成后用自然语言总结，不要再调用工具。"""


class LLMAgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


def build_llm_agent_graph(guard: PermissionGuard, llm: BaseChatModel):
    tools = build_guarded_tools(guard)
    tools_by_name = {tool.name: tool for tool in tools}
    llm_with_tools = llm.bind_tools(tools)

    def agent_node(state: LLMAgentState) -> dict:
        response = llm_with_tools.invoke(state["messages"])
        return {"messages": [response]}

    def tools_node(state: LLMAgentState) -> dict:
        last: AIMessage = state["messages"][-1]
        tool_messages: list[ToolMessage] = []
        for call in last.tool_calls:
            tool = tools_by_name.get(call["name"])
            if tool is None:
                content = f"[权限网关拦截] 工具不在白名单: {call['name']}"
            else:
                content = tool.invoke(call["args"])
            tool_messages.append(
                ToolMessage(content=str(content), tool_call_id=call["id"])
            )
        return {"messages": tool_messages}

    def route(state: LLMAgentState) -> Literal["tools", "__end__"]:
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "tools"
        return END

    graph = StateGraph(LLMAgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tools_node)
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", route, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")
    return graph.compile()
