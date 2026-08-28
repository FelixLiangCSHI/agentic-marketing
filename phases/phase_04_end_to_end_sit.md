# Phase 04：端到端 SIT 与故障恢复

> 计划窗口：2026-09-28 至 2026-10-09  
> 路线图映射：原 Phase 4  
> 阶段里程碑：在 SIT 完成 Content -> Approval -> Campaign -> Approval -> Publish -> Reconcile -> Metrics -> Report 的可信闭环  
> 环境入口：`https://digital-marketing-sit.carstream-int.com`  
> 执行模式：**Remote-validation Dominant**；测试定义和部署 Manifest 在 GitHub，阶段主体必须在 SIT 远端执行

## 1. 阶段目标

1. 将 Phase 01–03 的 Release Candidate 部署到独立 SIT 环境。
2. 使用脱敏 Product 数据、供应商 Development/Sandbox Credential 和专用测试广告账户完成双 Agent 端到端测试。
3. 验证拒绝返工、审批失效、外部写幂等、超时对账、Queue 重复投递、Worker 恢复、DLQ 和定时指标拉取。
4. 验证所有关键状态、权限决策、Tool 调用、审批、外部对象和指标可通过统一 Trace/Audit 追溯。
5. 验证无公网入站、批准 Proxy/NAT、FQDN Allowlist、Secret Manager 和四环境隔离。
6. 形成可复现的 SIT Evidence Pack、缺陷台账和 SIT -> UAT 晋级决定。

## 2. Scope / Non-scope

### 2.1 本阶段包含

- SIT 环境部署、Migration、配置和健康检查。
- Content Agent 与 Campaign Agent 完整业务路径。
- LinkedIn Advertising 与 Google Ads 的测试账户调用。
- DeepSeek、即梦在获批情况下的 SIT Credential；未获批 Provider 保持 Mock 并记录阻断。
- SSO、RBAC、Medical/Marketing/Campaign Approval。
- Queue、DLQ、Object Storage、PostgreSQL、Proxy、Secret 和 Observability 集成。
- 正常、拒绝、取消、超时、限流、Token 到期、重复投递、Worker 重启、外部部分成功和数据过期场景。
- 50 并发的 SIT 基线与长任务积压测试。
- 缺陷分级、修复验证和回归。

### 2.2 本阶段不包含

- 生产 Credential、生产广告账户或真实业务预算。
- PRD 300 并发最终容量结论。
- 新增渠道、第二媒体供应商或新 Workflow Runtime。
- 自动修改预算、竞价、受众、暂停或删除 Campaign。
- 公网 Callback、Webhook、CDN 或绕过内部 Gateway 的入口。
- 用 Mock 结果替代供应商测试账户的真实 Contract 验收。

### 2.3 GitHub Repo 与 SIT 远端分工

| GitHub Repo 保留 | SIT 远端执行 |
|---|---|
| SIT 测试代码、故障 fixture、Deployment Manifest、Migration、配置 Schema、Dashboard/Alert 定义、Runbook、Evidence 模板 | RC 部署、SSO/Gateway/DB/Queue/Object Store/Secret/Proxy 连通 |
| Mock/Contract 回归、静态扫描、Schema/Migration 预检 | LinkedIn/Google 测试账户发布、对账和指标读取 |
| 缺陷修复及其失败测试、版本化 Prompt/Policy/Skill | Worker 重启、重复投递、DLQ Replay、Token 到期、50 并发 |

远端执行要求：

- 使用受保护 SIT Pipeline 和企业内自托管 Runner；普通 PR 只能生成候选 Artifact，不能自动部署 SIT。
- SIT 只部署由 commit SHA 和 image digest 标识的 RC；禁止 SSH 热修、手工复制文件或现场修改 Prompt/Policy。
- Secret、脱敏 Product 数据、外部 API 原始响应和对象只留在 SIT；GitHub Artifact 只保存脱敏报告、hash 和受控 Evidence Link。
- 测试脚本可以从 Repo 运行，但运行身份、网络入口、预算和清理任务由 Environment Approval 控制。
- Phase 04 属于远端验收阶段：没有 SIT DNS、SSO、Database、Queue 和渠道测试账户证据时，阶段必须 `BLOCKED`。

