# Phase 02：Content Creation & Compliance Agent MVP

> 计划窗口：2026-09-07 至 2026-09-25  
> 路线图映射：原 Phase 2  
> 阶段里程碑：从批准产品资料生成可追溯内容，经过自动检查和人工 Medical/Marketing 审核后输出不可变 `ApprovedContentPackage`  
> 并行关系：可在 Phase 01 后半段启动，但只可依赖已冻结的 Harness 与 Domain Contract  
> 执行模式：**Repo-first Hybrid**；Content/RAG/Compliance 主要在 GitHub 开发，真实 Product/模型/媒体连接在 DEV/SIT 远端验证

## 1. 阶段目标

1. 建立 Product 数据只读契约、批准数据摄取、版本化索引和可追溯 RAG。
2. 建立独立 Content Agent Runtime、LangGraph Workflow、Prompt/Skill/Policy 版本管理。
3. 接入 DeepSeek 候选 LLM Connector，并提供默认关闭的真实模式和确定性 Stub。
4. 接入即梦候选媒体 Connector，并提供异步任务、轮询、成本控制和确定性 Stub。
5. 生成 Content Brief、渠道文案变体和媒体资产，但不执行任何外部发布。
6. 建立 Medical Compliance & QA、引用追溯、严重度、定点返工和人工审批。
7. 产出版本化、哈希绑定、不可原位修改的 `ApprovedContentPackage`。
8. 建立 Golden、Adversarial、Contract、Workflow 和安全测试门禁。

## 2. Scope / Non-scope

### 2.1 本阶段包含

- Product MDM/PIM/DAM 只读 Adapter。
- 批准状态、版本、市场、语言、有效期和撤销状态。
- RAG 摄取、Chunk、Embedding、索引版本和引用返回。
- Content Brief、文案和渠道变体。
- DeepSeek 文本生成 Connector。
- 即梦图片生成 Connector；如实际租户只提供视频模型，图片能力不得被虚构为已接通。
- 品牌、Medical、市场法规和渠道规格 Skill。
- 确定性规则 + 模型 Critic + 人工 Reviewer 三层门。
- Content Review UI、拒绝意见和指定节点返工。
- `ApprovedContentPackage` v1。

### 2.2 本阶段不包含

- LinkedIn、Google Ads 或其他渠道发布。
- Campaign 预算、账户或渠道写凭据。
- Agent 自行签发 Medical 最终批准。
- 互联网开放检索进入批准事实库。
- 将用户附件、Memory 或模型生成内容当作已批准产品事实。
- 同时接入多个媒体供应商。
- 自动视频能力；除非业务明确将其纳入首发且正式 API 已审批。
- Meta、Instagram、YouTube、邮件实际发送。

### 2.3 GitHub Repo 与远端环境分工

| 位置 | 本阶段任务 | 允许的数据/凭据 | 完成证据 |
|---|---|---|---|
| GitHub PR/普通 CI | Product/RAG Contract、Content Workflow、Compliance、Prompt/Skill/Policy、DeepSeek/即梦 Adapter、Mock、Golden/Adversarial Eval、Review UI | 合成或脱敏 fixture；无真实 Secret；外部 HTTP 默认关闭 | Unit/Contract/Workflow/Security/Eval 报告 |
| 共享 DEV | Product API、Embedding、LLM/媒体开发 Credential、PostgreSQL、Queue、Object Store、SSO 和人工 Review 集成 | DEV Secret Manager 的短期身份和批准脱敏数据 | DEV Integration、Trace/Audit 和费用报告 |
| SIT | 真实网络路径、FQDN、限流、异步媒体恢复和 Reviewer 业务路径 | SIT 独立 Credential/Project/Bucket/Queue | SIT Contract/E2E、Provider Job 和 Checkpoint Evidence |

执行边界：

- Coding Agent 可以在 GitHub 完成 Mock MVP 和绝大多数质量优化，但不能仅凭本地结果宣称 Product RAG、DeepSeek 或即梦已真实接通。
- 远端测试由受保护 Pipeline 触发，使用企业内自托管 Runner；不从普通 PR、Fork 或开发者笔记本注入真实 Credential。
- Prompt、Skill、Policy、JSON Schema、Connector 代码和非敏感配置必须进 Repo；Product 原始数据、媒体原文件、API 响应和 Secret 留在远端受控存储。
- 远端失败应修复 Repo 中的代码/配置/IaC，再重新部署；禁止直接修改远端 Python 文件、Prompt 或数据库记录形成不可追溯差异。
- Phase 02 的代码工作可在 GitHub 收敛，阶段退出仍要求远端 Product/Provider 门禁和人类 Medical/Marketing 复核。

## 3. 前置条件

