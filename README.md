# AI Agent 工具调用权限边界测试

个人研究项目。DeepSeek 负责 Agent 规划，LangGraph 编排调用流程，PermissionGuard 在工具执行前做权限校验。

完整说明见 [docs/report.md](docs/report.md)。

## 环境

```powershell
.\scripts\setup_env.ps1
.venv\Scripts\activate
copy .env.example .env
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

`.env` 中配置 DeepSeek API Key，详见 `.env.example`。

## 运行

```powershell
python scripts/run_attack_suite.py
python scripts/run_agent_llm.py --role operator
pytest tests/ -q
```

| 脚本 | 说明 |
|------|------|
| `run_attack_suite.py` | 攻击用例回归（MockPlanner，不消耗 API） |
| `run_agent_llm.py` | DeepSeek Agent |
| `run_agent.py` | Mock 固定流程演示 |

审计日志：`logs/audit.jsonl`

## 结构

```
config/policies.yaml    角色与策略
src/agent_guard/        网关、沙箱、Agent
sandbox/                文件与数据库沙箱
scripts/                运行入口
tests/                  测试
```

MIT