## 3. 前置条件与启动门禁

### 3.1 代码门禁

- Phase 01 的 Harness、Approval、Audit、Queue、Checkpoint、Contract 和 CI 退出条件通过。
- Phase 02 的 `ApprovedContentPackage`、Golden/Adversarial Eval 和定点返工通过。
- Phase 03 的 `ActivationRequest`、双渠道 Dry-run、幂等、对账、指标和 Strategy Draft 通过。
- Python/TypeScript 契约使用相同 Golden/Invalid fixtures。
- 所有 Migration 可空库正向、回退一个版本、再次正向。
- Release Candidate 使用不可变 commit SHA 和镜像 digest。

由于 SIT 在 Phase 03 后半段开始，分波次进入：

1. 2026-09-28 起先验证 Phase 01/02 和 Phase 03 的 Mock RC。
2. Phase 03 渠道 Contract 在 2026-10-02 通过后，再启用 LinkedIn/Google 测试账户路径。
3. 任何未达到门禁的功能保持禁用，不允许用临时绕过进入共享 SIT。

### 3.2 环境门禁

| 项目 | 要求 | 阻断行为 |
|---|---|---|
| Internal DNS / TLS | SIT 域名、Gateway 侧证书有效 | 入口测试阻断 |
| Gateway | `/` -> Web:8080；`/api/*` -> API:8000 | 路由不符不得测试 |
| SSO | 独立 SIT OIDC/SAML App 和组映射 | 不得使用 DEV/PRD App |
| PostgreSQL | 独立 SIT 数据库、TLS、Role、备份 | Migration 阻断 |
| Queue/DLQ | Content/Campaign/Connector 独立 Queue | Worker 测试阻断 |
| Object Store | 独立 Bucket/Prefix、KMS、生命周期 | 媒体路径阻断 |
| Secret Manager | 独立 SIT Namespace | 不得用文件或 DEV Secret |
| Proxy/NAT | 静态出口 IP、批准 FQDN、TLS | 真实外部调用阻断 |
| API Credential | SIT/Development Credential 和测试账户 | 对应 Connector 保持 Mock |
| Observability | Log、Metric、Trace、Alert 索引 | Critical Workflow 阻断 |

### 3.3 API 时间门禁

2026-09-18 应已获得：

- SIT Credential。
- LinkedIn/Google 测试广告账户。
- OAuth Redirect POC。
- 外部 FQDN Allowlist。

2026-10-02 应满足：

- Production Access 审核完成，或有明确书面批准日期。
- UAT 所需 Quota 已确认。

未满足时，SIT 可继续验证 Mock、Contract、权限和恢复，但必须把真实外部路径标记为 `BLOCKED_EXTERNAL_DEPENDENCY`，不得标记为通过。

## 4. SIT 基础设施基线

| Role | 规格 | 端口 | 说明 |
|---|---|---|---|
| Web | 2 Core / 4 GB / 60 GB | 8080/TCP | 单节点，内部 Gateway/LB |
| API/Worker | 4 Core / 8 GB / 100 GB | 8000/TCP；443 出站 | 单 VM 可运行隔离 Worker 进程 |
| PostgreSQL | 4 Core / 8 GB / 200 GB | 5432/TCP | 托管 PostgreSQL 16，私有 Endpoint |

共同要求：

- Region：SG。
- OS：RHEL 9.7 基线，最终小版本由 IT 确认。
- 入口只允许内部 HTTPS `443/TCP`。
- 无公网入站、无 CDN。
- 外部 API 只经批准的 HTTPS Proxy/NAT。
- Queue、Bucket、Database、Secret、SSO App、OAuth Client 和模型 Project 不与 DEV/UAT/PRD 共用。