### 3.1 必须完成

- Phase 01 已冻结：
  - Run、Task、Approval、Audit、Connector Error。
  - `ApprovedContentPackage` v1。
  - Tool Level、Hook 顺序和 Secret Reference 规范。
- Fake Queue、Object Store、Secret Resolver 和 Identity Provider 可用。
- Medical Reviewer、Marketing Reviewer 和 Product Data Owner 已指定。
- Product 数据至少提供脱敏 DEV 样本。

### 3.2 外部依赖门禁

| 依赖 | 最晚门禁 | 未满足时处理 |
|---|---:|---|
| Product Data DEV 只读访问 | 2026-08-28 | 使用版本化 Fake Product fixtures，真实 RAG 验收保持阻断 |
| DeepSeek/企业 LLM 审批 | 2026-08-28 提交 | `mode: mock`，不得上传真实产品资料 |
| Embedding 服务 | 2026-09-04 | 使用确定性 Fake Embedding，禁止把它标记为质量验收 |
| 即梦区域、租户和官方 API | 2026-09-04 | `mode: mock`，不得使用非官方 Cookie/逆向接口 |
| SIT Credential 与 FQDN Allowlist | 2026-09-18 | Contract Test 可继续，SIT 真实路径阻断 |
| Medical Policy v1 | 2026-09-11 | 只允许生成草稿，不允许形成 APPROVED 内容包 |

## 4. 现有仓库复用

| 当前区域 | 本阶段用途 | 改造要求 |
|---|---|---|
| `src/data-processing/` | 文件安全校验、标准化和缺失值处理经验 | 提取通用验证规则；不直接用于批准 Product API |
| `src/analysis/` | 确定性指标和来源证据模式 | 复用“公式与证据分离”原则，不让 LLM 计算或覆盖精确值 |
| `src/domain/analysis.ts` | 来源引用和可靠性字段参考 | 映射到跨语言 JSON Schema，不复制冲突类型 |
| `src/domain/action-plan.ts` | 版本、引用、状态失效模式参考 | 新 Content Contract 使用独立版本 |
| `src/agents/` | 证据驱动输出和安全拒绝参考 | 移除 UI/内存耦合，迁入 Content Workflow 节点 |
| `src/tests/` | 回归和 fixture 组织方式 | 增加 Python/TypeScript Contract fixtures |

现有 LinkedIn 导出数据不是 Product 主数据，也不能作为 Medical Claim 的批准来源。

## 5. 目标代码结构

```text
agents/content/
  agent.yaml
  prompts/
    brief/
    copy/
    compliance_critic/
  workflows/
    content_mvp.py
  policies/
    tool-policy.yaml
    content-policy.yaml
  skills/
    brand-tone/
    medical-claims-policy/
    market-regulation-us/
    market-regulation-cn/
    linkedin-ad-spec/
    google-ads-spec/
packages/
  product-rag/
  compliance/
  domain-contracts/
  connector-sdk/
connectors/
  llm/deepseek/
  embedding/
  jimeng/
workers/
  content/
  connector/
apps/
  api/src/dmt_api/routes/content.py
  web/src/features/content/
tests/
  unit/content/
  contract/product/
  contract/deepseek/
  contract/jimeng/
  workflow/content/
  security/content/
evals/
  content/
  compliance/
  adversarial/
config/
  deepseek.yaml
  jimeng.yaml
```

## 6. 实现步骤

### 6.1 固定 Content 输入契约

新增 `content-request.v1.schema.json`，至少包含：

```text
request_id, product_ids, market, locale, target_audience,
target_channels, objective, campaign_context, user_prompt,
attachment_artifact_ids, requested_media_types, deadline,
tenant, business_unit
```

校验：

- `product_ids` 必须可映射到批准 Product 数据。
- `market`、`locale`、渠道和媒体类型使用枚举。
- 附件只接受允许的 MIME、大小和 Malware Scan 通过的对象存储 URI。
- Prompt 和附件全部视为不可信数据。
- Content Agent 不接收 Campaign Account、预算或写 Credential。

### 6.2 实现 Product Adapter

在 `packages/product-rag/adapters/` 定义：

- `get_product(product_id, version)`
- `list_approved_documents(product_id, market, locale, as_of)`
- `get_claims(product_id, market, locale, as_of)`
- `get_changes(cursor)`

每个 Product 文档必须带：

```text
source_id, source_version, product_id, market, locale,
approval_status, approved_by, effective_from, expires_at,
revoked_at, classification, content_hash, updated_at
```

行为：

