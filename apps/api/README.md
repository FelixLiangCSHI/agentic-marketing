# dmt-api — Control API 骨架（Phase 01 / Subphase 02）

企业内网 Python Control API 的最小骨架。Phase 01 中所有外部能力保持 `mode: mock`；
不访问真实 LLM、即梦、LinkedIn、Google Ads 或企业远端服务；配置中只允许 Secret Reference。

## 开发命令

```bash
python3 -m venv ../../.venv && ../../.venv/bin/pip install -e ".[dev]"

# 单元测试（含与 TypeScript 共享的契约 fixtures 验证）
python3 -m pytest

# 类型检查（strict）
python3 -m mypy
```

仓库根目录也提供 `npm run api:test` 与 `npm run api:typecheck`。

## 已实现端点

| 端点 | 行为 |
|---|---|
| `GET /api/health/live` | 仅检查进程存活 |
| `GET /api/health/ready` | 检查本地配置（不调用外部付费 API）；非 `mock` 模式 fail closed |
| `POST /api/v1/runs` | 类型化占位；输入按契约校验后返回 `501 not_implemented` |
| `GET /api/v1/runs/{run_id}` | 占位，`501 not_implemented` |
| `POST /api/v1/runs/{run_id}/cancel` | 占位，`501 not_implemented` |
| `GET /api/v1/tasks` | 占位，`501 not_implemented` |
| `GET /api/v1/approvals` | 占位，`501 not_implemented` |

错误响应统一使用版本化结构：`code`、`message`、`trace_id`、`retryable`、`details`；
不返回堆栈、Secret 或供应商原始 Token。

## 契约

`src/dmt_api/contracts.py` 中的 Pydantic 模型与
`packages/domain-contracts/schemas/*.v1.schema.json` 一一对应，并用同一套
Golden/Invalid fixtures（`packages/domain-contracts/fixtures/`）验证，
Python 与 TypeScript 结果必须 100% 一致。

## 依赖锁定理由

| 依赖 | 版本 | 理由 |
|---|---|---|
| fastapi | 0.141.1 | Control API 框架（计划技术基线）；当前最新稳定版 |
| pydantic | 2.13.4 | 契约运行时验证（Pydantic v2）；当前最新稳定版 |
| pytest | 9.1.1 | 单元测试（dev） |
| httpx | 0.28.1 | FastAPI TestClient 传输层（dev） |
| mypy | 2.3.1 | 严格类型检查（dev） |

SQLAlchemy / Alembic / LangGraph / OpenTelemetry 属于后续 Subphase（03+），
按最小实现原则暂不引入。