## 5. 交付物与目标路径

```text
tests/
  integration/sit/
    test_content_to_campaign.py
    test_rejection_and_rework.py
    test_external_write_reconciliation.py
    test_metrics_and_reports.py
    test_environment_isolation.py
  workflow/sit/
  security/sit/
  performance/sit/
  recovery/sit/
  fixtures/sit/
    product/
    deepseek/
    jimeng/
    linkedin/
    google_ads/
evals/
  content/sit/
  compliance/sit/
  campaign/sit/
  adversarial/sit/
infra/
  sit/
    deployment/
    config/
    network/
    observability/
docs/
  runbooks/sit-deployment.md
  runbooks/sit-test-plan.md
  runbooks/sit-recovery.md
  runbooks/connector-reconciliation.md
  runbooks/credential-rotation.md
```

CI Evidence 存为流水线 Artifact，不把真实响应、Token、员工身份、未发布素材或敏感 Product 数据提交到 Git。

## 6. 实现步骤

### 6.1 冻结 Release Candidate

1. 从通过 Phase 01–03 Critical CI 的 commit 创建 RC tag。
2. 构建 Web、API、Content Worker、Campaign Worker、Connector Worker 的不可变镜像。
3. 记录：
   - commit SHA。
   - image digest。
   - Migration revision。
   - Prompt/Model/Policy/Skill/Workflow 版本。
   - Connector 版本和 API version 配置。
4. SIT 缺陷修复通过短分支合入；每次修复生成新 RC，不原位替换镜像。
5. 禁止在 SIT 主机手工改代码或镜像。

### 6.2 部署与配置验证

部署顺序：

1. Database Role 与 Schema。
2. Migration。
3. Queue/DLQ、Bucket/Prefix、Secret Reference。
4. OpenTelemetry/Log/Metric。
5. API。
6. Worker。
7. Web。
8. Gateway Health Check。

验证：

- `/api/health/live` 不依赖外部供应商。
- `/api/health/ready` 验证 DB、Queue、Object Store 和关键配置。
- Readiness 不调用付费模型或创建外部对象。
- `mode: sandbox/live` 的 Connector 在缺少审批、Secret、Proxy、FQDN、Quota 或官方核验时启动失败。
- Web 只通过 `/api/*` 调用 Control API，不直连数据库或供应商。

### 6.3 建立脱敏测试数据

准备：

- 批准 Product、过期 Product、撤销 Product、跨市场 Product。
- 正常 Claim、禁用表达、竞品比较和无来源 Claim。
- LinkedIn/Google 测试账户。
- 测试预算硬上限。
- 合成媒体、恶意 MIME、超大文件和 Malware Scan 失败 fixture。
- 具备 Requester、Medical Reviewer、Marketing Reviewer、Campaign Approver、Auditor 角色的测试身份。

数据规则：

- 不使用 PRD 员工名单、真实患者/客户数据或未授权营销素材。
- Test Account 名称带 `DMT-SIT-` 前缀，便于对账和清理。
- 测试 Campaign 结束时间和预算有硬上限。
- 所有 fixture 有 Owner、版本、数据分类和清理日期。

### 6.4 执行 Critical Happy Path

`SIT-E2E-001`：

```text
Internal SSO Login
  -> Submit Content Request
  -> Retrieve Approved Product Facts
  -> Generate Copy and Media
  -> Compliance Check
  -> Medical/Marketing Review
  -> ApprovedContentPackage
  -> Build LinkedIn + Google Campaign Draft
  -> Channel Dry-run
  -> Campaign Approval
  -> Consume Single-use Token
  -> Publish to Test Account
  -> Reconcile External IDs
  -> Poll Raw Metrics
  -> Normalize Metrics
  -> Performance Report
  -> Strategy Draft
```

