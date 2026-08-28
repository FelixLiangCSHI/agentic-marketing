# Phase 03：Campaign Agent 与渠道集成

> 计划窗口：2026-09-14 至 2026-10-02  
> 路线图映射：Campaign Agent MVP（MA-01 至 MA-08）  
> 本阶段目标：在共享 Harness、审批、审计、队列和契约冻结后，实现 LinkedIn Advertising 与 Google Ads 的草稿、Dry-run、审批发布、状态对账、指标读取、报告和策略草稿。  
> 生产原则：默认 `mock`；真实渠道仅允许经批准的测试账户和显式 Feature Flag；无公网入站、无供应商 Webhook。  
> 执行模式：**Repo-first Hybrid**；Connector/Policy/Mock 在 GitHub 优化，OAuth 和渠道测试账户写入必须在受保护 DEV/SIT 远端执行

## 1. 阶段目标

1. 只消费状态为 `APPROVED` 且未过期的 `ApprovedContentPackage`，构造可审阅的渠道化 `CampaignProposal`。
2. 对 LinkedIn 和 Google Ads 分别执行账户、预算、币种、地区、时间、受众、素材规格和渠道 Policy 的 Dry-run，不产生外部副作用。
3. 建立统一的 `ActivationRequest` v1、Connector SDK 和 `ConnectorError` v1；Connector 隔离第三方 SDK、认证、限流、重试和供应商字段。
4. 对所有外部写入强制执行：人工审批、审批令牌、输入哈希、幂等键、审计；任何超时或不确定结果都必须先对账再重试。
5. 以供应商原始指标不可变存储，以独立归一化模型计算跨渠道指标，保证原始数据不被模型或归一化过程覆盖。
6. 生成 `PerformanceReport` 和 `StrategyRecommendation`/策略草稿；策略只可进入新的审批流程，不得直接修改、暂停、删除或扩大生产 Campaign。
7. 在 LinkedIn Test Account 和 Google Ads Test Account 完成端到端发布、读取、故障注入、重复投递和恢复测试；真实凭据不进入仓库、日志、Trace 或测试夹具。

## 2. 前置条件与阻断门

Phase 03 开始前，Phase 01 的退出条件必须全部满足：

- `ApprovedContentPackage`、`ActivationRequest` 和 `ConnectorError` v1 Schema 已冻结，Python 与 TypeScript 共享 Golden/Invalid fixtures。
- Fake 双 Agent 已验证暂停、审批、恢复、拒绝、取消、Worker 重启恢复和重复消息无副作用。
- L3 Tool 无有效审批时拒绝率为 100%；审批记录支持原子消费、撤销、过期和输入哈希绑定。
- DEV/SIT/UAT/PRD 配置、Secret Namespace、Proxy/NAT、Queue/DLQ、Object Store、审计和监控均有 Owner、工单号和目标日期。
- `APPROVED` 内容包包含内容哈希、批准人、批准时间、过期时间、市场/语言和渠道变体。
- LinkedIn Marketing API 申请已提交并获得 Development Access/测试广告账户；Google Ads Developer Token、Manager Account、测试 Manager/Customer Account 和 Google Cloud Project 已申请。
- 已确认企业内部 HTTPS OAuth Redirect、OAuth Broker 或受控管理员授权方案；没有把公网 Callback 当作默认方案。
- 完成供应商官方文档、账号权限、数据驻留、出站 FQDN、Quota 和生产准入级别的核验记录。缺少任何一项时保持 `mode: mock`，不得用猜测值上线。

以下任一项未完成，阶段仍可开发 Fake Connector 和契约测试，但不得启用 `sandbox`/`live`：

| 阻断项 | 处理 |
|---|---|
| API 申请、测试账户或权限未获批 | 仅运行 deterministic mock |
| Redirect URI 未得到供应商和 IAM 确认 | 不执行真实 OAuth |
| Proxy/NAT、FQDN Allowlist 或 Secret Manager 未就绪 | 不访问外部 API |
| 官方文档无法确认某个 endpoint、字段、版本或配额 | 配置标记 `verification: blocked`，不得实现猜测的调用 |
| 内容包过期、撤销、哈希不匹配或渠道变体缺失 | 阻断 Draft/Publish，返回可审计的结构化错误 |

## 3. Scope / Non-scope

### 3.1 Scope

- Campaign Agent 的输入校验、Draft、渠道映射、Dry-run、Campaign Approval UI/API、发布 Worker、重试、对账和补偿。
- LinkedIn **Advertising API**：Campaign Management、Ads Reporting；按官方要求使用 REST API 和成员 3-legged OAuth。
- Google Ads API：Campaign/必要层级的创建与查询、GAQL 报告；使用官方 endpoint 和 Developer Token。
- 账户、预算、币种、时区、日期、地区/受众约束、素材规格和渠道 Policy 的结构化校验。
- 原始指标落库、跨渠道归一化、趋势/效率计算、报告导出和只读策略草稿。
- Fake Connector、确定性 mock fixtures、限流/超时/Token 过期/外部已创建等故障注入。
- API、Worker、Schema、Migration、审计、Trace、指标、Runbook 和量化验收证据。

### 3.2 Non-scope

- 自动提高预算、扩大受众、修改竞价、删除、暂停或恢复生产 Campaign；这些动作属于 L4，MVP 始终拒绝。
- Meta、Instagram、YouTube、邮件、LinkedIn Page 有机发布、Lead Sync、Conversions、Matched Audiences。
- 供应商 Webhook、公网入站、CDN、任意 URL Fetch；状态和指标只使用 HTTPS 出站轮询。
- Buffer 或任何社交排程供应商的生产 Connector；现有 Buffer 相关导出/交接仅作为非 MVP 原型参考。
- 将旧的本地 UI/桥接或内存状态当作生产 API、Worker、Approval 或 Connector。
- 自动将策略建议写回渠道；Email/Social 只生成草稿，不发送。
- 新增第二套 Workflow Runtime、通用 Shell、原始 SQL Tool 或让 Agent 直接调用第三方 SDK。

### 3.3 GitHub Repo 与远端环境分工

| 位置 | 本阶段任务 | 关键限制 | 完成证据 |
|---|---|---|---|
| GitHub PR/普通 CI | `ActivationRequest`、Campaign Draft、Dry-run、Policy、Connector SDK、Mock LinkedIn/Google、幂等/对账、Raw/Normalized Metrics | 只用确定性 fixture；无真实 OAuth；不得产生外部写 | Unit/Contract/Workflow/重复投递报告 |
| 共享 DEV | OAuth POC、Proxy/FQDN、Development Credential、测试 Manager/Ad Account、只读/最小写入验证 | 专用测试账户和硬预算；人工批准；Secret Manager | OAuth、Dry-run、Publish/Reconcile Trace |
| SIT | 双渠道完整发布、状态/指标轮询、429/超时/Token 到期/后台修改 | SIT Credential 与 Queue 隔离；所有写入带 Approval/Hash/Idempotency | 外部 Object ID、Audit、Metrics 和清理记录 |

