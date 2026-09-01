# Phase 02 → 企业级部署 Gap Summary

> 记录日期：2026-09-01（UTC）· 基线：`main` @ `cd555f7`（Phase 02 Content Agent MVP 已合并）
> 背景：当前全部开发在本地环境与 GitHub repo 内完成，按仓库规则运行 `mode: mock`、仅合成数据与
> Fake Credential（见 `AGENTS.md`、`docs/phase01/blocked.md`）。本文汇总 **现在（repo 内）就能修复的 gap**
> 与 **必须等接入企业云端 / 企业方确认后才能解决的 gap**，重点是后者。
> 依据：Phase 02 各 subphase evidence（`docs/phase02/subphase01–07-evidence.md`）、Phase 2 代码审查
> （2026-08-28，open-code-review 全文件审查 + code-review-graph 结构图谱）与 Phase 01 阻断清单。

---

## 1. 一览表

| 类别 | 现在可改（repo 内） | 只能连上企业云端后改 |
|---|---|---|
| 租户隔离 | ✅ 索引键 / 账本契约 / API 读路径补 tenant | — |
| 受控事实 / 完整性门 | ✅ Citation grounding、资产 hash 逐一校验 | ⛔ 真实 Product Schema 验收（B-01） |
| 身份与审批 | ✅ 修 nonce 无界增长、decide 过期校验 | ⛔ 企业 SSO/OIDC 真实接入（B-02/B-05） |
| Connector 真实模式 | ✅ 治理逻辑缺陷（预算日切、Retry-After 钳制等） | ⛔ 真实 LLM / 即梦 / Embedding 接入（B-03/B-05/B-10） |
| 状态持久化 | ✅ 定义持久化接口与原子语义 | ⛔ 企业 Postgres/对象存储/Queue/KMS（B-06） |
| 部署工件 | ✅ Dockerfile、lifespan、连接池、限流中间件 | ⛔ 四环境 VM/域名/Proxy、受保护流水线执行（B-06） |
| 人工验收 | — | ⛔ 实名 Medical/Marketing Reviewer UAT（B-09） |

---

## 2. ⛔ 现在改不了：必须等企业云端 / 企业方确认的 gap（重点）

这些 gap 的共同点：**代码扩展点已预留**（Protocol / secretref / 类型化 BLOCKED 错误），但解除依赖仓库外的
企业资源、Credential 或人工签字。按规则真实 Credential 不进仓库/CI，只能在受保护流水线与远端环境验证。

### G-E1 真实 Product Data（RAG 事实源）——依赖 B-01

- **现状**：`packages/product-rag` 全部基于 Fake Adapter + 合成 fixtures；contract 冻结为 Fake 基线。
- **Gap**：真实 MDM/PIM/DAM 的 Schema、版本与"批准状态"定义未经 Product Data Owner 确认；
  真实数据的召回质量、来源完整率（100% 硬门）、过期/撤销过滤均无法验收。
- **解除条件**：Product Data Owner 确认 Schema 并复核 subphase01/02 evidence 与 golden 数据集；
  企业侧提供只读 Product API 访问。

### G-E2 企业 SSO / OIDC 身份接入——依赖 B-02 / B-05

- **现状**：`apps/api` 仅 `FakeIdentityProvider` 用于本地/CI；`EnterpriseIdentityProvider`（OIDC）
  未配置即 fail-closed，签名校验器需运行时注入。
- **Gap**：DEV SSO App 未建立、OIDC/SAML 形式未确认；真实登录流、角色映射、token 生命周期
  只能在 DEV 环境端到端验证。
- **解除条件**：IAM 建立 DEV App 并发放 client 配置（经 Secret 管道注入，不进仓库）。

### G-E3 真实 LLM（DeepSeek）与 Embedding——依赖 B-03 / B-05

- **现状**：`connectors/llm/deepseek` 与 `product_rag/embedding.py` 均为确定性 Mock；
  config 仅 `secretref://`，`enabled:false`、`mode:mock`；sandbox/live 缺 env/secretref 即类型化启动失败。
- **Gap**：企业 LLM 审批的数据处理/区域/保留政策未记录；DEV Quota 未发放；真实模型的
  refusal/token-limit/限流行为、真实 Embedding 召回质量均无法验证。**尤其**：Citation grounding
  在真实模型下的对抗性验证（模型捏造引用）只能接真实 LLM 后做红队测试。
- **解除条件**：审批政策落档 + DEV Credential/Proxy/FQDN allowlist 由 pipeline 注入。

### G-E4 即梦（Jimeng）真实媒体生成——依赖 B-05 / B-10

- **现状**：异步 Job Worker、对账、资产校验全部走确定性 Mock transport 与本地 fixtures。
- **Gap**：即梦官方企业开通（Volcengine/BytePlus 或企业网关）、CN/Global 租户与区域选择、
  auth 方式、图片模型、数据保留/训练政策未经供应商文档与采购/安全确认；
  真实 URL 过期、供应商 hash 一致性、真实恶意样本扫描无法验收。
- **解除条件**：采购/安全确认供应商条款；DEV 租户 Credential 经 Secret 管道发放。

### G-E5 企业基础设施（持久化 / Queue / KMS / 监控）——依赖 B-06

- **现状**：审批链已用真实 Postgres 语义（Alembic + UoW），但 review store、OIDC nonce、
  连接器限流/预算、DeepSeek journal、package ledger、job store **全部为进程内内存实现**；
  对象存储/Queue/DLQ/OTel 仅 `infra/local` docker-compose Fake。
