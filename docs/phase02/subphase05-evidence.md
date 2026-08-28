# Phase 02 / Subphase 05 Evidence — 即梦（Jimeng）媒体 Connector

日期：2026-08-28 · 分支：`copilot/phase-02-content-agent-mvp` · 模式：GitHub repo（`mode: mock`，无外部 HTTP）

## 1. 交付物

| 交付物 | 位置 |
|---|---|
| 统一 Connector 接口 | `connectors/jimeng/src/jimeng_connector/connector.py`（`validate_config/dry_run/execute/get_status/reconcile/cancel/normalize_error`；图片生成为异步 Job，全部 Job 动作受支持；非图片能力 `NotSupportedError`，不伪装） |
| 非敏感配置（父模板） | `config/jimeng.yaml`（`enabled:false`、`mode:mock`、env 间接引用、Secret 仅 `secretref://`、`callback_webhook_enabled:false`） |
| 配置 Schema + 运行时解析 | `config.py`（`extra=forbid`；Cookie/浏览器/非官方 auth 立即类型化 `FAIL`；CN 与 Global 租户禁止混用（region 前缀绑定）；sandbox/live 缺任一 env/secretref 即类型化启动失败） |
| Job/资产契约 + 幂等键 | `contracts.py`（`MediaJobRequestV1/JobRecordV1/GeneratedAssetV1`；`idempotency_key = run_id_node_id_input_hash`；request hash 绑定 model + config hash） |
| 确定性异步 Mock | `transport.py` + `tests/fixtures/jimeng/generated/`（completed、failed_job、cancelled、429 create、timeout-but-created、URL 过期、非法 MIME、合成恶意样本、unknown job；N 次轮询后完成） |
| 异步 Worker（持久队列轮询） | `worker.py`（提交→入队→轮询→下载→校验→导入；创建超时先 `find_job` 对账绝不盲目重建；unknown job → `NEEDS_RECONCILE` + DLQ 人工对账；URL 过期重取 result 引用不重建 Job；Worker 重启用同一 store/queue 恢复） |
| 资产校验 + 对象存储导入 | `storage.py`（TLS/MIME 白名单/大小/供应商 hash 一致/合成恶意扫描；不通过则不落盘；`generated` 与 `approved` 分区隔离；对象版本不可变，修改产生新版本） |
| 限流与费用门禁 | `governance.py`（本地 RPM 窗口、最大并发、jobs/day、per-run/daily 预算 + 每 run 资产数上限；80% 告警、100% 硬停，均在 create 前检查） |
| 错误标准化 | `errors.py` → `connector-error.v1` 契约（`ConnectorErrorV1`，connector=`jimeng`） |
| Content Workflow 桥接 | `media_generator.py`（`JimengMediaGenerator` 实现 `MediaGenerator` 协议；`GenerateMedia` 槽位零图改动切换 Fake ↔ Jimeng） |
| DEV Smoke（受保护） | `scripts/dev_smoke.py`（缺 `JIMENG_DEV_APPROVAL_EVIDENCE` 即 `BLOCKED` 退出，不发 HTTP；repo 不含真实 HTTP client） |
| CI 门禁 | `.github/workflows/ci.yml` 新增 `jimeng-connector` job；npm scripts `jimeng:test`/`jimeng:typecheck` |

## 2. 租户/模型/config 版本

- 供应商路径：仅官方企业 API（`volcengine_cn`｜`byteplus_global`｜`approved_enterprise_gateway`）；Cookie/逆向/第三方转售代理被 schema 与运行时双重禁止
- 租户-区域绑定：`volcengine_cn→cn-*`、`byteplus_global→ap-/eu-/us-*`、`approved_enterprise_gateway→gw-*`，混用即类型化失败
- Mock 模型：`jimeng-image-mock`（capability=`image_generation`，`png|jpeg|webp`）；真实 model_id/endpoint/quota 为 DEV env + 审批事项
- Config：`config/jimeng.yaml` schema_version `1.0`；config hash 由 `JimengConfig.config_hash()` 计算并绑定进 request hash
- Mock 定价为合成常数（`MOCK_COST_PER_IMAGE=0.02`），真实定价属审批事项