执行边界：

- GitHub 最适合优化 Mapper、Policy、错误分类、幂等、对账、报告和 Strategy 质量；这些应通过 Mock/Contract 先收敛。
- LinkedIn 3-legged OAuth、Google Ads Developer Token、真实 Quota 和测试账户发布无法只在 Repo 验收，必须走企业网络内的受保护 Runner。
- 普通 PR Workflow 不授予 OAuth Refresh Token、Developer Token 或渠道写权限；只有受保护 Environment、批准 Tag 和人工审批可运行真实 Connector Job。
- OAuth 初始用户授权可能通过内部浏览器 Redirect/OAuth Broker 完成，但 Token 只进入远端 Secret Manager，不回写 GitHub。
- 远端发现 Schema/版本差异后，应更新 Repo 的 Adapter、Contract fixture 和官方核验记录，再重新部署；禁止在远端热补丁。

## 4. 当前仓库复用与迁移边界

当前仓库的 LinkedIn 解析/分析契约和确定性分析实现是**离线原型资产**，可用于字段语义、别名、缺失值与 `0` 的区别、指标公式和回归 fixtures；它们不是在线 Marketing API Connector，也不能作为外部发布证明：

| 现有资产 | Phase 03 用法 | 禁止事项 |
|---|---|---|
| `src/domain/linkedin.ts` | 提取字段名、渠道维度和兼容映射，新增 v1 契约前先写兼容测试 | 不把其类型直接当作供应商写 API 请求 |
| `src/analysis/metric-catalog.ts` | 复用指标定义/标签，映射到 raw metric 名称 | 不覆盖原始供应商值，不把缺失值当 `0` |
| `src/analysis/metrics-engine.ts`、`src/analysis/snapshot-engine.ts` | 复用确定性计算和快照测试；由 Adapter 转换为统一 read model | 不让模型输出修改计算结果 |
| `src/analysis/quality-engine.ts` | 复用数据质量规则和错误分类 | 不把质量警告静默为成功 |
| `src/data-processing/field-aliases.ts`、`normalizers.ts` | 复用离线列名/格式归一化的可解释规则 | 不用于猜测供应商 API 版本或字段 |
| `src/tests/analysis-*`、`src/tests/normalization-quality.test.ts`、`src/tests/parser-formats.test.ts` | 作为回归基线和 Golden 数据来源 | 不删改无关既有测试 |
| `src/exports/report-exports.ts` | 参考报告导出字段和稳定排序 | 不输出 Secret、原始 Token 或未授权数据 |
| `src/domain/buffer-handoff.ts`、`src/exports/buffer-export.ts` | 仅保留历史交接的字段语义，标记 Buffer 为 non-MVP | 不新增 Buffer Connector、OAuth 或发布路径 |

复用方式为“先测量、再提取、再兼容”：生产契约放入 `packages/domain-contracts`，旧 TypeScript 原型通过兼容层读取；不要一次性移动或重写现有目录。只修改本阶段所需文件，用户删除的文件不恢复。

## 5. 目标目录与模块责任

以下是必须落地或明确占位的精确路径（不存在时按 Phase 01 的 Monorepo 约定创建）：

```text
agents/campaign/
  agent.yaml                         # Agent 身份、工具白名单、工作流版本
  prompts/campaign-draft.md          # 仅生成结构化草稿，不含 Secret
  prompts/performance-report.md
  prompts/strategy-draft.md
  workflows/campaign_activation.py   # Validate -> Draft -> Dry-run -> Approval -> Activate -> Reconcile -> Metrics -> Report
  policies/campaign-policy.yaml      # 预算、市场、L3/L4、过期和数据边界
  skills/channel-mapping.yaml

packages/domain-contracts/schemas/
  activation-request.v1.schema.json
  campaign-proposal.v1.schema.json
  campaign-dry-run.v1.schema.json
  performance-report.v1.schema.json
  strategy-recommendation.v1.schema.json
  connector-error.v1.schema.json
packages/connector-sdk/
  src/connector.py
  src/models.py
  src/errors.py
  tests/test_connector_contract.py
packages/approval/src/service.py
packages/audit/src/events.py

connectors/linkedin/
  src/connector.py
  src/auth.py
  src/mappers.py
  src/metrics.py
  tests/test_contract.py
  fixtures/mock_success.yaml
  fixtures/mock_faults.yaml
connectors/google_ads/
  src/connector.py
  src/auth.py
  src/mappers.py
  src/metrics.py
  tests/test_contract.py
  fixtures/mock_success.yaml
  fixtures/mock_faults.yaml

apps/api/src/dmt_api/routes/campaigns.py
apps/api/src/dmt_api/services/campaign_service.py
apps/api/src/dmt_api/services/reconciliation_service.py
workers/campaign/src/worker.py
workers/connector/src/dispatcher.py

config/linkedin.yaml
config/google_ads.yaml
tests/unit/campaign/
tests/contract/connectors/
tests/workflow/campaign/
tests/integration/connectors/
tests/security/campaign/
tests/performance/campaign/
evals/campaign/
docs/runbooks/campaign-reconciliation.md
docs/runbooks/channel-token-rotation.md
```

职责边界：

- Agent 只调用注册的 `campaign.draft`、`campaign.validate`、`campaign.publish`、`metrics.read`；不得导入供应商 SDK。
- Connector 负责 endpoint、API 版本、认证、请求/响应映射、限流、重试、错误规范化、状态查询和对账。
- API 负责鉴权、Schema、审批请求和查询；Worker 负责带租约的异步执行；Approval/Audit 负责不可变证据。
- `packages/harness-core` 不放渠道 Prompt、SDK、Secret 或供应商字段。

## 6. 实现步骤：运行时流程与数据契约

### 6.1 Run 和状态

Campaign Run 沿用 Phase 01 的统一 Run Contract 和状态机；每次状态变化追加 `run_events`，并携带 `trace_id`、`run_id`、`task_id`、`agent_type`、`workflow_version`、`tool_call_id`、`approval_id`、`content_package_id`、`campaign_id`、`external_object_id`、`policy_version`。

业务节点必须按以下顺序执行：

```text
ValidateApprovedPackage
  -> BuildCampaignDraft
  -> ChannelDryRun
  -> WAITING_APPROVAL
  -> ConsumeApprovalToken
  -> Activate
  -> ReconcileExternalState
  -> CollectMetrics
  -> AnalyzePerformance
  -> RecommendStrategy
  -> DraftEmailAndSocial
```