每一步必须验证：

- 输入/输出 Schema。
- Run/Task 状态。
- Workflow Journal/Checkpoint。
- Tool Policy 和 Approval。
- Trace 关联字段。
- Audit。
- Object Store URI 与 hash。
- 外部对象 ID 或明确的 Mock 标记。

### 6.5 执行审批与返工场景

| ID | 场景 | 预期 |
|---|---|---|
| SIT-E2E-002 | Compliance 检出 Critical Claim | 阻断 Review Approval |
| SIT-E2E-003 | Reviewer 指定 Copy 返工 | 只重跑 Copy 及下游节点 |
| SIT-E2E-004 | 修改已批准内容 | 创建新版本，旧审批失效 |
| SIT-E2E-005 | Campaign Approver 修改预算 | 重新 Dry-run、hash 和审批 |
| SIT-E2E-006 | 发起人自批 | 100% 拒绝并审计 |
| SIT-E2E-007 | Token 过期/撤销/已使用 | 100% 拒绝，不调用外部 API |
| SIT-E2E-008 | Package 过期/撤销 | Campaign Agent 拒绝消费 |

### 6.6 执行 Connector 故障矩阵

对 DeepSeek、即梦、LinkedIn、Google Ads 分别覆盖：

| 故障 | 注入方式 | 预期行为 |
|---|---|---|
| HTTP 429 | Stub 或测试限流 | 遵守 `Retry-After`；有界退避 |
| 408/网络超时 | Proxy Fault | 标记 retryable，不假成功 |
| 5xx | Stub/Fault Proxy | 熔断、有界重试、告警 |
| 400/Schema | Invalid fixture | 不重试，返回结构化错误 |
| 401/Token 过期 | 撤销测试 Token | 暂停、轮换/重新授权任务 |
| DNS/TLS/Proxy 拒绝 | Network Policy | 不允许直接绕过 Proxy |
| 响应格式变化 | Malformed fixture | Contract 失败，不静默默认 |

外部写入额外覆盖：

1. 请求超时但供应商已创建对象。
2. 响应返回后本地进程崩溃。
3. 同一消息投递 100 次。
4. 相同 idempotency key、不同 input hash。
5. Campaign/Ad Group/Ad 部分成功。
6. 用户在供应商后台手工修改对象。

预期：

- 先对账，再决定是否重试。
- 已存在对象不重复创建。
- 未知状态进入人工队列/DLQ。
- 本地与外部差异被报告，不自动覆盖。
- 需要暂停/删除的补偿生成审批或 Runbook 任务，不自动执行 L4。

### 6.7 执行 Queue 与 Worker 恢复

测试：

- Content、Campaign、Connector 消息重复投递。
- Worker 在 Tool 前、Tool 后、Checkpoint 前后退出。
- Task lease 过期和重新领取。
- Poison Message 达到最大重试进入 DLQ。
- DLQ Replay 使用相同幂等键。
- 任务取消发生在队列等待、执行、等待审批和轮询阶段。
- 定时 Metrics Job 保存 watermark/cursor 并补跑。

验收：

- Run 状态不回退到非法状态。
- 重复副作用为 0。
- 已完成节点不重复收费调用。
- 取消后不再启动新副作用。
- Replay 全程保留原 Run、Trace 和原因。

### 6.8 执行数据与指标验证

检查：

- Product 数据按 tenant/product/market/locale/validity 隔离。
- 批准 Claim 来源覆盖率 100%。
- Content Package 和媒体不可原位覆盖。
- Raw Channel Metrics 只追加。
- 缺失、权限不足、不可用和真实 `0` 不互相转换。
- Normalized Metrics 单独计算并带公式版本。
- 报告结论可追溯到 Raw Metric ID 和 response hash。
- 指标重复拉取去重。
- API 分页、游标和 watermark 可恢复。

### 6.9 执行安全集成测试

覆盖：