## 3. 命令与结果

| 命令 | 结果 |
|---|---|
| `connectors/jimeng: python3 -m pytest` | 44 passed（config/租户隔离/禁 Cookie；幂等 100×→1 个 Job；创建超时对账；Worker 重启恢复；URL 过期重取；unknown job→DLQ；MIME/恶意样本拒绝且不落盘；版本不可变；预算/RPM/day 限额；normalize_error；工作流端到端） |
| `connectors/jimeng: python3 -m mypy` / `mypy tests scripts` | strict，0 错误 |
| `python3 scripts/dev_smoke.py`（无审批） | `BLOCKED`，exit 2，无外部 HTTP |
| 全量回归 | apps/api 97 passed/48 skipped、harness 45、infra 43、product-rag 55、content-workflow 28、deepseek 36、evals+integration 17、contract 37+ts；npm test 113 pass/tsc/eslint 全绿 |
| Secret 扫描 | 0 发现（303 files） |
| CodeQL（actions/python/javascript） | 见最终提交（目标 0 告警） |

## 4. Prompt 任务映射

| 任务 | 状态 |
|---|---|
| 1. 官方企业接入声明 + 禁 Cookie/逆向/第三方代理 | 完成（schema `Literal` + 运行时 `ForbiddenAuthError`=FAIL） |
| 2. 父模板非敏感配置，默认 enabled:false/mode:mock | 完成 |
| 3. Credential 仅 secretref（AK/SK 或 Bearer）；CN/Global 租户隔离 | 完成 |
| 4. 异步 Job：创建→持久队列轮询→下载→校验→导入；无公网 Webhook | 完成 |
| 5. 幂等：重复提交/创建超时/Worker 重启不产生重复 Job | 完成（100× 测试、timeout-but-created 对账、restart-resume） |
| 6. Unknown job 停止创建 → NEEDS_RECONCILE + DLQ 人工对账 | 完成 |
| 7. 资产校验（TLS/MIME/大小/hash/恶意扫描）+ generated/approved 分区 + 版本不可变 | 完成 |
| 8. 限流/并发/jobs-day/预算/资产上限（80%/100%） | 完成 |
| 9. DEV Smoke 缺审批不运行 | 完成（`BLOCKED` 验证） |

## 5. P2-CP03（媒体 Connector Checkpoint）

**状态：`BLOCKED`（真实路径）/ Mock 基线证据已备**

- Mock 全链路（create→poll→download→validate→import→workflow 打包前）确定性通过，无外部 HTTP，Secret 泄漏 0
- 即梦官方企业开通（Volcengine/BytePlus 或企业网关）、租户/区域选择、auth 方式、图片模型与数据保留/训练政策**未经供应商文档与采购/安全确认** → 真实模式 `BLOCKED`
- Marketing + Security 人工复核未执行；AI 自评不能批准。未保存 Chain-of-Thought

## 6. 费用/风险/阻断（Job/资产证据）

- 费用：Mock 合成定价，本次 0 真实费用；预算/资产上限门禁已生效并有测试
- Job 证据：mock job id 为幂等键派生哈希（`mock-job-*`），JobRecord 持久化 provider_job_id/request_hash/state/asset key+version+sha256；资产落 `local/<tenant>/content-agent-generated/<run_id>/…`，审批后复制到 `content-agent-approved`
- B-10（新）：即梦官方企业资质/租户/模型/保留政策未确认 → sandbox/live 及 DEV Smoke `BLOCKED`
- B-05 沿用：DEV Credential/Proxy/FQDN allowlist 未发放 → 真实传输由 DEV pipeline 注入
- 沿用：B-01（Product schema）、B-03（企业 LLM 审批）、B-09（真实 Medical Reviewer）

## 7. Ready for Subphase 06

是 —— Content Agent 的文案（DeepSeek）与媒体（Jimeng）槽位均已可插拔且带治理；工作流打包、审阅与对象存储链路就绪。