拒绝只回到指定 Draft 节点；取消、过期、不可恢复错误和补偿均要保留原始事件。任何外部写入前必须完成 PreToolUse Policy、Approval、哈希和幂等校验。

### 6.2 `ActivationRequest` v1

Schema 文件为 `packages/domain-contracts/schemas/activation-request.v1.schema.json`。最小结构如下；实际 JSON Schema 必须限制枚举、格式、长度、数值边界和禁止未知字段：

```json
{
  "schema_version": "1.0",
  "request_id": "act_<stable-id>",
  "run_id": "run_<id>",
  "tenant": "tenant_<id>",
  "requester_id": "employee_<id>",
  "content_package_id": "acp_<id>",
  "content_package_hash": "sha256:<hex>",
  "channel": "linkedin",
  "account_id": "internal-account-id",
  "objective": "LEAD_GENERATION",
  "campaign_name": "approved-name",
  "budget": {
    "currency": "USD",
    "total_limit": 1000.0,
    "daily_limit": 100.0
  },
  "schedule": {
    "timezone": "America/New_York",
    "start_at": "2026-09-21T00:00:00Z",
    "end_at": "2026-10-02T23:59:59Z"
  },
  "audience_constraints": {
    "markets": ["US"],
    "age_min": null,
    "age_max": null,
    "excluded_segments": []
  },
  "channel_settings": {},
  "policy_version": "campaign-policy-1",
  "approval_id": "approval_<id>",
  "approval_token": "approval-token-reference-only",
  "input_hash": "sha256:<canonical-request-and-content-hex>",
  "idempotency_key": "tenant_<id>:linkedin:<request-id>:v1"
}
```

规则：

1. `content_package_hash` 必须与数据库中不可变的 `ApprovedContentPackage.content_hash` 相等，包必须是 `APPROVED`、未过期且包含目标渠道变体。
2. `input_hash` 对规范化的内容包哈希、账户、渠道、预算、排期、受众、素材哈希、Policy/Workflow 版本计算；字段任何变化都生成新 Request 并使旧 Approval 失效。
3. `approval_token` 只保存引用/opaque token，不在日志和模型上下文暴露 token 值；令牌必须绑定 requester、approver、角色、范围、输入哈希和过期时间。
4. `account_id` 是内部账户标识或 Secret Reference，不是 Access Token；数据库不得保存供应商 Refresh Token 明文。
5. 金额用 Decimal/最小货币单位计算，拒绝 NaN、负数、超租户/环境上限和不支持的币种。
6. Campaign 发布、修改、暂停、删除等写意图全部走此类审批链；MVP 的 L4 修改一律拒绝。

### 6.3 Connector 接口

`packages/connector-sdk/src/connector.py` 定义同步语义（实现可在 Worker 中异步调用）：

```python
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

@dataclass(frozen=True)
class DryRunResult:
    valid: bool
    normalized_request: Mapping[str, Any]
    warnings: Sequence[str]
    errors: Sequence[Mapping[str, Any]]
    request_fingerprint: str

@dataclass(frozen=True)
class ExternalWriteResult:
    outcome: str  # CREATED | ALREADY_EXISTS | ACCEPTED | UNKNOWN
    external_object_id: str | None
    operation_id: str | None
    raw_response_ref: str | None

class Connector(Protocol):
    name: str
    api_version: str

    def validate_config(self) -> None: ...
    def health_check(self) -> Mapping[str, Any]: ...
    def dry_run(self, request: Mapping[str, Any]) -> DryRunResult: ...
    def execute(self, request: Mapping[str, Any],
                *, approval_token_ref: str, input_hash: str,
                idempotency_key: str) -> ExternalWriteResult: ...
    def get_status(self, *, external_object_id: str | None,
                  idempotency_key: str) -> Mapping[str, Any]: ...
    def reconcile(self, *, request: Mapping[str, Any],
                  idempotency_key: str,
                  external_object_id: str | None = None) -> Mapping[str, Any]: ...
    def collect_metrics(self, *, account_id: str,
                        external_object_id: str,
                        window: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]: ...
    def normalize_error(self, error: Exception) -> Mapping[str, Any]: ...
    def cancel(self, *, external_object_id: str,
               idempotency_key: str) -> Mapping[str, Any]: ...
```

`cancel` 仅在供应商支持且 Runbook 明确允许时实现；不得用它绕过审批。所有 Connector 还必须：

- 仅从 `SecretResolver`、`Clock`、`HttpClient`、`ProxyPolicy` 取得依赖；
- 在请求中带 trace/idempotency 关联信息（供应商支持的 header 才可发送）；
- 将响应原文写入受控 Object Store 引用，数据库只存 URI、摘要哈希和结构化字段；
- 将 4xx 权限/Schema、429 限流、5xx/网络、超时、认证过期分别映射为 `ConnectorError`，标记 `retryable` 和 `reconcile_required`；
- 不把供应商错误正文、Token、Authorization header 放进 Agent 消息、异常响应或日志。

## 7. Campaign Draft 与 Dry-run

### 7.1 Draft

`BuildCampaignDraft` 是 L1、无外部副作用。输入为已批准内容包、目标、预算上限、时间窗口、市场/受众约束和渠道配置，输出 `CampaignProposal`：

- `proposal_id`、`schema_version`、`content_package_hash`、`input_hash`；
- `channel`、内部 `account_id`、objective、campaign/ad-group/ad 结构；
- 预算、币种、时区、开始/结束时间、受众表达式；
- 渠道化文案和素材 URI/哈希（不复制完整敏感资产）；
- 预估成本、已知限制、warnings、Policy/Prompt/Skill/Workflow 版本；
- `status: DRAFT`，创建者和时间。

Draft 必须确定性排序；相同输入、配置版本和 Fake Clock 产生相同 `proposal_id`/`input_hash`。人工修改预算或受众后重新计算哈希并重新 Dry-run，不覆盖旧版本。

### 7.2 Dry-run

`ChannelDryRun` 通过 Connector 做本地 Schema/Policy 校验；如官方 API 提供无副作用 validate/preview，可在 sandbox 使用，但禁止把“请求被接受”当作已发布。必须检查：

- 账户存在、环境与账户类型匹配、Connector auth 可用；
- objective、Campaign 层级和渠道字段映射；
- currency、金额精度、每日/总预算和租户/环境上限；
- 时区、开始/结束时间、最小/最大时长；
- 地区、排除受众、敏感或禁止定向；
- 文案长度、字符集、CTA、素材 MIME/像素/文件大小/宽高比；
- 官方当前 Policy、权限、API version 和配置中的已核验 quota；
- 幂等键格式、审批范围和 `input_hash`。

任何错误均返回结构化 `campaign-dry-run.v1`，不能部分发布。Dry-run 通过只代表可申请审批，不代表可写。