- 只读 Service Identity。
- 默认只返回 `APPROVED`、未过期、未撤销记录。
- API 返回自由文本仍按不可信数据处理，只能作为数据，不能成为系统指令。
- 每次摄取记录 cursor、输入哈希、结果数量和失败明细。
- 删除/撤销事件必须使关联 Chunk 和索引条目不可召回。

### 6.3 实现批准 RAG

在 `packages/product-rag/` 分离：

- `ingestion/`
- `chunking/`
- `embedding/`
- `index/`
- `retrieval/`
- `citations/`

RAG 规则：

1. 摄取前验证批准状态、市场、语言、有效期、哈希。
2. Chunk 保存文档版本和字符/页码位置。
3. Embedding 保存模型、Deployment、维度和索引版本。
4. 查询必须过滤 tenant、product、market、locale、approval、validity。
5. 结果返回文本、来源、版本、位置、有效期和 hash。
6. 模型升级创建新索引版本，禁止原位混用不同向量。
7. DBA 批准后才可使用 PostgreSQL `pgvector`；否则使用企业批准向量服务。
8. 互联网内容、用户附件和 Memory 不得写入批准 Product 索引。

### 6.4 建立 Content Skill Registry

每个 Skill 必须包含：

```text
skill_id, version, owner, approved_by, effective_from,
expires_at, market, locale, classification, content_hash
```

加载规则：

- 按 Agent、市场、语言和渠道最小加载。
- 过期或撤销 Skill 阻断相关 Workflow。
- Prompt、Policy、Skill 和模型配置版本写入 Run。
- Skill 内容只读；Agent 不能在运行中修改。
- Medical Policy 更新触发受影响 Golden Set 回归。

### 6.5 实现 Content Workflow

在 `agents/content/workflows/content_mvp.py` 建立：

```text
ValidateInput
  -> RetrieveProductFacts
  -> BuildBrief
  -> GenerateCopy
  -> GenerateMedia
  -> ComplianceCheck
  -> HumanReview
  -> PackageApproved
```

失败/返工：

```text
ComplianceCheck -> Rework
HumanReview reject -> Rework
Rework fact_issue -> RetrieveProductFacts
Rework copy_issue -> GenerateCopy
Rework asset_issue -> GenerateMedia
```

规则：

- 每个节点输入/输出均用版本化 Schema。
- 每步写 Workflow Journal 和 Checkpoint。
- 拒绝必须包含 issue code、严重度、Reviewer comment 和目标返工节点。
- 返工只使下游相关节点失效，不盲目重跑全部 Workflow。
- `PackageApproved` 前执行独立 Goal Check，但 Goal Check 不能代替 Medical Reviewer。

### 6.6 实现 DeepSeek Connector

实现统一接口：

- `validate_config`
- `dry_run`
- `execute`
- `get_status`
- `reconcile`
- `cancel`（若 API 不支持则返回类型化 `NOT_SUPPORTED`）
- `normalize_error`

真实调用只存在于 `connectors/llm/deepseek/`，Agent 节点不得直接导入供应商 SDK。

在 Phase 2 编码时创建以下配置；本文模板是交付所需的完整占位模板：

```yaml
# config/deepseek.yaml
schema_version: "1.0"
provider: "deepseek"
enabled: false
mode: "mock" # mock | sandbox | live

endpoint: "${DEEPSEEK_API_ENDPOINT}"
api_path: "${DEEPSEEK_API_PATH}"

auth_method:
  type: "bearer"
  api_key_secret_ref_env: "DEEPSEEK_API_KEY_SECRET_REF"
  send_from_server_only: true

models:
  chat_model_env: "DEEPSEEK_CHAT_MODEL"
  temperature: 0.2
  max_output_tokens_env: "DEEPSEEK_MAX_OUTPUT_TOKENS"

timeouts:
  connect_ms: 3000
  request_ms: 60000
  total_workflow_ms: 90000

rate_limit:
  requests_per_minute_env: "DEEPSEEK_RPM"
  tokens_per_minute_env: "DEEPSEEK_TPM"
  max_concurrency_env: "DEEPSEEK_MAX_CONCURRENCY"
  local_queue: true
  fail_when_quota_unknown_in_live: true

retry_strategy:
  policy: "exponential_backoff_with_jitter"
  max_attempts: 4
  initial_delay_ms: 500
  max_delay_ms: 8000
  multiplier: 2.0
  honor_retry_after: true
  retry_http_statuses: [408, 429, 500, 502, 503, 504]
  do_not_retry_http_statuses: [400, 401, 403, 404, 409, 422]
  retry_requires_same_request_hash: true

network:
  proxy_url_env: "DMT_HTTPS_PROXY"
  allowed_fqdns_env: "DEEPSEEK_ALLOWED_FQDNS"
  direct_internet_egress_allowed: false
  tls_verify: true

cost_control:
  per_run_budget_env: "DEEPSEEK_PER_RUN_BUDGET"
  daily_budget_env: "DEEPSEEK_DAILY_BUDGET"
  stop_at_percent: 100
  alert_at_percent: 80

data_handling:
  allowed_classifications: ["internal", "confidential-approved-for-provider"]
  redact_pii: true
  log_request_body: false
  log_response_body: false
  record_prompt_version: true
  record_model_version: true

mock:
  fixture_dir: "tests/fixtures/deepseek"
  deterministic_seed: 20260907
  latency_ms: 50
  validate_request_schema: true
  fault_injection:
    enabled_env: "DEEPSEEK_MOCK_FAULTS_ENABLED"
    timeout_rate_env: "DEEPSEEK_MOCK_TIMEOUT_RATE"
    rate_limit_rate_env: "DEEPSEEK_MOCK_429_RATE"
    server_error_rate_env: "DEEPSEEK_MOCK_5XX_RATE"
```

