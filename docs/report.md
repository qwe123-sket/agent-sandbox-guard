# AI Agent 工具调用权限边界测试 — 项目报告

| 文档编号 | AGENT-GUARD-2025-01 |
|----------|---------------------|
| 版本 | v1.0 |

| 项目类型 | 个人研究 |

---

## 1. 摘要

本项目针对 AI Agent 工具调用的权限失控问题，设计并实现了一套沙箱化 Agent 原型系统。系统以 DeepSeek 大模型作为任务规划层，LangGraph 作为编排引擎，在工具执行路径上部署 PermissionGuard 权限网关，形成「规划—校验—执行—审计」闭环。

系统提供 8 个沙箱工具、3 级角色权限及 YAML 可配置安全策略。经 6 组攻击场景自动化回归测试，拦截率 100%；DeepSeek 端到端联调完成文件列举、写入、读取三步操作。代码规模约 1,040 行 Python。

---

## 2. 背景与目标

### 2.1 背景

Agent 接入外部工具后，风险从生成内容扩展到对文件系统、数据库和网络的实际操作。常见威胁包括：低权限角色调用高危工具、路径穿越读取沙箱外资源、prompt 注入诱导越权操作、多步工具链组合实现数据外泄等。

### 2.2 目标

- 构建可运行的 Agent 沙箱及工具集
- 实现统一的工具调用权限网关
- 对典型攻击场景进行可重复的自动化验证
- 接入 DeepSeek，验证真实大模型场景下的治理有效性

---

## 3. 系统架构

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐     ┌──────────┐
│  用户输入    │ ──► │ DeepSeek     │ ──► │ PermissionGuard │ ──► │  沙箱     │
│  (Prompt)   │     │ (LangGraph)  │     │ 白名单/校验/HITL │     │ 执行层   │
└─────────────┘     └──────────────┘     └────────┬────────┘     └──────────┘
                                                   │
                                                   ▼
                                            logs/audit.jsonl
```

### 3.1 规划层

DeepSeek `deepseek-chat` 通过 OpenAI 兼容接口接入，LangGraph 驱动 Agent 与工具的多轮交互。模型仅绑定当前角色白名单内的工具定义。

### 3.2 治理层（PermissionGuard）

| 环节 | 功能 |
|------|------|
| 工具白名单 | 按 readonly / operator / admin 限制可调用工具 |
| 参数校验 | 路径、URL、SQL 等字段的规则匹配与拒绝 |
| HITL | delete_file、db_write、http_post 需人工确认 |
| 审计 | 每次调用写入 JSONL，含角色、参数、决策、结果 |

策略配置位于 `config/policies.yaml`，与业务代码分离。

### 3.3 沙箱层

| 能力 | 实现 | 隔离方式 |
|------|------|----------|
| 文件 | sandbox/workspace/ | 路径 resolve，禁止目录逃逸 |
| 数据库 | SQLite | 独立数据文件；查询限制 SELECT |
| HTTP | httpx | scheme 与 host 黑名单 |

---

## 4. 实现概要

- **工具集**：8 个（read_file、write_file、delete_file、list_files、db_query、db_write、http_get、http_post）
- **角色模型**：readonly（4 工具）、operator（6 工具）、admin（8 工具）
- **验证模式**：MockPlanner 用于攻击回归；DeepSeek 用于真实 LLM 场景
- **代码组织**：`src/agent_guard/` 下分 sandbox、security、agent、guard 模块

---

## 5. 测试与验证

### 5.1 攻击回归

执行 `scripts/run_attack_suite.py`，6 个用例全部通过。

| 编号 | 场景 | 测试角色 | 预期 | 结果 | 拦截机制 |
|------|------|----------|------|------|----------|
| 1 | 越权删除 | readonly | 拒绝 | 通过 | 工具白名单 |
| 2 | 路径穿越 | operator | 拒绝 | 通过 | 参数规则 |
| 3 | 注入写库 | readonly | 拒绝 | 通过 | 工具白名单 |
| 4 | SSRF | operator | 拒绝 | 通过 | URL host 规则 |
| 5 | 工具链外发 | operator | 拒绝 | 通过 | HITL |
| 6 | 正常只读 | readonly | 放行 | 通过 | — |

### 5.2 单元测试

`pytest tests/`：3 项，全部通过。

### 5.3 DeepSeek 联调

`scripts/run_agent_llm.py --role operator`，任务为列举 workspace、创建 memo.txt、读取确认。

| 步骤 | 工具 | 结果 |
|------|------|------|
| 1 | list_files | 成功 |
| 2 | write_file | 成功，23 字符 |
| 3 | read_file | 内容与写入一致 |

单次任务共 3 次 tool call，均经 PermissionGuard 放行，审计日志已记录。

---

## 6. 结论

本项目完成了 Agent 工具调用权限边界的原型验证。PermissionGuard 在执行层对越权调用、恶意参数和高风险操作实现了有效拦截；DeepSeek 联调表明该治理机制可与真实大模型协同工作。

当前为逻辑沙箱，未采用容器级隔离；HITL 为命令行交互，HTTP 层未覆盖 redirect 跟随防护。上述项可作为后续迭代方向。

---

## 附录 A：环境与复现

```powershell
.\scripts\setup_env.ps1
copy .env.example .env
python scripts/run_attack_suite.py
python scripts/run_agent_llm.py --role operator
pytest tests/ -q
```

## 附录 B：术语

| 术语 | 说明 |
|------|------|
| PermissionGuard | 本项目工具调用权限网关 |
| HITL | Human-in-the-loop，高风险操作人工确认 |
| MockPlanner | 固定工具调用序列，用于可复现测试 |

---

*本报告描述内容为本地原型验证结果。*