## 8. 审批、幂等、对账与补偿

### 8.1 审批令牌

- Draft 和 Dry-run 完成后创建 `CAMPAIGN_ACTIVATION` Approval；绑定 Requester、Campaign Approver、角色、渠道、账户、预算、排期、受众、内容包哈希、`input_hash`、Policy/Workflow 版本和过期时间。
- 发起人不得批准自己的高风险请求；Medical Reviewer 与 Campaign Approver 必须分离。
- 令牌单次使用，数据库以条件更新/唯一约束原子消费；消费失败不得调用外部写 API。
- 任何内容、账户、预算、时间、受众、配置版本或哈希变化都使令牌失效；过期/撤销/已用令牌 100% 拒绝。
- Audit 写入失败时 L3 Tool fail closed；审批决定、Token 消费、Connector 调用和外部 ID 必须可追溯。

### 8.2 幂等写入

先在 `connector_operations` 建立唯一记录：

```text
(tenant, channel, account_id, idempotency_key, input_hash)
```

同一键只允许一个逻辑写操作；Worker 重试读取该记录和 `external_object_id`。若相同键但 `input_hash` 不同，拒绝并告警，不覆盖旧操作。幂等键应由稳定业务 ID、渠道和 Request 版本组成，不使用时间戳或随机值作为唯一防重依据。

### 8.3 Reconcile-before-retry

外部请求返回超时、连接断开、5xx、Worker 崩溃或状态 `UNKNOWN` 时：

1. 将操作标为 `UNKNOWN`，停止盲目重试。
2. 使用供应商可查询的 operation/object ID、请求指纹、名称/时间窗口和内部幂等键对账；只使用允许的精确查询，禁止宽泛搜索造成误认。
3. 找到唯一对象则记录 `external_object_id`、状态和原始响应引用，转 `RECONCILED`/继续收集状态。
4. 明确确认未创建后，按配置的退避和最大次数重试同一幂等键。
5. 仍无法判定则进入人工队列/DLQ，不创建第二个对象。

所有状态查询必须可重入；不把网络超时直接标为失败，更不允许凭“看起来没有”重复创建。

### 8.4 补偿

补偿是针对已确认副作用的最小化收敛，不是隐式回滚：

- 部分层级成功：记录每个外部 ID，停止后续写入，优先调用供应商支持的撤销/删除草稿能力；生产删除/暂停为 L4，MVP 不自动执行。
- 内容包在发布后被撤销/过期：标记 Run 风险，停止后续操作，生成人工 Runbook 任务，不自动修改生产对象。
- 本地 DB 写入失败但外部已成功：通过 Outbox/对账任务补齐审计和对象映射；禁止再次创建。
- 补偿本身同样需要审批（如属于 L3/L4）、输入哈希、幂等键和完整审计。
- `COMPENSATING` 只能转为 `COMPENSATED`、`FAILED` 或 `WAITING_APPROVAL`，不得静默吞错。

## 9. LinkedIn Advertising Connector

### 9.1 固定约束

- 使用官方 LinkedIn REST API 基础地址（配置模板中的 `https://api.linkedin.com`），资源路径和 API 版本必须由 `config/linkedin.yaml` 注入；代码不得硬编码会过期的 `v2`、`v2024...` 等 transient 版本。
- Marketing APIs 使用成员 **3-legged OAuth Authorization Code**；不得用 Client Credentials 代替成员授权。Client ID、Client Secret、Refresh Token 仅以 Secret Reference 解析。
- MVP 只实现官方已核验的 Campaign Management、Ads Reporting 最小字段；每个字段/权限均需官方文档证据和测试账户验证。
- 最小权限按官方批准结果配置（典型为 `rw_ads`、`r_ads`、`r_ads_reporting`，不得自行扩大）；有机 Page 发布不在本阶段。
- 使用 HTTPS 出站、批准 Proxy/NAT 和 FQDN Allowlist；状态/报告采用轮询，不启用 Webhook。

### 9.2 实现要点

`connectors/linkedin/src/mappers.py` 将内部 Draft 映射为官方资源，保留 request/response 摘要哈希；`metrics.py` 保存官方原始字段、时间粒度、时区、分页游标和 retrieval time。Connector 不假设某个资源 ID 格式或未在官方文档确认的异步语义；不确定时返回 `verification_required`。

OAuth 首次授权只允许内部 HTTPS Redirect、企业 OAuth Broker 或受控管理员工作站；Redirect URI、scope、access tier 和 token 生命周期写入核验记录。Refresh、撤销、轮换和离职处理必须走 Secret Manager Runbook。

## 10. Google Ads Connector

### 10.1 固定约束

- 使用官方 Google Ads API endpoint（配置模板中的 `https://googleads.googleapis.com`）；`api_version` 由 `env://` 或 `config://` 非敏感引用注入，不能在代码中硬编码瞬态版本。
- Developer Token 必须是 Secret Reference，并作为独立的渠道凭据审计；绝不写入 YAML、测试 fixture、日志或错误响应。
- 认证模式只能是：
  - 企业**自有且批准**的账户：经 Security/IAM 批准后可使用 Google Service Account，优先采用 Workload Identity 或其他受管凭据，并把该身份按最小权限加入 Ads Account；
  - 其他客户/非企业自有账户：使用 OAuth Consent、OAuth Client 和 Refresh Token。不得默认 Service Account 代表普通客户账户。
- 报表使用 Google Ads API 的 GAQL 与 `GoogleAdsService.Search`/`SearchStream`（以官方当前文档和客户端版本核验为准），不创建虚构的“Reporting API”。
- `customer_id`、可选 `login_customer_id`、Manager/Customer 关系和 access level 必须由 `env://`/`config://` 引用提供并验证；无官方批准 quota 时不填写猜测值。
- 仅 HTTPS 出站轮询，无公网 Webhook；分页、SearchStream 重连和 token refresh 必须可审计。

### 10.2 实现要点

`connectors/google_ads/src/mappers.py` 只生成通过 Dry-run 的资源层级；`metrics.py` 将 GAQL 字段和 Google Ads 时区原样保存，另算统一 read model。Developer Token、OAuth Client/Refresh Token 由 `SecretResolver` 提供；企业自有账户的 Service Account 优先通过 Workload Identity/受管凭据引用取得，不允许模型或前端传入长期 JSON Key。

## 11. 原始指标与归一化指标

### 11.1 Raw Metrics（不可变）

`raw_channel_metrics` 每条记录至少包含：

```text
metric_id, tenant, channel, account_id, external_object_id,
provider_field_name, provider_value, provider_value_type,
provider_currency, provider_timezone, attribution_window,
period_start, period_end, provider_api_version,
retrieved_at, source_response_ref, source_response_hash,
connector_version, trace_id
```