配置约束：

- `mock` 是默认值。
- `sandbox/live` 启动时必须解析 endpoint、模型、Quota、Proxy、Allowlist 和 Secret Reference；缺失即失败。
- API Key 只从 Secret Manager 解析，不能存入 YAML、数据库、前端或日志。
- 正式启用前，Architecture/Security 必须对照 DeepSeek 官方文档核验 endpoint、模型、认证、数据保留、区域、训练政策和配额。
- 模型返回的引用不可信；引用只能由 RAG 层提供和校验。

### 6.7 实现即梦 Connector

即梦/Dreamina 的区域、租户、产品线和认证方式可能不同。只允许采购和 Security 确认的官方企业 API；禁止浏览器 Cookie、抓包 Token、逆向接口或第三方代理。

```yaml
# config/jimeng.yaml
schema_version: "1.0"
provider: "jimeng"
enabled: false
mode: "mock" # mock | sandbox | live

tenant:
  variant_env: "JIMENG_TENANT_VARIANT" # volcengine_cn | byteplus_global | approved_enterprise_gateway
  region_env: "JIMENG_REGION"
  project_env: "JIMENG_PROJECT_ID"

endpoint: "${JIMENG_API_ENDPOINT}"
operations:
  create_path_env: "JIMENG_CREATE_PATH"
  status_path_env: "JIMENG_STATUS_PATH"
  result_path_env: "JIMENG_RESULT_PATH"

auth_method:
  type_env: "JIMENG_AUTH_METHOD" # vendor_signed_request | bearer, must match issued official docs
  access_key_id_secret_ref_env: "JIMENG_ACCESS_KEY_ID_SECRET_REF"
  secret_access_key_secret_ref_env: "JIMENG_SECRET_ACCESS_KEY_SECRET_REF"
  bearer_token_secret_ref_env: "JIMENG_BEARER_TOKEN_SECRET_REF"
  session_token_secret_ref_env: "JIMENG_SESSION_TOKEN_SECRET_REF"
  send_from_server_only: true
  browser_cookie_auth_forbidden: true

model:
  model_id_env: "JIMENG_MODEL_ID"
  capability: "image_generation"
  output_formats: ["png", "jpeg", "webp"]
  max_images_per_request_env: "JIMENG_MAX_IMAGES_PER_REQUEST"

async_job:
  enabled: true
  poll_interval_ms: 3000
  max_poll_interval_ms: 15000
  max_duration_ms: 600000
  persist_job_id: true
  resume_after_worker_restart: true
  callback_webhook_enabled: false

timeouts:
  connect_ms: 3000
  create_request_ms: 30000
  status_request_ms: 15000
  download_ms: 60000

rate_limit:
  requests_per_minute_env: "JIMENG_RPM"
  jobs_per_day_env: "JIMENG_JOBS_PER_DAY"
  max_concurrency_env: "JIMENG_MAX_CONCURRENCY"
  local_queue: true
  fail_when_quota_unknown_in_live: true

retry_strategy:
  policy: "exponential_backoff_with_jitter"
  max_attempts: 5
  initial_delay_ms: 1000
  max_delay_ms: 30000
  multiplier: 2.0
  honor_retry_after: true
  retry_http_statuses: [408, 429, 500, 502, 503, 504]
  do_not_retry_http_statuses: [400, 401, 403, 404, 409, 422]
  reconcile_job_before_retry_create: true
  idempotency_key: "run_id_node_id_input_hash"

network:
  proxy_url_env: "DMT_HTTPS_PROXY"
  allowed_fqdns_env: "JIMENG_ALLOWED_FQDNS"
  direct_internet_egress_allowed: false
  tls_verify: true
  webhook_required: false

storage:
  import_result_to_object_store: true
  result_bucket_ref_env: "DMT_GENERATED_ASSET_BUCKET_REF"
  verify_mime: true
  malware_scan: true
  preserve_provider_response_hash: true
  provider_url_max_ttl_seconds: 900

cost_control:
  per_run_budget_env: "JIMENG_PER_RUN_BUDGET"
  daily_budget_env: "JIMENG_DAILY_BUDGET"
  max_assets_per_run_env: "JIMENG_MAX_ASSETS_PER_RUN"
  alert_at_percent: 80
  stop_at_percent: 100

data_handling:
  allowed_classifications: ["internal", "confidential-approved-for-provider"]
  redact_pii: true
  log_prompt: false
  log_result_url: false
  provider_training_opt_out_required: true
  retention_policy_must_be_approved: true

mock:
  fixture_dir: "tests/fixtures/jimeng"
  deterministic_seed: 20260907
  create_latency_ms: 50
  complete_after_polls: 2
  validate_request_schema: true
  generated_asset_fixture: "tests/fixtures/jimeng/generated/sample-approved.png"
  fault_injection:
    enabled_env: "JIMENG_MOCK_FAULTS_ENABLED"
    timeout_rate_env: "JIMENG_MOCK_TIMEOUT_RATE"
    rate_limit_rate_env: "JIMENG_MOCK_429_RATE"
    failed_job_rate_env: "JIMENG_MOCK_FAILED_JOB_RATE"
    malformed_result_rate_env: "JIMENG_MOCK_MALFORMED_RATE"
```