- 用户 Prompt、附件、Product API 文本、Tool Result 中的 Prompt Injection。
- 恶意 URL、SSRF、路径遍历、公式和伪造 MIME。
- 跨 Agent、跨 Tenant、跨环境访问。
- 前端伪造角色、审批、Package 状态、Tool Level。
- Secret 在日志、Trace、错误、Object Metadata 和 UI 的泄漏。
- 无审批 L3、所有 L4、任意 URL Fetch、通用 Shell、原始 SQL。
- Audit 不可用。

预期：

- 不可信文本只能作为数据。
- Secret 泄漏为 0。
- 跨域访问 100% 拒绝。
- Audit 失败时高风险 Tool fail closed。
- SSRF 只能访问明确 Allowlist，默认拒绝。

### 6.10 验证 Trace、指标与告警

每个 Critical Run 必须可按 `trace_id` 查询：

```text
run_id, task_id, agent_type, workflow_version, tool_call_id,
approval_id, content_package_id, campaign_id, external_object_id,
model, prompt_version, policy_version
```

触发并验证：

- L3/L4 无审批。
- 外部发布超时且无法对账。
- DLQ 非空。
- 未批准 Claim 尝试进入 Package。
- 费用达到 80%。
- Quota 达到 80%。
- RAG 来源过期。
- Worker 无心跳。
- Audit 写入失败。

每个告警具有 Owner、严重度、去重键、通知渠道、Runbook 和关闭条件。

### 6.11 执行 50 并发 SIT 基线

工作负载必须混合：

- 轻量 Portal 查询。
- Content Run。
- 媒体长任务。
- Campaign Dry-run。
- 测试账户发布。
- Metrics Poll。

记录：

- API p50/p95/p99。
- Queue Depth、Oldest Message Age。
- Worker 利用率和心跳。
- DB Connection/CPU/IOPS。
- 外部 API 429/5xx。
- Token、媒体任务和费用。

本阶段不擅自承诺未获 Product/SRE 签字的延迟 SLO。目标是确认在 50 并发下：

- 无数据错乱或跨用户响应。
- 无审批绕过。
- 无重复副作用。
- 队列可在测试窗口后回落。
- 资源数据足以支持 Phase 05 的 100/300 并发方案。

### 6.12 缺陷管理与回归

| 严重度 | 定义 | SIT 退出要求 |
|---|---|---|
| Critical | 未审批发布、Secret 泄漏、错误 Medical Claim、数据丢失、跨 Tenant | 0 |
| High | 重复 Campaign、无法恢复、审计缺失、主要路径不可用 | 0 |
| Medium | 有绕行方案且不破坏安全/数据正确性 | 有 Owner、修复日期、UAT 接受 |
| Low | 非关键 UI/文档问题 | 可进入后续 Backlog |

每个修复必须：

1. 添加可复现失败测试。
2. 最小修复。
3. 运行目标和受影响回归。
4. 重新生成 RC。
5. 关闭缺陷时附测试和部署证据。

## 7. 核心场景矩阵

| ID | 类别 | 场景 | 必需证据 |
|---|---|---|---|
| SIT-CONT-01 | Content | 批准事实 -> 内容包 | Claim/Source/Approval/Hash |
| SIT-CONT-02 | Content | 过期资料 | 检索过滤和阻断 Audit |
| SIT-CONT-03 | Content | 定点返工 | Journal 节点差异 |
| SIT-CAMP-01 | Campaign | LinkedIn 测试发布 | Approval/Idempotency/External ID |
| SIT-CAMP-02 | Campaign | Google 测试发布 | Approval/Idempotency/External ID |
| SIT-CAMP-03 | Campaign | 修改预算 | 新 hash、新审批 |
| SIT-FAIL-01 | Recovery | 超时但已创建 | Reconcile 证据、无重复 |
| SIT-FAIL-02 | Recovery | 100 次重复消息 | 单一外部对象 |
| SIT-FAIL-03 | Recovery | Worker 重启 | Checkpoint/Lease |
| SIT-FAIL-04 | Recovery | Poison Message | DLQ + Replay |
| SIT-METRIC-01 | Data | Raw/Normalized | Raw 不变、公式版本 |
| SIT-SEC-01 | Security | Prompt Injection | 数据/指令隔离 |
| SIT-SEC-02 | Security | 跨 Agent/跨 Tenant | 100% 拒绝 |
| SIT-OPS-01 | Observability | Critical Trace | 全字段完整 |
| SIT-PERF-01 | Performance | 50 并发混合负载 | 资源/Queue/错误报告 |

