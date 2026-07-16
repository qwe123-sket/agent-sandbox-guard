# Agent Guard

Agent Guard 是一个轻量级 Agent Harness 与工具执行安全网关。模型负责生成工具调用请求，Harness 负责循环控制、工具注册、权限校验、沙箱执行、人工审批和审计。项目使用 OpenAI 兼容接口接入 DeepSeek，不依赖 LangChain 或 LangGraph 编排。

## 功能

- 多轮 Agent Loop：消息组装、Tool Schema、结果回灌和停止条件
- 运行控制：最大轮次、工具调用预算、超时、重试和连续错误停止
- 权限网关：按角色暴露工具、参数校验和策略拒绝
- HITL：高风险工具执行前人工确认
- 沙箱工具：文件、SQLite 和 HTTP
- 结构化追踪：轮次、状态、耗时、停止原因和工具调用数
- JSONL 审计：角色、参数、决策、原因和结果摘要
- MCP：面向外部 Agent 的只读 stdio Server
- 确定性评测：攻击调用、正常任务和本地 Gate 开销

## 架构

```text
User task
    │
    ▼
Model (OpenAI-compatible tool calling)
    │
    ▼
AgentHarness
    ├─ turn / tool budgets
    ├─ timeout / retry / stop policy
    └─ structured trace
    │
    ▼
PermissionGuard
    ├─ role allowlist
    ├─ argument validation
    ├─ HITL
    └─ audit
    │
    ▼
Sandbox tools (filesystem / SQLite / HTTP)
```

所有工具执行均通过 `PermissionGuard.execute()`，包括 LLM Tool Calling、Mock 评测和 MCP 入口。

## 环境要求

- Python 3.10+
- DeepSeek 或其他 OpenAI 兼容 API（仅 LLM 运行模式需要）

## 安装

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

配置模型：

```bash
copy .env.example .env
```

```dotenv
OPENAI_API_KEY=your-api-key
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-chat
OPENAI_TIMEOUT_SECONDS=30
OPENAI_MAX_RETRIES=2
```

## 使用

### Mock Harness

```bash
python scripts/run_agent.py --role operator
```

Mock 模式使用固定工具序列，不调用模型 API，适合验证权限、HITL 和审计。

### LLM Harness

```bash
python scripts/run_agent_llm.py \
  --role operator \
  --max-turns 12 \
  --max-tool-calls 24 \
  --timeout 120 \
  --trace-output reports/llm_trace.json
```

可用角色：

| 角色 | 权限范围 |
|------|----------|
| `readonly` | 读文件、列目录、只读 SQL、HTTP GET |
| `operator` | readonly + 写文件、HTTP POST |
| `admin` | 全部工具，包括删除文件和数据库写入 |

`delete_file`、`db_write` 和 `http_post` 默认需要 HITL。

### 确定性评测

```bash
python scripts/run_eval_suite.py --iterations 1000
pytest tests/ -q
```

当前提交附带的 [`reports/harness_eval.json`](reports/harness_eval.json) 记录：

| 指标 | 结果 |
|------|------|
| 攻击调用 | 14/14 拦截 |
| 正常任务 | 10/10 成功 |
| 误拦 | 0/10 |
| 本地 Gate 附加开销 | P95 < 0.5 ms |
| 测试 | 9 passed |

延迟数据来自当前机器上 1000 次本地 `list_files` 微基准，仅用于观察 Gate 与审计的附加开销，不代表 LLM 或网络端到端延迟。

### MCP Server

```bash
python scripts/run_mcp_server.py
```

MCP 入口仅暴露 `list_files`、`read_file` 和 `db_query`：

```json
{
  "mcpServers": {
    "agent-guard": {
      "command": "python",
      "args": ["scripts/run_mcp_server.py"]
    }
  }
}
```

## 策略配置

`config/policies.yaml` 定义：

- 角色与工具白名单
- 禁止访问的路径
- 高风险 HITL 工具
- 字段类型和长度约束
- URL scheme、host 和私网地址限制
- SQL 关键字限制

HTTP 工具关闭自动重定向，避免公网 URL 通过 30x 跳转到内网地址。

## 项目结构

```text
src/agent_guard/
├── eval/         用例、指标与报告
├── harness/      Loop、LLM Client、Tool Schema、Mock
├── mcp/          只读 MCP Server
├── sandbox/      文件、SQLite、HTTP 工具
├── security/     白名单、参数校验、HITL、审计
└── guard.py      工具执行网关
```

## 安全边界

- 文件沙箱是路径级逻辑隔离，不等同于容器或虚拟机隔离。
- URL 校验覆盖 IP 字面量和禁止 host；DNS rebinding 仍需由网络出口策略处理。
- HITL 的安全性取决于审批端身份认证和操作上下文展示。
- 当前评测为本地确定性用例，不代表生产流量下的检测率。
- LLM 输出不应直接作为授权依据，工具执行权限始终由服务端策略决定。

## License

MIT