真实模式启用前必须确认：

1. API 的法定供应商、官方开发者门户和合同主体。
2. 中国区或国际区租户，不混用 endpoint、Credential 或配额。
3. 官方认证签名算法和 SDK。
4. 模型确实支持图片生成；视频模型不能伪装成图片能力。
5. 输入输出保留、训练、区域和跨境政策。
6. 创建、查询、取消和结果下载的正式 Contract。

### 6.8 实现 Content Brief 与文案生成

Content Brief 必须结构化：

```text
brief_id, product_id, market, locale, objective, audience,
approved_facts, prohibited_claims, required_disclosures,
brand_tone, channel_constraints, source_references,
prompt_version, skill_versions
```

生成要求：

- Prompt 只接收最小批准事实和政策。
- 每个 Claim 绑定来源 Chunk、文档版本、位置、市场和有效期。
- 无来源内容标记为未验证并阻断最终内容包。
- 不允许模型修改事实、引用、Policy 或审批状态。
- 渠道变体分别验证长度、格式和禁用表达。
- 所有输出先进入 `DRAFT`。

### 6.9 实现媒体生成

`media.create` 是 L2 Tool：

- 校验 DLP、Prompt、资产数量、尺寸、格式、费用和并发。
- 使用持久 Queue；创建后保存 provider job ID。
- Worker 重启后继续轮询。
- 下载结果后验证 MIME、大小、哈希和 Malware Scan。
- 转存对象存储，不依赖供应商临时 URL。
- 人工批准前只存于 `generated/`；批准后复制为新版本到 `approved/`。
- 修改 Prompt 或资产会使旧审批失效。

### 6.10 实现 Compliance

三层门：

1. **确定性规则**
   - 禁用词、必需披露、市场限制、长度、格式、过期 Claim。
2. **模型 Critic**
   - 识别潜在歧义、夸大、竞品比较和引用不一致。
   - 只能提出问题，不能覆盖规则结果。
3. **人工 Reviewer**
   - Medical Reviewer 处理 Medical Claims。
   - Marketing Reviewer 处理品牌和渠道适配。

结构化输出：

```text
compliance_result_id, content_version_id, policy_version,
issues[], severity, rule_id, claim_id, source_reference,
suggested_rework_node, automated_status, reviewer_status
```

Critical 问题、无来源 Claim、过期资料、恶意附件或 DLP 命中必须阻断。

### 6.11 实现 Review 与定点返工 UI

在 `apps/web/src/features/content/` 提供：

- Brief、文案、媒体和 Claim/Source 并排查看。
- Compliance 问题按严重度和节点分组。
- Approve、Reject、Request Changes。
- Reject 必填原因和目标节点。
- 显示 Prompt/Model/Skill/Policy/Content 版本。
- 显示审批失效原因。

前端只发送 Reviewer 决策；服务端重新验证角色、哈希、状态和职责分离。

### 6.12 生成不可变 `ApprovedContentPackage`

权威结构：