## 8. 验收标准

### 8.1 Critical Workflow

- [ ] Content -> Approval -> Package -> Campaign -> Approval -> Publish -> Reconcile -> Metrics -> Report 全链路通过。
- [ ] LinkedIn 与 Google Ads 均使用专用测试账户完成至少一次真实端到端；如外部审批阻断，明确标记未通过。
- [ ] Compliance Reject 和 Human Reject 均可定点返工。
- [ ] Strategy 只能生成草稿，不能修改外部 Campaign。

### 8.2 可靠性

- [ ] 100 次重复消息产生的重复 Campaign/媒体 Job：0。
- [ ] 外部写超时后先对账遵守率：100%。
- [ ] Worker 重启后 Critical Workflow 可恢复。
- [ ] Poison Message 正确进入 DLQ，Replay 不重复副作用。
- [ ] 所有 Retry 有最大次数、指数退避、抖动和错误分类。

### 8.3 安全与审计

- [ ] 无有效审批的 L3 调用：0；拒绝率 100%。
- [ ] L4 自动执行：0。
- [ ] Secret 泄漏：0。
- [ ] 跨 Agent、跨 Tenant、跨环境访问：0。
- [ ] Critical Run 的 Audit/Trace 字段完整率：100%。
- [ ] Audit 写失败时高风险 Tool 100% fail closed。

### 8.4 数据与质量

- [ ] 最终 Claim 来源覆盖率：100%。
- [ ] 过期/撤销资料进入 Package：0。
- [ ] Raw Metric 被覆盖：0。
- [ ] 报告结论到 Raw Metric/公式版本的追溯率：100%。
- [ ] 缺失值被转换为真实 `0`：0。

### 8.5 环境与晋级

- [ ] SIT 域名、TLS、Gateway 路由和 Health Check 通过。
- [ ] SIT SSO、Database、Queue、Bucket、Secret、OAuth Client 与其他环境隔离。
- [ ] 外部 API 只经批准 Proxy/NAT 和 FQDN Allowlist。
- [ ] Critical 缺陷：0；High 缺陷：0。
- [ ] Production API 权限已进入最终审核，Owner 和批准日期明确。
- [ ] SIT Evidence Pack、缺陷报告和 UAT 测试数据已签字。

## 9. 验证命令

以 Phase 01 创建的实际脚本为准；最低执行：

```powershell
npm ci
npm test
npm run lint
npm run typecheck
npm run build
python -m pytest tests\contract
python -m pytest tests\workflow tests\integration\sit
python -m pytest tests\security\sit tests\recovery\sit
python -m pytest tests\performance\sit
```

Deployment 后再运行：

```powershell
$env:DMT_ENV = "sit"
$env:DMT_BASE_URL = "https://digital-marketing-sit.carstream-int.com"
python -m pytest tests\integration\sit -m sit
```

测试进程只接收 Secret Reference，不读取或打印真实 Secret。失败日志上传前必须脱敏。

## 10. Evidence Pack

每次 SIT RC 产生：

- RC commit SHA 和 image digest。
- Config version/hash；只含非敏感值。
- Migration revision。
- 测试清单、通过率和失败链接。
- Golden/Adversarial Eval 结果。
- Connector Contract 版本和官方核验记录。
- 外部测试对象 ID 清单和清理状态。
- Trace/Audit 完整性报告。
- 50 并发报告。
- 缺陷台账和风险接受。
- SIT -> UAT 签字。

