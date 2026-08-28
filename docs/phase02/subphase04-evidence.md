# Phase 02 / Subphase 04 Evidence — DeepSeek Connector

日期：2026-08-28 · 分支：`copilot/phase-02-content-agent-mvp` · 模式：GitHub repo（`mode: mock`，无外部 HTTP）

## 1. 交付物

| 交付物 | 位置 |
|---|---|
| 统一 Connector 接口 | `connectors/llm/deepseek/src/deepseek_connector/connector.py`（`validate_config/dry_run/execute/get_status/reconcile/cancel/normalize_error`；同步 Chat，异步动作返回 `NOT_SUPPORTED`） |
| 非敏感配置（父模板） | `config/deepseek.yaml`（`enabled:false`、`mode:mock`、env 间接引用、Secret 仅 `secretref://`） |
| 配置 Schema + 运行时解析 | `config.py`（`extra=forbid`；sandbox/live 缺 endpoint/model/quota/proxy/allowlist/secretref 即类型化失败；raw key 拒绝） |
| 请求/结果契约 + request hash | `contracts.py`（`ChatRequestV1/ChatResultV1`，hash 绑定 model + config hash，`retry_requires_same_request_hash`） |
| 确定性 Mock + fault injection | `transport.py` + `tests/fixtures/deepseek/`（normal、refusal、invalid JSON、429、timeout、5xx、token limit、uncited claim；种子化一次性故障注入） |
| 限流与费用门禁 | `governance.py`（本地 RPM 窗口、最大并发、per-run/daily 预算，80% 告警、100% 硬停） |
| 重试策略 | 有界指数退避 + 抖动（408/429/5xx/timeout），尊重 `Retry-After`；400/401/403/404/409/422 不重试 |
| 观测记录 | `observability.py`（request hash、model/prompt/config version、token/费用；无 body、无 Secret） |
| 错误标准化 | `errors.py` → `connector-error.v1` 契约（`ConnectorErrorV1`，connector=`llm`） |
| Content Workflow 桥接 | `workflow_model.py`（`DeepSeekContentModel` 实现 `ContentModel` 协议；模型引用不可信，仅按 `chunk_hash` 由 RAG 事实解析） |
| DEV Smoke（受保护） | `scripts/dev_smoke.py`（缺 `DEEPSEEK_DEV_APPROVAL_EVIDENCE` 即 `BLOCKED` 退出，不发 HTTP） |
| CI 门禁 | `.github/workflows/ci.yml` 新增 `deepseek-connector` job；security job pip-audit 覆盖 |

## 2. Provider/config 版本

- Provider：`deepseek`（Chat Completions，OpenAI 兼容 wire payload）
- Config：`config/deepseek.yaml` schema_version `1.0`；config hash 由 `DeepSeekConfig.config_hash()` 计算并记入每条 journal
- Prompt：`content-copy-prompt/1.0.0`
- Mock 定价为合成常数（`governance.py`），真实定价属审批事项

## 3. 命令与结果

| 命令 | 结果 |
|---|---|
| `connectors/llm/deepseek: python3 -m pytest` | 36 passed（config schema/unknown field/secret absence；mock contract/fault/retry/budget/journal；normalize_error；workflow 集成） |
| `connectors/llm/deepseek: python3 -m mypy` / `mypy tests` | strict，0 错误 |
| `python3 scripts/dev_smoke.py`（无审批） | `BLOCKED`，exit 2，无外部 HTTP |
| 全量回归 | apps/api 97 passed/48 skipped、harness 45、infra 43、product-rag 55、content-workflow 28、evals 5、integration 12；npm test/eslint/tsc/build 全绿 |
| Secret 扫描 | 0 发现 |
| CodeQL（actions/python/javascript） | 0 告警 |

## 4. Prompt 任务映射

| 任务 | 状态 |
|---|---|
| 1. 统一接口 + NOT_SUPPORTED | 完成 |
| 2. 父模板非敏感配置，默认 enabled:false/mode:mock | 完成 |
| 3. API Key 仅经 Secret Resolver；endpoint/model/quota/proxy 来自配置 | 完成（raw key 在 config/env 均被拒绝） |
| 4. 超时、本地队列、预算、最大并发 | 完成 |
| 5. 有界退避+抖动、尊重 Retry-After、4xx 不盲重试 | 完成（同一 request hash 重放，测试断言 payload 相同） |
| 6. 记录 hash/version/token/费用，不记录 body/Secret | 完成（journal 序列化断言无正文/无 secretref） |
| 7. fixtures 覆盖 8 种场景 | 完成 |
| 8. DEV Smoke 缺审批不运行 | 完成（`BLOCKED` 验证） |

## 5. P2-CP02（AI 质量 Checkpoint）

**状态：`BLOCKED`（真实路径）/ Mock 基线证据已备**

- Mock 输出 Claim 来源覆盖 100%（无引用 Claim 被合规拦截 → `BLOCKED`，测试证明）
- 结构化输出/渠道硬规则经 Content Workflow 门禁 100% 通过；Mock 无外部 HTTP；Secret 泄漏 0
- 企业 LLM 审批、数据处理/区域/保留政策、DEV Quota 未记录 → DeepSeek 真实模式 `BLOCKED`
- Marketing + QA 人工复核未执行；AI 自评不能批准。未保存 Chain-of-Thought

## 6. 费用/风险/阻断

- 费用：Mock 合成定价，本次 0 真实费用；预算门禁（80%/100%）已生效并有测试
- B-03：企业 LLM/DeepSeek 审批未记录 → sandbox/live 及 DEV Smoke `BLOCKED`
- B-05：DEV Credential/Proxy/FQDN allowlist 未发放 → 真实传输由 DEV pipeline 注入，repo 不含真实 HTTP client
- 官方 endpoint/model/quota 未经 Architecture/Security 对照 DeepSeek 官方文档核验 → 启用前必须核验
- 沿用：B-01（Product schema）、B-09（真实 Medical Reviewer）

## 7. Ready for Subphase 05

是 —— Connector SDK 模式（接口/错误标准化/治理）可直接复用于即梦媒体 Connector；`ContentWorkflow` 的 media_generator 槽位与 `MediaGenerator` 协议已就绪。