```json
{
  "schema_version": "1.0",
  "package_id": "acp_...",
  "version": 1,
  "status": "APPROVED",
  "product_id": "product_...",
  "market": "US",
  "locale": "en-US",
  "target_audience": ["..."],
  "channel_variants": {
    "linkedin": ["content_version_id"],
    "google_ads": ["content_version_id"]
  },
  "asset_uris": ["object://..."],
  "claims": [
    {
      "text": "...",
      "source_id": "...",
      "source_version": "...",
      "source_excerpt_hash": "sha256:..."
    }
  ],
  "compliance_result_id": "compliance_...",
  "approval_id": "approval_...",
  "approved_by": "employee_id",
  "approved_at": "ISO-8601",
  "expires_at": "ISO-8601",
  "content_hash": "sha256:..."
}
```

规则：

- 只有服务端 Package Builder 可创建 `APPROVED`。
- 内容、资产、Claim、引用、审批或版本任一变化都创建新版本。
- 旧版本保留审计，不原位修改。
- Package 过期、撤销或引用资料过期时禁止 Campaign 消费。
- Content Agent 不能读取 Campaign Account 或渠道写 Secret。

## 7. Mock / Stub 场景

### 7.1 DeepSeek fixtures

- 正常结构化响应。
- 无 Tool Use 的完整草稿。
- 超时、429、5xx。
- 非法 JSON、超出 Token、模型拒绝。
- Prompt Injection 文本被当作数据。
- 输出包含无来源 Claim。

### 7.2 即梦 fixtures

- 创建成功 -> 两次轮询 -> 完成。
- 创建超时但任务已存在，按 idempotency key 对账。
- 429 和指数退避。
- Job 失败、取消、过期。
- 结果 MIME 不匹配。
- 供应商临时 URL 过期。
- Malware Scan 失败。
- Worker 重启后继续轮询。

### 7.3 Product fixtures

- 正常批准 Claim。
- 过期、撤销、跨市场、跨语言。
- 缺少版本或批准人。
- 相同 ID 不同 hash。
- 增量 cursor 重放。
- Product API 返回恶意指令文本。

## 8. 测试策略

### 8.1 Unit

- Product 状态和有效期过滤。
- Chunk 来源位置。
- Claim 与引用绑定。
- Skill 选择和过期。
- Compliance 严重度和阻断。
- 定点返工节点选择。
- Package hash 和版本。
- DeepSeek/即梦配置 Schema 与错误标准化。

### 8.2 Contract

- Product API。
- DeepSeek 正常/错误响应。
- 即梦创建/查询/失败/结果。
- Embedding 维度和索引版本。
- Object Store 与 Malware Scan。

### 8.3 Workflow

- 正常批准。
- Compliance 拒绝 -> 指定节点返工。
- Human Reject -> 指定节点返工。
- 审批过期。
- Worker 重启。
- 取消。
- Provider 超时和恢复。

### 8.4 Eval / Security

- 无来源诱导 Prompt。
- Medical 禁用表达。
- 竞品比较。
- 跨市场 Claim。
- 恶意附件、SSRF URL、超大文件、伪造 MIME。
- Product API 文本中的 Prompt Injection。
- Tool 参数越权。
- Secret、PII 和供应商 Token 泄漏。

## 9. 验收标准

### 9.1 功能

- [ ] 用户可提交 Product、市场、语言、受众、目标渠道和内容目标。
- [ ] Content Workflow 可暂停、恢复、取消和定点返工。
- [ ] DeepSeek 与即梦默认使用确定性 Mock。
- [ ] 真实 Provider 未获批或配置不完整时启动失败，而不是静默退回 Mock。
- [ ] Reviewer 可查看内容、Claim、来源、Policy 和版本。
- [ ] 只有合法 Medical/Marketing 决策可形成 `APPROVED` Package。

### 9.2 质量门槛

- [ ] 最终 Claim 来源覆盖率：100%。
- [ ] Golden Set 中 Critical 未批准 Claim 逃逸：0。
- [ ] 已过期或撤销资料进入最终内容包：0。
- [ ] 无审批或哈希不匹配内容包：0。
- [ ] 所有内容包具有内容哈希、审批、版本和有效期：100%。
- [ ] 人工拒绝后只返工指定节点：100%。
- [ ] Critical Compliance 召回率：100%。
- [ ] 总体 Compliance 召回目标由 Medical Owner 签字；建议不低于 95%。

### 9.3 可靠性与安全

- [ ] DeepSeek/即梦 429、超时、5xx 均有有界重试和 Trace。
- [ ] 媒体创建超时先对账，不重复创建 Job。
- [ ] Worker 重启后媒体任务恢复。
- [ ] 所有媒体结果进入对象存储并完成类型、哈希和 Malware Scan。
- [ ] Prompt、日志、Trace、数据库和 UI 中不出现真实 Secret。
- [ ] Content Agent 无 Campaign 写 Tool、预算和渠道 Credential。