- `provider_value` 按供应商原类型保存；整数、Decimal、百分比、枚举和缺失值不混淆。
- 不把缺失、不可用、权限不足和真实 `0` 互相转换；重复拉取以 `(channel, object, field, period, source_response_hash)` 去重。
- 原始记录只追加，供应商修订由新 retrieval/version 表示；禁止模型、报表或归一化任务 UPDATE 原值。

### 11.2 Normalized Metrics（可重算）

`normalized_metrics` 独立保存：

```text
metric_id, channel, external_object_id, canonical_metric,
value_decimal, currency, timezone, period_start, period_end,
formula_version, source_raw_metric_ids, quality_status, calculated_at
```

统一维度至少包含 `impressions`、`clicks`、`spend`、`conversions`（供应商提供时）、`ctr`、`cpc`、`cpm`、`conversion_rate`。公式、汇率、归因窗口、币种和时区必须显式版本化；无法可靠转换时返回 `not_available`，不插补。对账/指标读取失败不会覆盖上一版，只标记 freshness 和 error。

## 12. 报告与策略草稿

### 12.1 `PerformanceReport`

`PerformanceReport` 是只读产物，包含：

- report/run/campaign/channel/account 标识、时间窗口、数据新鲜度；
- raw/normalized 数据引用、公式版本、币种/时区/归因窗口；
- 花费、曝光、点击、CTR、CPC、CPM、转化及分渠道对比；
- 数据质量、缺失字段、权限/限流/延迟告警；
- 预算消耗与已批准上限的差异；
- 每个结论的来源 raw metric ID、计算版本和 `trace_id`。

报告模板禁止把推断写成事实；没有数据就写 `not_available` 并列出原因。报告落到 Object Store 的 `{environment}/{tenant}/campaign/{run_id}/reports/`，数据库只存 URI、哈希和元数据。

### 12.2 `StrategyRecommendation`/策略草稿

策略草稿可提出“调整预算/受众/素材/排期”的建议、证据、预期影响、风险、置信度和下一步审批范围，但必须：

- 明确标记 `DRAFT`、生成版本、数据窗口和原始证据；
- 不调用任何 L3/L4 写 Tool，不直接修改 Campaign；
- 预算、受众、竞价、暂停/删除等建议生成新的 `ActivationRequest` 或人工任务，并重新 Dry-run、审批和输入哈希；
- 与产品事实知识库、Content Package 和 Memory 分离保存。

## 13. 可复制配置模板

以下模板可直接复制为 `config/linkedin.yaml`。所有 `${...}` 都是环境变量名或 Secret Manager 引用名，不是秘密值；提交前必须由配置加载器解析、校验未知字段并脱敏打印。

```yaml
schema_version: "1.0"
provider: "linkedin"
connector: "connectors.linkedin.LinkedInAdvertisingConnector"
enabled: false
mode: "mock" # mock | sandbox | live
endpoint:
  base_url: "https://api.linkedin.com"
  api_version: "${LINKEDIN_API_VERSION}"
  resource_prefix: "/rest"
  verify_tls: true
  version_source: "env://LINKEDIN_API_VERSION"
  official_docs:
    - "https://learn.microsoft.com/en-us/linkedin/marketing/quick-start"
    - "https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow"
    - "https://learn.microsoft.com/en-us/linkedin/marketing/integrations/ads/getting-started"
  verification: "required-before-sandbox-or-live"
auth_method: "oauth_3legged"
auth:
  client_id_ref: "secret://dmt/${DMT_ENV}/linkedin/client-id"
  client_secret_ref: "secret://dmt/${DMT_ENV}/linkedin/client-secret"
  refresh_token_ref: "secret://dmt/${DMT_ENV}/linkedin/refresh-token"
  redirect_uri_ref: "config://oauth/linkedin/redirect-uri"
  scopes:
    - "rw_ads"
    - "r_ads"
    - "r_ads_reporting"
  token_endpoint: "https://www.linkedin.com/oauth/v2/accessToken"
  authorization_endpoint: "https://www.linkedin.com/oauth/v2/authorization"
  rotation_runbook: "docs/runbooks/channel-token-rotation.md"
account:
  account_id_ref: "config://accounts/${DMT_ENV}/linkedin/ad-account-id"
  test_account_required: true
  production_access_tier_ref: "config://approvals/linkedin/access-tier"
rate_limit:
  requests_per_window_ref: "config://limits/linkedin/approved-rpm"
  window_seconds: 60
  quota_source: "official-doc-and-approved-application"
  on_exhausted: "queue-with-jitter"
retry_strategy:
  max_attempts: 3
  retryable_errors: ["TIMEOUT", "NETWORK", "HTTP_429", "HTTP_500", "HTTP_502", "HTTP_503", "HTTP_504"]
  non_retryable_errors: ["AUTH_EXPIRED", "HTTP_400", "HTTP_401", "HTTP_403", "SCHEMA_INVALID"]
  reconcile_before_retry: true
  honor_retry_after: true
  backoff: "exponential"
  base_delay_seconds: 2
  max_delay_seconds: 60
  jitter: "full"
timeouts:
  connect_seconds: 5
  read_seconds: 30
  write_seconds: 30
  total_seconds: 45
environment:
  name_ref: "env://DMT_ENV"
  feature_flag_ref: "config://features/linkedin-real-api"
  secret_namespace: "dmt/${DMT_ENV}/campaign/linkedin"
  external_fqdn_allowlist_ref: "config://network/linkedin/fqdns"
proxy:
  required: true
  url_ref: "secret://dmt/${DMT_ENV}/egress/proxy-url"
  ca_bundle_ref: "secret://dmt/${DMT_ENV}/egress/ca-bundle"
  static_egress_ip_ref: "config://network/static-egress-ip"
  allow_inbound: false
mock:
  deterministic: true
  fixture_set: "connectors/linkedin/fixtures/mock_success.yaml"
  fault_fixture_set: "connectors/linkedin/fixtures/mock_faults.yaml"
  clock_ref: "fake://clock/2026-09-14T00:00:00Z"
  seed: 31014
  fault_injection:
    enabled: true
    scenarios:
      - "HTTP_429"
      - "TIMEOUT_AFTER_EXTERNAL_CREATE"
      - "AUTH_EXPIRED"
      - "DUPLICATE_DELIVERY"
      - "PARTIAL_HIERARCHY_SUCCESS"
```

以下模板可直接复制为 `config/google_ads.yaml`。`use_service_account` 只有在 Security/IAM 对企业自有账户的审批记录存在时才能为 `true`。

