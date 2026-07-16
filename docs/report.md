# Agent Guard — Agent Harness 安全执行层 项目报告

| 文档编号 | AGENT-GUARD-2025-01 |
|----------|---------------------|
| 版本 | v2.1 |

| 项目类型 | 个人研究 |

---

## 1. 摘要

本项目按 **Harness Engineering** 实现 Agent 工具调用安全执行层：模型只负责提议 `tool_call`，**是否执行由 Harness Gate（PermissionGuard）决定**。

相对 v1（LangGraph 编排），v2 移除 LangGraph / LangChain，改为自研：

- `AgentHarness`：多轮 agent loop、运行预算、失败停止与结构化 trace
- `OpenAICompatibleClient`：DeepSeek 等兼容接口，支持超时和重试
- `run_mock_harness`：无 LLM 的确定性回归 loop
- `eval`：攻击 / 正常任务评测与延迟微基准
- `MCP Server`：面向外部 Agent 的只读工具入口

系统提供 8 个沙箱工具、3 级角色权限及 YAML 策略。攻击回归拦截率以 `run_attack_suite.py` 为准。

---

## 2. 背景与目标

Agent 接入外部工具后，风险扩展到文件系统、数据库与网络。业界共识：

```text
Agent ≈ 模型（推理） + Harness（工具执行、权限、沙箱、校验、观测）
```

目标：

- 自研最小 Harness loop，不依赖 LangGraph 状态图
- Gate 与 Sandbox 与模型解耦
- 攻击场景可重复自动化验证
- 可接 DeepSeek 做真实 LLM 联调

---

## 3. 系统架构

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐     ┌──────────┐
│  用户输入    │ ──► │ Model            │ ──► │ Gate            │ ──► │ Sandbox  │
│             │     │ DeepSeek tools   │     │ PermissionGuard │     │ 执行面   │
└─────────────┘     └────────┬─────────┘     └────────┬────────┘     └──────────┘
                             │                         │
                             └──── Harness Loop ───────┘
                                        │
                                        ▼
                                 logs/audit.jsonl
```

核心代码：`src/agent_guard/harness/loop.py` 中的 `AgentHarness.run()`。

---

## 4. 实现概要

| 模块 | 路径 | 职责 |
|------|------|------|
| Loop | `harness/loop.py` | model ↔ tool 回环、轮次/工具预算、失败停止、trace |
| LLM | `harness/llm.py` | OpenAI 兼容 client、请求超时与重试 |
| Tools | `harness/tools.py` | tool schema + `execute_via_gate` |
| Mock | `harness/mock.py` | 攻击回归用确定性 loop |
| Eval | `eval/` | 24 条用例、可靠性/安全指标、微基准 |
| MCP | `mcp/` | 只读 stdio MCP Server，调用仍经过 Gate |
| Gate | `guard.py` | 白名单 / 参数校验 / HITL / 审计 |
| Sandbox | `sandbox/` | 文件 / DB / HTTP |

---

## 5. 测试与验证

```powershell
python scripts/run_attack_suite.py
python scripts/run_eval_suite.py --iterations 1000
pytest tests/ -q
```

2026-07-18 本地确定性评测结果（详见 `reports/harness_eval.json`）：

| 指标 | 结果 |
|------|------|
| 攻击用例 | 14/14 拦截 |
| 正常任务 | 10/10 成功 |
| 误拦率 | 0%（0/10） |
| 本地 Gate 附加开销 | P95 < 0.5 ms（当前机器本地微基准） |
| pytest | 9 passed |

攻击场景覆盖角色越权、路径穿越、SSRF / 私网访问、危险 SQL、未知工具；正常任务覆盖文件、目录与只读数据库调用。

延迟数据来自 1000 次本地 `list_files` 微基准，仅用于衡量 Gate + 审计的本地附加开销，不代表 LLM 或网络端到端延迟。

---

## 6. 结论

v2.1 将编排从 LangGraph 迁到自研 Harness：模型可提议，Gate 决定执行，Sandbox 承载副作用；并补齐确定性评测、运行预算、MCP 工具入口和 CI。HTTP 工具关闭自动重定向，并统一拦截 loopback、link-local、private 等 IP 字面量。

当前限制：文件沙箱仍为逻辑隔离而非容器隔离；域名解析后的私网地址与 DNS rebinding 尚需在网络出口层治理；LLM 端到端任务成功率未纳入确定性 CI 指标。

## 7. 上下游

| 项目 | Harness 位置 |
|------|----------------|
| PromptSentinel | 输入 / 输出治理 |
| RagGuard | 可信上下文 |
| Agent Guard | 工具执行治理（本项目） |