### 9.4 可演示里程碑

演示场景：

1. 使用批准 Product fixture 创建任务。
2. 生成带引用的 Brief、文案和图片。
3. Compliance 对禁用表达给出 Critical 问题。
4. Reviewer 指定 `GenerateCopy` 返工。
5. 只重跑文案及其下游节点。
6. Medical 和 Marketing 合法审批。
7. 输出不可变 `ApprovedContentPackage`。
8. 修改任一字段后证明旧审批失效并创建新版本。

## 10. 验证命令

Phase 01 创建相应脚本后执行：

```powershell
npm test
npm run lint
npm run typecheck
npm run build
python -m pytest tests\unit\content tests\contract\product tests\contract\deepseek tests\contract\jimeng
python -m pytest tests\workflow\content tests\security\content
```

CI 还必须运行最小 Content Eval Smoke。不得用 Mock 测试通过替代真实 DEV/SIT Credential 验收。

## 11. 时间估算与里程碑

建议投入：约 15 个工程工作日；Product/RAG、Content Workflow、Connector 和 Review UI 可并行，但共享 Contract 变更必须串行审查。

| 日期 | 里程碑 |
|---|---|
| 2026-09-07 | Content Contract、Product Contract、Golden fixtures 冻结 |
| 2026-09-11 | Fake Product RAG、Skill Registry、DeepSeek Stub |
| 2026-09-16 | Content Brief/Copy Workflow、引用与 Compliance 初版 |
| 2026-09-18 | 即梦 Stub、异步媒体恢复；SIT Credential/FQDN 门禁 |
| 2026-09-22 | Review/Rework UI、审批和不可变 Package |
| 2026-09-25 | Golden/Adversarial Eval、阶段演示和退出评审 |

## 12. 风险、缓解与注意事项

| 风险 | 影响 | 缓解 | Owner |
|---|---|---|---|
| Product 数据无批准/版本 | RAG 不可用于合规 | 建批准视图；无批准状态只允许草稿 | Product Data Owner |
| DeepSeek 未获企业批准 | 无真实 LLM | 保持 Stub；不得上传真实资料 | Architecture / Security |
| 即梦身份或区域不明确 | 误接非官方 API | 只接受合同和官方文档；Cookie/逆向接口禁止 | Procurement / Security |
| 即梦只提供视频模型 | 无图片能力 | 更换批准图片模型或降低首发范围 | Product Owner |
| Medical 规则过度依赖模型 | 合规逃逸 | 确定性规则、引用、Critic、人工四层证据 | Medical Owner |
| RAG 跨市场召回 | 错误 Claim | 强制 tenant/product/market/locale/validity filter | Agent Engineer |
| 媒体长任务积压 | SLA/费用失控 | 独立 Queue、并发/预算上限、取消和 DLQ | SRE |
| 返工导致全流程重跑 | 时间和费用增加 | 问题绑定节点，只使相关下游失效 | Backend |
| Prompt Injection | 越权或污染事实 | 数据/指令隔离、Tool Schema、DLP、无任意 URL | Security |

## 13. Coding Agent 执行纪律

每个实现任务必须写明：

```text
目标 -> 受影响文件 -> 先失败的测试 -> 最小实现
-> 目标测试 -> 受影响测试/类型/构建 -> 规格审查 -> 影响面审查
```

额外规则：

- 不为 P1 渠道或第二媒体供应商提前建实现。
- 不在 Agent 节点直接调用供应商 SDK。
- 不用宽泛 `try/except` 吞掉供应商错误；统一 `ConnectorError` 分类。
- 不用“生成成功”的自然语言代替结构化产物和测试证据。
- 任何 Policy、Prompt、Skill、模型和 Schema 变更都版本化并触发相应 Eval。
- 对 `domain-contracts`、Migration、Tool Policy 和 Package Builder 做双人审查。

## 14. AI 输出质量 Checkpoints

### 14.1 判定与评分规则

- 每个 Checkpoint 先执行确定性硬门，再由独立 Evaluator 按冻结 Rubric 评分，最后由指定业务角色复核。
- AI 自评、Critic 或 Goal Check 只能提出问题，不能覆盖 Product 状态、确定性 Compliance 规则或人工批准。
- 结果使用 `PASS / FAIL / BLOCKED`；缺数据、外部 API 未批准或 Reviewer 缺席必须为 `BLOCKED`。
- Producer 和 Evaluator 不共享上下文、Memory 和 Tool Set；Evaluator 只读取产物、批准来源、Rubric 和 Evidence Reference。
- 软维度 0–4 分，默认加权平均 >= 3.4 且单项 >= 3；事实、引用、安全和审批属于硬门，不以平均分抵消。
- Checkpoint 结果保存 artifact/hash、Prompt/Model/Skill/Policy/Rubric/Dataset 版本、分项分数、违规项、Reviewer 和证据，不保存 Chain-of-Thought。