```yaml
schema_version: "1.0"
provider: "google_ads"
connector: "connectors.google_ads.GoogleAdsConnector"
enabled: false
mode: "mock" # mock | sandbox | live
endpoint:
  base_url: "https://googleads.googleapis.com"
  api_version: "${GOOGLE_ADS_API_VERSION}"
  version_source: "env://GOOGLE_ADS_API_VERSION"
  official_docs:
    - "https://developers.google.com/google-ads/api/docs/api-policy/developer-token"
    - "https://developers.google.com/google-ads/api/docs/oauth/overview"
    - "https://developers.google.com/google-ads/api/docs/oauth/service-accounts"
    - "https://developers.google.com/google-ads/api/docs/best-practices/test-accounts"
  verification: "required-before-sandbox-or-live"
auth_method: "oauth" # oauth | service_account_approved
auth:
  developer_token_ref: "secret://dmt/${DMT_ENV}/google_ads/developer-token"
  oauth_client_id_ref: "secret://dmt/${DMT_ENV}/google_ads/oauth-client-id"
  oauth_client_secret_ref: "secret://dmt/${DMT_ENV}/google_ads/oauth-client-secret"
  refresh_token_ref: "secret://dmt/${DMT_ENV}/google_ads/refresh-token"
  service_account_identity_ref: "config://identity/google-ads/workload-identity"
  managed_credential_ref: "config://identity/google-ads/managed-credential"
  use_service_account: false
  service_account_approval_ref: "config://approvals/google-ads/service-account"
  redirect_uri_ref: "config://oauth/google-ads/redirect-uri"
account:
  customer_id_ref: "config://accounts/${DMT_ENV}/google_ads/customer-id"
  login_customer_id_ref: "config://accounts/${DMT_ENV}/google_ads/login-customer-id"
  manager_account_required: true
  test_account_required: true
  enterprise_owned_account_required_for_service_account: true
rate_limit:
  requests_per_window_ref: "config://limits/google-ads/approved-rpm"
  daily_operations_quota_ref: "config://limits/google-ads/approved-daily-quota"
  quota_source: "official-doc-and-approved-developer-token-access-level"
  on_exhausted: "queue-with-jitter"
retry_strategy:
  max_attempts: 3
  retryable_errors: ["TIMEOUT", "NETWORK", "HTTP_429", "HTTP_500", "HTTP_502", "HTTP_503", "HTTP_504", "INTERNAL"]
  non_retryable_errors: ["AUTH_EXPIRED", "DEVELOPER_TOKEN_INVALID", "PERMISSION_DENIED", "INVALID_ARGUMENT", "POLICY_VIOLATION"]
  reconcile_before_retry: true
  honor_retry_after: true
  backoff: "exponential"
  base_delay_seconds: 2
  max_delay_seconds: 60
  jitter: "full"
timeouts:
  connect_seconds: 5
  read_seconds: 45
  write_seconds: 45
  total_seconds: 60
environment:
  name_ref: "env://DMT_ENV"
  feature_flag_ref: "config://features/google-ads-real-api"
  secret_namespace: "dmt/${DMT_ENV}/campaign/google-ads"
  external_fqdn_allowlist_ref: "config://network/google-ads/fqdns"
proxy:
  required: true
  url_ref: "secret://dmt/${DMT_ENV}/egress/proxy-url"
  ca_bundle_ref: "secret://dmt/${DMT_ENV}/egress/ca-bundle"
  static_egress_ip_ref: "config://network/static-egress-ip"
  allow_inbound: false
query:
  reporting_service: "GoogleAdsService"
  query_language: "GAQL"
  stream_mode: "SearchStream"
  api_version_source: "config://endpoint/api-version"
mock:
  deterministic: true
  fixture_set: "connectors/google_ads/fixtures/mock_success.yaml"
  fault_fixture_set: "connectors/google_ads/fixtures/mock_faults.yaml"
  clock_ref: "fake://clock/2026-09-14T00:00:00Z"
  seed: 31015
  fault_injection:
    enabled: true
    scenarios:
      - "HTTP_429"
      - "TIMEOUT_AFTER_EXTERNAL_CREATE"
      - "AUTH_EXPIRED"
      - "DUPLICATE_DELIVERY"
      - "PARTIAL_MUTATE_SUCCESS"
```

配置要求：

- `mode: mock` 是默认值；`sandbox`/`live` 必须同时有 Feature Flag、审批、Secret Manager、Proxy、测试/生产准入和官方文档核验。
- 模板中的 endpoint 是官方域名，不代表已获调用权限；API version、RPM、每日 quota、access tier 和账户 ID 均不得写死，必须来自经批准的 `env://` 或 `config://` 引用（Developer Token 等真正秘密仍使用 `secret://`）。
- 禁止真实 Secret、Refresh Token、Developer Token、长期 JSON Key、Client Secret 出现在 Git、fixture、snapshot、日志、错误或 Prompt；企业 Service Account 仅使用经批准的 Workload Identity/受管凭据引用。
- 不支持的 quota 或未经官方确认的 endpoint/字段必须删除或标为 `verification: blocked`，不能以占位数字伪装可用。

## 14. 官方文档核验门

每个渠道在启用 `sandbox` 前必须提交 `docs/runbooks/channel-token-rotation.md` 或等价核验记录，逐项包含 URL、访问日期、文档版本/页面标题、截图或响应摘要哈希、核验人和结论：

1. 官方 REST/Google Ads endpoint、API version 注入方式和资源路径。
2. Campaign 创建/查询/状态/报告字段、分页、异步操作和错误码。
3. LinkedIn 3-legged OAuth、scope、Redirect URI、Access Tier；禁止 Client Credentials。
4. Google Developer Token、Basic/Explorer/Production Access、Manager/Customer 关系和 Developer Token 使用要求。
5. Google Service Account 是否允许目标企业自有账户；若不满足必须使用 OAuth。
6. 官方 rate limit/quota 的实际批准值、窗口和超限响应；未知值不得进入配置。
7. 测试账户可用能力、数据隔离、账单/花费限制和生产晋级条件。
8. 无公网 Webhook 的轮询方案、Token rotation/revoke 和数据保留/驻留要求。
9. Proxy/NAT 的精确 FQDN、静态出口 IP、TLS 和安全批准。

核验失败的 Connector 只能返回 `verification_required`，CI 应阻止 `sandbox`/`live` 配置合并。任何供应商要求公网 Callback/Webhook 时，立即阻断并提交独立安全评审；本阶段不开放 `/api/*` 公网入站。

## 15. 测试、评估与验收标准

### 15.1 TDD 顺序