Evidence 保存在受控 CI Artifact/文档库，按公司政策设置访问与保留，不提交含敏感数据的原始响应。

## 11. 时间估算与里程碑

建议投入：10 个工程工作日；前半段与 Phase 03 收尾并行，后半段进行真实测试账户、恢复和回归。

| 日期 | 里程碑 |
|---|---|
| 2026-09-28 | SIT 环境、RC、Migration、SSO、Queue/Storage/Secret/Observability 就绪 |
| 2026-09-30 | Content、审批、Package 和 Mock Campaign 端到端通过 |
| 2026-10-02 | LinkedIn/Google Contract 与测试账户门禁；Production Access 状态确认 |
| 2026-10-05 | 双渠道发布/对账/指标与审批返工通过 |
| 2026-10-07 | 故障、重复、恢复、DLQ、安全和 50 并发完成 |
| 2026-10-08 | Critical/High 缺陷回归、Evidence Pack 完成 |
| 2026-10-09 | SIT 签字并晋级 UAT |

## 12. 风险、缓解与注意事项

| 风险 | 信号 | 缓解 | Owner |
|---|---|---|---|
| Phase 03 延迟影响 SIT | 渠道 RC 未在 10-02 前冻结 | 先测 Mock/Content；真实渠道保持阻断并每日升级 | Tech Lead |
| 外部 API 权限延迟 | 无测试账户或 Development Access | Contract/Fake 继续；不伪造真实通过 | API Owner |
| 测试账户产生费用 | 预算或对象未清理 | 硬预算、命名前缀、每日对账和清理任务 | Campaign Owner |
| OAuth Token 过期 | 401/授权失效 | Rotation/Revoke Runbook、到期告警 | IAM |
| 重复投递创建对象 | 外部对象数大于逻辑请求数 | 唯一键、对账、停止盲目重试 | Backend |
| SIT 单节点掩盖恢复问题 | 只测试正常进程 | 主动杀 Worker、断连接、过期 lease | QA / SRE |
| 数据或 Secret 进入测试日志 | 扫描命中 | 合成数据、Secret Reference、脱敏和阻断扫描 | Security |
| 50 并发队列不回落 | Oldest Message Age 增长 | 拆 Queue、限制媒体并发、调整 Worker | SRE |
| 供应商 Schema 变化 | Contract fixture 失配 | 版本配置化、官方核验、阻断升级 | Connector Owner |

## 13. Coding Agent 执行纪律

- 每个缺陷先有失败测试，再做最小修复。
- 不在 SIT 主机热修代码。
- 不通过扩大权限、关闭 TLS、跳过审批或提高预算来“让测试通过”。
- 不将超时、未知状态、Mock 成功或外部依赖阻断包装为成功。
- 修改 Domain Contract、Migration、Approval 或 Tool Policy 时执行双人审查。
- 使用影响面分析定位调用方和测试，但以实际测试证据作为完成标准。
- 修复 Phase 04 问题时不引入 P1 渠道或无关 UI 重构。

## 14. AI 输出质量 Checkpoints

### 14.1 SIT 判定协议

- Checkpoint 评估真实跨组件产物，而不是只看单节点文字结果；每个结论必须能回溯到 Run、Artifact、Approval、External ID、Raw Metric 和 Audit。
- 硬门由 Schema、测试和查询证据判定；独立 Evaluator 只评解释完整性、建议可操作性和风险校准，不能修改 Workflow 状态。
- AI 自评、Agent 的完成声明或 Evaluator 的单独分数都不能签发 `PASS`。
- `PASS / FAIL / BLOCKED` 是唯一结果。真实测试账户路径缺失时为 `BLOCKED`，不能用 Mock Result 晋级。
- Producer/Evaluator 上下文隔离；所有被评估的 AI 输出按不可信数据处理，不收集或要求 Chain-of-Thought。