- **Gap**：多 worker/多副本部署下上述状态会分裂或丢失（限流预算 × 副本数、重启丢审批记录）；
  但真实的 Postgres/Redis/对象存储/KMS/监控实例、四环境 VM/DB/域名/出站 Proxy 工单均在企业侧，
  repo 内无法接入与联调。
- **解除条件**：Operations/Network/DBA/Security 完成 B-06 工单；届时按已预留的 Protocol
  （`JobStore`、`PackageStore`、`KnowledgeBaseIndex` 等）实现企业后端并在 DEV 联调。

### G-E6 受保护流水线部署与远端验证——依赖 B-06

- **现状**：`deploy-dev.yml` 为 fail-closed 占位；无任何真实部署路径。
- **Gap**：真实部署、DEV Smoke、灰度与回滚演练必须在受保护流水线与远端环境执行；
  本地/普通 CI 按规则禁止访问 DEV/SIT/UAT/PRD。
- **解除条件**：环境就绪后补 pipeline 实现（含 OIDC id-token、SHA 锁定的 Actions）。

### G-E7 实名双轨人工审核 UAT——依赖 B-09（+ B-05 的 DEV SSO）

- **现状**：HumanReview 仅 Fake Reviewer fixtures；P2-CP05 状态 `BLOCKED`。
- **Gap**：真实 Medical/Marketing Reviewer 未任命；实名双轨审批的端到端 UAT、
  审批签字对 canonical content hash 的绑定验收，AI 自评不能替代。
- **解除条件**：Medical/Compliance 任命实名 Reviewer 并在 DEV 完成 UAT 签字。

### G-E8 各硬门（Checkpoint）的人工签发

- **现状**：P2-CP01 ~ CP06 全部为 `BLOCKED`（非 FAIL）——这是自评纪律的正确结果。
- **Gap**：`PASS` 只能由对应 Owner（Product Data Owner、Reviewer、Architect 等）复核
  evidence 文档与 fixtures 后签发，无法由 repo 内工作解除。

---

## 3. ✅ 现在就能改：repo 内可修复的 gap（不依赖企业云端）

以下来自 Phase 2 代码审查（2026-08-28），mock 环境即可修复与测试，建议在接入企业云端**之前**完成，
否则 G-E 系列解除后会直接暴露：

### P1（部署前必须修）

| # | Gap | 位置 |
|---|---|---|
| G-R1 | 租户隔离缺 tenant：chunk_id 不含 tenant/market/locale；`delete_by_source` 无 tenant 参数；`ApprovedContentPackageV1`/lineage_key 无 tenant 字段；reviews/approvals API 读路径无 tenant 过滤 | `product_rag/chunking.py`、`index.py`、`content_package/store.py`、`contracts.py`、`apps/api/routes/{reviews,approvals}.py` |
| G-R2 | Citation 只验存在性不验来源：应校验 Claim 引用属于实际检索 fact 集（chunk_hash 成员校验） | `content_workflow/workflow.py`、`compliance/rules.py` |
| G-R3 | `_check_assets` 只比数量不比 hash，资产防篡改门实质 no-op | `content_package/builder.py` |
| G-R5 | 时间戳按字典序字符串比较 + 可选小数秒，合规过期门可判错 | `product_rag/models.py`、`rules.py`、`builder.py` 等 |
| G-R6 | Jimeng asset_issue 返工幂等键不变，永远返回旧资产 | `jimeng_connector/media_generator.py`、`worker.py` |

### P2（企业接入前应修）

- 审批 `decide` 不校验 `expires_at`；`/ready` 每次新建 engine；engine 懒加载竞态、无池配置、无 lifespan。
- OIDC `_pending_nonces` 无界增长；占位路由（runs/tasks/content）无鉴权、无限流。
- 连接器治理：预算/限流非线程安全、`daily_spent` 无日切、默认 `_noop_sleeper` 使退避为零等待、
  `Retry-After` 未被 `max_delay_ms` 钳制、`rework_count` 无上限。
- 禁用表达/推测扫描未覆盖 disclosures/claim 文本/alt_text；`revoke()` 无状态机校验。
- CI：`pip-audit` 未覆盖 compliance/content-package/jimeng；Actions 按 tag 非 SHA 锁定。
- 契约同步：Python Pydantic 为手写镜像，仅靠 fixtures 保证一致；connector-error 镜像不在 parity 测试内
  → 建议 schema 生成 Pydantic 或加 `jsonschema` 直验测试。
- 可先行准备的部署工件：API Dockerfile（非 root、只读 fs）、uvicorn 生产配置、优雅停机、
  限流/请求体上限中间件、持久化接口的 put-if-absent 原子语义定义。

---

## 4. 依赖与顺序建议

1. **现在**：完成 §3 的 G-R1 ~ G-R6（尤其 tenant 模型端到端补全），全部可在 mock 下 RED-GREEN 验证。
2. **B-06 环境就绪后**：以已预留 Protocol 实现企业持久化后端（Postgres/对象存储/Queue/KMS），
   替换进程内状态；补 deploy pipeline。
3. **B-02/B-03/B-05/B-10 Credential 经 pipeline 注入后**：逐个 connector 切 sandbox → DEV Smoke，
   对真实 LLM 做 Citation grounding 红队测试。
4. **B-01/B-09 人工侧就绪后**：真实 Product 数据验收 + 实名双轨 UAT，由 Owner 逐门签发 PASS，
   解除 P2-CP01 ~ CP06 的 `BLOCKED`。