1. 先阅读当前实现、Phase 01 契约、依赖和测试，列出假设、阻断点和影响路径。
2. 先新增会失败的 Unit/Contract/Workflow/Integration/Security 测试，再实现最小代码（RED-GREEN-REFACTOR）。
3. 每次改动只触及本阶段必要文件；不得顺手重构、换 Runtime 或恢复旧部署资产。
4. 目标测试通过后，运行受影响模块测试、类型检查、lint/build、Migration 和跨语言契约测试。
5. 用 code-review-graph 或等价本地影响面分析检查符号、调用方、权限、Queue、Migration、Connector 和 fixtures；影响面分析不能替代测试。
6. 共享契约、Approval、Migration、Tool Policy、Secret/Proxy 配置必须双人审查并保留证据。

### 15.2 必测场景

**Unit/Contract**

- `ActivationRequest` 缺字段、未知字段、过期包、哈希不匹配、负预算、币种/时区/市场/素材规格错误均拒绝。
- 相同输入产生相同 Draft 指纹；预算或受众变化产生新哈希并使旧 Token 失效。
- LinkedIn 使用 3-legged OAuth；Google Service Account 未审批时拒绝，默认 OAuth。
- `validate_config` 拒绝缺 endpoint、auth、api version ref、quota ref、proxy 或官方核验标志的真实配置。
- Connector Error 正确区分 retryable/reconcile_required；不泄漏 Secret。

**Workflow/Approval/Security**

- L3 无审批、过期、撤销、已使用、发起人自批、哈希不匹配的拒绝率为 100%。
- Dry-run 不产生外部调用副作用；策略 Tool 无法写 Campaign。
- Duplicate queue delivery、Worker restart、重复执行同一幂等键均不产生重复外部对象。
- 超时后对账找到对象时不重建；确认未创建后才重试；未知状态进入人工/DLQ。
- Audit 写失败时高风险 Tool fail closed；两个 Agent 无法读取对方凭据、上下文和 Memory。

**Integration/Recovery**

- LinkedIn/Google Test Account 各完成 Draft -> Dry-run -> Approval -> Publish -> Reconcile -> Metrics。
- 注入 429、网络错误、Token 过期、超时后外部已创建、部分层级成功、分页断点和 DLQ。
- 原始指标重复拉取去重；缺失值不变为 `0`；normalized 重新计算不改变 raw。
- 供应商后台修改对象后，对账报告差异并不擅自覆盖或自动修复。

### 15.3 量化验收门槛

- LinkedIn 和 Google Ads 测试账户端到端成功率：每渠道至少 10 个确定性场景，成功率 100%。
- 未审批/无效审批的外部写调用：0；测试中拒绝率：100%。
- 同一幂等键在 100 次重复消息/重试下的重复 Campaign/层级对象：0。
- 外部写操作具备 `approval_id`、`input_hash`、`idempotency_key`、审计和对账证据：100%。
- 超时后“先对账再重试”场景遵守率：100%；外部已创建对象的重复创建：0。
- 预算、账户、地区/受众、排期和素材规格违规拦截率：100%。
- raw metric 原样保存、可追溯到 response hash；归一化不得覆盖 raw：100%。
- 报告每个结论可追溯到 raw metric ID/公式版本：100%；无数据不生成虚构数值。
- Secret 出现在 Git、fixture、日志、Trace、错误响应和 API 响应：0。
- `mock` 配置下测试无外部 HTTP；无公网入站/Webhook 资源：0。
- 受影响既有测试、Python/TypeScript 契约测试、Migration 正向/回退/再正向和 CI Critical 检查：全部通过。

## 16. 时间估算与交付计划（2026-09-14 至 2026-10-02）

| 日期 | 交付与门禁 |
|---|---|
| 09-14 | 读取 Phase 01 产物；冻结 MA-01 契约字段、假设、阻断台账；为 `ActivationRequest`、Connector Error、Campaign Proposal 写失败测试。 |
| 09-15 | 完成 Schema、Canonical Hash、Draft 状态机、Campaign Policy 和 API/Worker 骨架；接入 Fake Clock/Queue/Secret。 |
| 09-16 | 完成 `Connector` SDK、Error Mapping、Http/Proxy 抽象、确定性 LinkedIn/Google fixtures 和故障注入。 |
| 09-17 | 完成 Campaign Draft、LinkedIn/Google Dry-run、预算/受众/素材规格校验；运行 Unit/Contract 门禁。 |
| 09-18 | 完成两渠道官方文档/权限/endpoint/version/quota 核验；拿到 SIT Credential、测试账户、OAuth Redirect POC 和 FQDN Allowlist，否则保持 mock。 |
| 09-21 | 完成 Approval UI/API、单次 Token 原子消费、L3/L4 Policy、input hash 和审计；完成安全负向测试。 |
| 09-22 | 完成 LinkedIn sandbox Connector、3-legged OAuth、Campaign 写/查/状态映射和 reconcile-before-retry。 |
| 09-23 | 完成 Google Ads sandbox Connector、Developer Token Secret Reference、OAuth；Service Account 仅实现审批后分支。 |
| 09-24 | 完成幂等表/Outbox、Worker lease、重复消息、超时外部已创建、部分成功和补偿 Runbook。 |
| 09-25 | 完成 raw metric ingestion、GAQL/LinkedIn reporting 轮询、分页/游标、normalized metric 计算和 freshness。 |
| 09-28 | 完成 Performance Report、Strategy Draft、导出/只读 API；验证策略不能直接写 Campaign。 |
| 09-29 | 每渠道至少 10 个 E2E 测试、恢复/DLQ/限流/Token 过期/后台改动场景；修复仅限本阶段影响。 |
| 09-30 | 运行跨语言 Contract、Integration、Security、Performance、Migration、Secret Scan；完成影响面和规格审查。 |
| 10-01 | 仅在审批和官方核验均通过时运行测试账户真实端到端；否则提交 mock 证据和阻断项，不伪造成功。 |
| 10-02 | 阶段评审和签字：量化门槛全通过、Runbook/告警/回滚齐备；未满足项明确 Owner、风险和 Phase 4 处理日期。 |

## 17. 风险、缓解与注意事项