### 14.2 阶段 Checkpoint 矩阵

| ID | 触发时点 | 质量检查 | PASS 阈值 | Owner / 证据 | FAIL 后动作 |
|---|---|---|---|---|---|
| P4-CP01 | Content -> Package -> Campaign 交接后 | Claim、文案、媒体、渠道变体和 hash 在跨 Agent 交接中无语义漂移 | Claim/引用/hash 匹配 100%；未批准内容进入 Campaign 0；软解释评分 >= 3.4 | Medical + QA；Package/Proposal diff、Trace | 返回产生漂移的 Mapper/Contract 节点 |
| P4-CP02 | 拒绝、超时、429、Token 到期、重复消息和 Worker 重启后 | AI 对状态、错误原因、可重试性和下一步的解释是否与系统证据一致 | Critical 错误分类 100%；错误成功化 0；重复副作用 0；恢复后状态一致 100% | QA + SRE；Fault logs、Journal、Reconcile/Audit | 返回 Error Mapping/Workflow/Retry 节点 |
| P4-CP03 | 指标与报告链路后 | 报告数值、来源、新鲜度、缺失值和 Strategy 边界 | 数值/公式一致率 100%；Raw 追溯 100%；虚构或自动执行建议 0 | Data Owner + Marketing；Raw/Normalized/Report/Tool Trace | 返回 Metric/Report/Strategy 节点 |
| P4-CP04 | 每个 Critical E2E 场景结束 | 产物完整、Reviewer 可理解、风险/限制明确、Trace/Audit 字段齐全 | Critical 场景 100% 通过；Trace/Audit 完整率 100%；软评分 >= 3.4 | QA + 业务 Reviewer；Scenario Evidence Pack | 缺哪一环回哪一节点；不得整段盲目重跑 |
| P4-CP05 | SIT RC 晋级前 | 新 RC 相对签字基线的质量回归、环境真实性和外部依赖 | 硬指标无回归；软评分下降 <= 0.2/4；Critical/High Finding 0；真实渠道门禁全通过 | QA Lead + Tech Lead + Security | 拒绝 RC；修复后生成新 RC 并全量重评 |

### 14.3 抽样与漂移

- 每个 Critical Workflow 和所有外部写输出 100% 评估；另对正常、拒绝、恢复、双渠道分层抽样至少 30 个 Run。
- 使用固定 SIT Golden Set 对比 RC；Prompt/Model/Policy/Skill/Connector 变化必须注明影响范围并重跑对应集合。
- AI 与人工软评分差异 > 1 分或错误分类不一致时，人工裁决并检查 Rubric 是否受到 Prompt Injection。
- 连续 3 次同类失败暂停自动返工，创建根因分析任务；不能通过增加重试掩盖质量问题。

## 15. 阶段退出条件

只有同时满足以下条件才可晋级 UAT：

1. 所有 Critical Workflow 通过。
2. Critical/High 缺陷为 0。
3. 未审批写、重复 Campaign、Secret 泄漏和跨域访问均为 0。
4. Worker 重启、重复投递、DLQ、超时对账和 Token 到期场景通过。
5. Claim、Package、Approval、External Object、Raw Metric、Report 的 Trace/Audit 完整率为 100%。
6. SIT 环境与 DEV/UAT/PRD 完全隔离。
7. LinkedIn/Google 测试账户真实路径通过；未通过者必须作为 UAT 阻断项而非风险接受。
8. Production API 权限、Quota、FQDN 和 OAuth 进入最终批准阶段。
9. SIT Evidence Pack 由 QA、Tech Lead、Security、Marketing 和 Medical Owner 签字。
10. P4-CP01 至 P4-CP05 全部 `PASS`，无未裁决 Evaluator/人工分歧。