### 14.2 阶段 Checkpoint 矩阵

| ID | 触发时点与 AI 输出 | 质量维度与硬门 | PASS 阈值 | Owner / 证据 | FAIL 后定点返工 |
|---|---|---|---|---|---|
| P2-CP01 | `RetrieveProductFacts` 后的检索结果 | 来源批准状态、版本、市场、语言、有效期、相关性、跨 Tenant 隔离 | 不合格/过期/撤销来源 0；引用定位和 hash 完整率 100%；Golden Source Recall@k >= 95% | Product Data Owner；Retrieval Report、Source IDs、Index Version | 返回摄取、过滤或检索节点；不得继续生成 |
| P2-CP02 | `BuildBrief` 和 `GenerateCopy` 后 | 事实一致性、Claim Grounding、需求覆盖、品牌语气、渠道规格、语言质量、无虚构数字 | Claim 来源覆盖率 100%；事实错误 0；无依据数字 0；渠道硬规则 100% 通过；软评分 >= 3.4 | Marketing + Medical 抽样复核；Brief/Copy、引用、Rubric | 事实问题回 `RetrieveProductFacts`；文案问题回 `GenerateCopy` |
| P2-CP03 | `GenerateMedia` 后 | Prompt/产品相关性、品牌一致性、敏感数据、禁用视觉、MIME/尺寸、生成缺陷、可访问性 | DLP/Malware/禁用视觉命中 0；技术规格 100% 通过；相关性和品牌软评分 >= 3.4 | Marketing + Security；Asset hash、Scan、缩略图和 Provider Job | 返回 `GenerateMedia`；旧资产不可原位覆盖 |
| P2-CP04 | `ComplianceCheck` 后 | Medical/市场规则、Claim-Source 一致、披露、Critical 召回、误报及建议返工节点 | Critical Recall 100%；总体 Recall >= 95%；Critical 逃逸 0；建议节点正确率 >= 95% | Medical Owner；Golden/Adversarial confusion matrix、Rule IDs | 返回规则/Skill/Critic；禁止 Critic 将规则失败改为通过 |
| P2-CP05 | `HumanReview` 前 | 面向 Reviewer 的解释是否完整、证据是否可读、风险是否准确校准、未确定项是否明确 | 必需字段和来源展示 100%；把推测写成事实 0；软评分 >= 3.4 | Medical + Marketing；Review Snapshot、Trace | 返回对应 Brief/Copy/Media/Compliance 节点 |
| P2-CP06 | `PackageApproved` 前 | Package Schema、内容/资产 hash、引用、审批、版本、有效期和渠道变体 | Schema/Hash/Approval 100% 通过；未批准或过期产物 0；修改后旧审批失效 100% | Package Builder 硬门 + Medical/Marketing 签字；Package/Approval/Audit | 阻断 Package；返回具体失败节点重新审批 |

### 14.3 Eval Set 与抽样

- Golden Set 至少覆盖正常、过期、撤销、跨市场、跨语言、禁用表达、竞品比较、无来源诱导、模型拒绝和供应商超时。
- 每次 Prompt/Model/Skill/Policy 变更运行完整受影响 Eval；普通代码 PR 至少运行 Smoke + 所有硬门。
- 首次基线和阶段退出由 Medical/Marketing 复核全部 Critical 样本，并分层抽样至少 30 个非 Critical 输出。
- AI Evaluator 与人工评分差异超过 1 分、事实结论不一致或 Reviewer 拒绝时，一律人工裁决并更新 Rubric/fixture，而不是调低阈值。
- 记录返工次数；同一 Checkpoint 连续失败 3 次后停止自动重试，转人工诊断。

## 15. 阶段退出条件

只有同时满足以下条件，`ApprovedContentPackage` 才可交给 Phase 03：

1. Product 数据来源已批准、版本化、可撤销且查询可追溯。
2. Golden Set 和 Adversarial Set 达到质量门槛。
3. Medical 与 Marketing Reviewer 角色、职责分离和审计有效。
4. Content Package 不可原位修改，变更会生成新版本并重新审批。
5. DeepSeek/即梦 Stub 的正常、限流、超时、失败和恢复 Contract Test 通过。
6. 真实 API 未获批时仍保持禁用，且不存在成功形状的静默回退。
7. Package Schema、hash、审批和有效期可被 Campaign Agent 独立验证。
8. P2-CP01 至 P2-CP06 全部 `PASS`，对应 Checkpoint Result、数据集和 Rubric 可复验。