| 风险 | 信号 | 缓解/退出条件 | Owner |
|---|---|---|---|
| LinkedIn 权限、Access Tier 或 Redirect 延迟 | 无 Development Access/测试账户 | Fake + Contract 并行；无官方核验不启用 sandbox/live | Product/IAM |
| Google Developer Token quota/access level 不足 | 429、申请未批准 | 只使用批准 quota；降低测试并发、排队；禁止猜测 quota | Marketing/API Owner |
| Service Account 被错误用于非自有账户 | 无企业所有权/安全批准 | 强制 OAuth；配置校验拒绝未批准 service account | IAM/Security |
| 供应商版本/字段瞬态变化 | 文档与响应 Schema 不一致 | 版本配置化、官方核验门、Contract fixture；禁止硬编码版本 | Connector Owner |
| API 超时但已产生副作用 | `UNKNOWN` 状态增长 | reconcile-before-retry、操作表唯一键、人工队列；重复对象必须为 0 | Backend/SRE |
| OAuth Token 泄漏或过期 | 日志扫描命中、401 增加 | Secret Manager、脱敏、rotation/revoke Runbook、告警 | Security |
| 部分层级成功导致半成品 | 资源层级状态不一致 | 逐层记录 ID、停止后续写入、审批后的最小补偿 | Campaign Owner |
| raw/normalized 指标混淆 | 缺失值变 0、报表不可追溯 | 两表/两 Schema、公式版本、raw hash 和质量门禁 | Data Owner |
| API/Queue/Proxy 不可用 | DLQ、Oldest Message Age、Proxy 错误 | 指数退避、熔断、DLQ、状态报告；不盲目重试 | SRE |
| 旧原型被误当生产实现 | 直接导入旧 UI/Bridge/Buffer | 兼容层隔离、Connector SDK 强制、代码审查检查依赖方向 | Tech Lead |
| 范围膨胀到自动优化/其他渠道 | 出现 L4 Tool 或新 SDK | Non-scope 拒绝；新增能力另立 ADR/阶段 | Product Owner |

## 18. Coding Agent 完成清单

提交前必须在 PR 描述中提供：

- 修改文件清单和每个文件的必要性；确认只创建/修改本 Phase 03 文件范围，不恢复用户删除内容。
- 假设、阻断点、官方文档核验链接/日期、测试账户与 Secret Reference（只写引用名，不写值）。
- RED 失败输出、GREEN 目标测试、受影响测试、lint/typecheck/build、Migration 和 Secret Scan 结果。
- `ActivationRequest`/Connector Contract fixtures、输入哈希示例、Approval/Idempotency/Reconcile/Compensation 证据。
- LinkedIn 与 Google Ads 的测试结果、原始指标 response hash、normalized 公式版本和报告追溯样例。
- 影响面审查：调用方、Tool Registry、权限、队列、数据库表、配置合并顺序、告警和回滚；共享契约、Migration、Tool Policy 变更完成双人审查。

严禁：

- 先写代码再补测试、无依据猜 endpoint/version/quota/auth、提交真实凭据；
- 把 timeout 当失败后直接重试、用模型输出覆盖 raw metric、绕过审批或把策略直接写入生产；
- 引入通用 URL Fetch、Shell、原始 SQL、公网 Webhook、第二套 Runtime 或无关重构。

## 19. AI 输出质量 Checkpoints

### 19.1 判定协议

- 所有 Campaign AI 输出先过 Schema、批准内容包、Policy、预算、渠道规格和权限硬门，再做独立质量评分和人工复核。
- Agent、Strategy Generator 和 LLM Critic 均不能签发外部写权限；AI 自评不能消费 Approval Token。
- 结果仅为 `PASS / FAIL / BLOCKED`。API 权限、测试账户或官方规格缺失时为 `BLOCKED`，不得用 Mock 成功替代。
- Producer/Evaluator Run 隔离；Evaluator 只接收规范化产物、原始证据、Rubric 和只读 Tool，不接收 Producer 结论或 Chain-of-Thought。
- 软维度按 0–4 分，默认加权平均 >= 3.4、单项 >= 3；金额、日期、受众、事实、审批、幂等和审计为不可被平均分抵消的硬门。

### 19.2 阶段 Checkpoint 矩阵

| ID | 触发时点与 AI 输出 | 检查内容 | PASS 阈值 | Owner / 证据 | FAIL 后动作 |
|---|---|---|---|---|---|
| P3-CP01 | `BuildCampaignDraft` 后 | 内容包忠实映射、目标/预算/币种/时区/受众完整、渠道文案未改变批准 Claim、假设明确 | 内容 hash 匹配 100%；批准 Claim 漂移 0；必填字段 100%；软评分 >= 3.4 | Marketing + Campaign Operator；Proposal diff、Content refs | 返回 Draft Mapper/Prompt；不得进入 Dry-run |
| P3-CP02 | `ChannelDryRun` 后 | 账户、预算、地区、受众、排期、素材规格、渠道 Policy 和错误解释 | 违规拦截率 100%；Dry-run 外部副作用 0；错误分类和修复建议正确率 >= 95% | Connector Owner + QA；Dry-run report、fixtures、API version | 返回 Mapper/Policy/Connector；重新核验官方规格 |
| P3-CP03 | `Activate` 前后 | Approval Token、input hash、幂等、执行意图、外部结果和 reconcile 证据 | 无效审批写调用 0；100 次重复投递重复对象 0；未知结果先对账 100%；Audit 完整率 100% | Campaign Approver + Security；Approval/Operation/External ID/Audit | Kill Switch；返回 Approval/Idempotency/Reconcile 层 |
| P3-CP04 | `AnalyzePerformance`/`PerformanceReport` 后 | 数值正确性、Raw 来源、公式版本、数据新鲜度、因果措辞、缺失值处理 | 与确定性计算一致率 100%；Raw 追溯率 100%；虚构数值/因果结论 0；软评分 >= 3.4 | Data Owner + Marketing；Raw IDs、formula version、report diff | 返回 Metric Normalizer/Report 节点；Raw 不可修改 |
| P3-CP05 | `RecommendStrategy` 后 | 建议与证据、目标、预算和 Policy 一致；风险/置信度校准；可执行性 | 建议证据链接率 100%；越过批准范围 0；直接写 Tool 调用 0；软评分 >= 3.4 | Marketing + Campaign Approver；Strategy/Evidence/Denied Tool Trace | 返回 Strategy 节点；需执行的建议创建新 Request |
| P3-CP06 | 阶段退出前 | LinkedIn/Google 双渠道一致性、Mock 与测试账户差异、回归和官方文档核验 | 每渠道至少 10 个场景 100% 通过；Critical/High Finding 0；未核验配置 0 | QA + API Owner；Contract/E2E/官方核验记录 | `BLOCKED` 或返回 Connector；不得宣称真实接通 |

### 19.3 Eval 与人工抽样

- 固定预算越限、币种/时区错误、受众违规、素材不匹配、Token 失效、超时已创建、重复消息、429 和后台手工修改数据集。
- 报告和 Strategy 退出评审至少分层抽样 30 个输出；所有外部写场景、所有 Critical/High Policy 场景必须 100% 人工复核。
- AI Evaluator 只能评相关性、清晰度、可执行性和风险校准；金额、指标和渠道合规使用代码/官方 Contract 判定。
- Prompt、Model、Policy、API version、Connector 或指标公式变化后重跑对应 Checkpoint；连续失败 3 次停止自动重试并升级 Owner。
- P3-CP01 至 P3-CP06 全部 `PASS` 才可将 Phase 03 标记完成并交付 SIT。
