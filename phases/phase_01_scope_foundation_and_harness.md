# Phase 01：范围冻结、平台基础与共享 Harness

> 计划窗口：2026-08-27 至 2026-09-11  
> 路线图映射：原 Phase 0 + Phase 1  
> 阶段里程碑：可演示的 Fake 双 Agent Harness，支持任务暂停、人工审批、恢复、拒绝、取消和审计  
> 生产目标：企业内网 Next.js Portal + Python API/Worker；Web `8080/TCP`，API `8000/TCP`  
> 执行模式：**Repo-first Hybrid**；代码与 Fake Harness 在 GitHub 优化，DEV 基础设施和企业服务连接在受保护远端环境验证

## 1. 阶段目标

本阶段建立后续 Content Agent 和 Campaign Agent 共用的可信基础，不实现完整业务能力。

1. 冻结 2026-10-30 MVP 范围、Non-scope、外部 API Owner 和审批状态。
2. 保留现有确定性数据处理与测试资产，以渐进方式演进为 Monorepo，禁止无测试的整体重写。
3. 建立企业内部 Portal、Python Control API、Worker 和共享 `harness-core` 的代码骨架。
4. 建立 SSO/RBAC、职责分离、审批令牌、Tool Registry、Hooks、Run/Task/Workflow Journal 和不可变审计。
5. 建立 PostgreSQL 16、对象存储、任务队列、DLQ、Secret Manager 和可观测性的抽象与本地 Fake。
6. 固定 DEV/SIT/UAT/PRD 的配置、网络、数据和 Secret 隔离规则。
7. 建立 CI/CD、契约测试、Migration 验证、Secret 扫描和最小 Eval 门禁。

## 2. Scope / Non-scope

### 2.1 本阶段包含

- MVP 决策与 ADR。
- 现有代码基线、特征测试和渐进迁移。
- Next.js 内部 Portal 骨架和 Python API/Worker 骨架。
- LangGraph 单一 Workflow Runtime。
- 两个 Agent 的独立配置、Session、Tool Set、Memory Namespace 和 Service Identity。
- Fake LLM、Fake Product、Fake Media、Fake LinkedIn、Fake Google Ads。
- Run、Run Event、Task DAG、Workflow Journal、Approval、Audit 基础数据模型。
- Queue、Retry、DLQ、Idempotency、Checkpoint/Resume。
- 企业 SSO/IAM 适配器和本地 Fake Identity Provider。
- DEV/SIT/UAT/PRD 配置分层及基础设施申请清单。

### 2.2 本阶段不包含

- 真实内容生成、Medical 最终判断或真实媒体生成。
- 真实 LinkedIn / Google Ads 发布。
- Meta、Instagram、YouTube、邮件实际发送。
- 自动提高预算、扩大受众、修改竞价或删除生产 Campaign。
- CrewAI 或第二套 Workflow Runtime。
- 公网入站、供应商 Webhook 或 CDN。
- 将本地 Python 演示的内存状态、本地配置或 Bridge 进程作为生产实现。

### 2.3 GitHub Repo 与远端环境总分工

**结论：所有 Phase 的代码、测试、Eval、IaC、Migration 和 Runbook 都进入 GitHub；但 Phase 4–6 不能只靠 GitHub CI 完成验收。**

| Phase | 主执行模式 | 适合在 GitHub Repo 优化 | 必须在远端环境完成 | 仅靠 Repo 能否完成阶段 |
|---|---|---|---|---|
| Phase 01 | Repo-first Hybrid | 架构、契约、Harness、Fake Infra、CI、IaC、Migration、Unit/Contract Test | DEV SSO、PostgreSQL、Queue、Object Store、Secret、Gateway/Proxy 连通 | 否；可完成代码，不能完成企业集成门禁 |
| Phase 02 | Repo-first Hybrid | RAG/Content/Compliance 代码、Prompt/Skill、Mock Connector、Golden/Adversarial Eval | DEV/SIT Product API、Embedding、DeepSeek/即梦、对象存储和人工 Review | 否；可完成 Mock MVP，真实质量门需远端 |
| Phase 03 | Repo-first Hybrid | Campaign Contract、Dry-run、Connector、Mock、幂等/对账和指标逻辑 | DEV/SIT OAuth、LinkedIn/Google 测试账户、Proxy/FQDN 和真实发布/读取 | 否；外部写验收必须远端 |
| Phase 04 | Remote-validation Dominant | SIT 测试代码、部署 Manifest、故障注入、Evidence 模板 | SIT 部署、SSO、双渠道 E2E、Queue/Worker 恢复、50 并发 | 否 |
| Phase 05 | Remote-validation Dominant | UAT/Security/Performance 脚本、Rubric、Runbook 和 RC 修复 | UAT 业务签字、100/300 并发、安全攻击、PITR/RPO/RTO | 否 |
| Phase 06 | Controlled PRD Execution | PRD IaC、发布/回退脚本、Runbook、Dashboard/Alert 定义 | PRD 部署、Credential 注入、Pilot、Rotation、Rollback、Go-Live | 否；生产执行只能走受保护流程 |

远端环境不仅指 RHEL VM，也包括企业 Gateway、托管 PostgreSQL、Queue、Object Store、Secret Manager、SSO、监控和供应商测试/生产账户。

执行通道：

1. **普通 PR CI**：只运行无 Secret 的 Unit/Contract/Mock/Eval；不得访问 SIT/UAT/PRD 或真实外部写 API。
2. **受保护部署流水线**：使用批准分支/Tag、人工 Environment Approval 和企业内自托管 Runner；通过 OIDC/Workload Identity 获取短期身份。
3. **远端 Secret**：Secret 值仅在企业 Secret Manager；GitHub 只保存 Secret Reference、非敏感配置和 OIDC 关系，不保存长期 Token/Key。
4. **生产操作**：Coding Agent 不直接 SSH/RDP 到 PRD，不执行服务器热修或手工 SQL；部署、Migration、Smoke、回退通过受保护 CI/CD 或经审批 Runbook。
5. **Break-glass**：只有具名人类 Operations/Security 人员可使用批准 Bastion，必须有工单、命令记录、双人复核和事后审计。
6. **Evidence 回传**：远端结果只回传脱敏测试报告、hash、Trace/Audit Reference 和状态；不把 Credential、敏感日志或业务原始数据上传 GitHub。

## 3. 前置条件与立即决策

### 3.1 输入

- GitHub 仓库：`https://github.com/FelixLiangCSHI/agentic-marketing`
- 双 Agent 共享 Harness 路线图。
- Infra 申请表中的 General Info、DataCenter、NW&FireWall、Domain Name。
- Product、Medical、Marketing、IAM、Network、Security、DBA 和 Operations 的 Owner 名单。

### 3.2 2026-08-28 范围冻结门禁

| 决策 | 本计划默认值 | Owner | 未完成时处理 |
|---|---|---|---|
| 首发渠道 | LinkedIn Advertising + Google Ads | Product Owner | 阻断 Phase 3 真实接入 |
| LinkedIn Page 有机发布 | 默认延期 | Marketing | 仅保留 Connector 扩展点 |
| 邮件实际发送 | 默认延期，仅生成草稿 | Marketing / Legal | 禁止创建发送 Tool |
| LLM | DeepSeek 仅作为候选，需企业审批 | Architecture / Security | 保持 `mode: mock` |
| Embedding | 一套企业批准服务 | Architecture / Security | RAG 只做 Fake Contract |
| 媒体生成 | 即梦作为候选，只选一个正式供应商 | Marketing / Procurement | 保持 `mode: mock` |
| Product 数据 | 明确 MDM/PIM/DAM Owner、Schema、版本和批准状态 | Product Data Owner | 阻断批准 RAG |
| Medical 签字 | 指定真实 Medical Reviewer | Medical / Compliance | Agent 不得生成最终批准 |
| OAuth 回调 | 内部 HTTPS Redirect、OAuth Broker 或受控管理员授权 | IAM / Network | 阻断渠道真实授权 |

### 3.3 API 申请启动

2026-08-28 前至少完成：

- Product Data DEV 只读权限。
- SSO DEV App。
- DeepSeek/企业 LLM 与 Embedding 的内部审批申请。
- LinkedIn Marketing API 与 Google Ads Developer Token 申请。

2026-09-04 前至少完成：

- 对象存储、Queue/DLQ、Secret/KMS、监控和出站 Proxy 工单。
- LinkedIn Development Access、Google 测试账户/Token。
- 即梦正式企业 API 的区域、租户、认证方式和数据处理条款确认。

## 4. 现有仓库处理原则

### 4.1 先建立可重复基线

在独立分支或 Worktree 执行：

```powershell
git fetch origin
git switch main
git pull --ff-only
git rev-parse HEAD
npm ci
npm test
npm run lint
npm run typecheck
npm run build
python -m unittest discover -s python_tests -v
```

记录：

- HEAD SHA。
- Node.js、npm、Python 版本。
- 每条命令的通过/失败及已知基线问题。
- 当前目录树和用户已经删除的文件。不得恢复不在最新 `main` 中的旧部署资产。

如果基线失败，先记录为独立已知问题；只修复会阻断本阶段迁移的失败，不做无关重构。

### 4.2 可复用资产

| 当前区域 | 处理方式 | 约束 |
|---|---|---|
| `src/data-processing/` | 保留并增加特征测试 | 继续区分缺失值与 `0`，不静默猜测 |
| `src/analysis/` | 作为确定性指标与质量引擎基础 | 原始指标不可被模型输出覆盖 |
| `src/domain/` | 提取可复用契约，逐步迁入 `packages/domain-contracts/` | 先兼容测试，再移动 |
| `src/agents/` | 作为证据驱动 Agent 原型参考 | 拆除对内存会话和 UI 的隐式耦合 |
| `src/tests/` | 保留为回归基线 | 迁移过程中必须持续通过 |
| `python_tests/` | 仅保留仍对应本地原型的回归价值 | 不把本地演示当生产后端 |
| Next.js `src/app/` | 作为内部 Portal 起点 | 生产认证、授权和 API 调用必须服务端执行 |

### 4.3 渐进迁移而非一次性搬家

按独立 PR 执行：

1. **PR-A：基线与特征测试**
   - 不移动文件。
   - 覆盖关键解析、指标、审批失效和导出契约。
2. **PR-B：新增生产目录骨架**
   - 新增 Python API、Harness、Connector、Worker、Migration 和 Infra 目录。
   - 保持现有 Next.js 路径可运行。
3. **PR-C：提取跨语言契约**
   - 将新生产契约放入 `packages/domain-contracts/`。
   - 现有 TypeScript 代码通过兼容层消费，不做全量重写。
4. **PR-D：Portal 迁移**
   - 只有在路由、构建、测试和部署命令已更新后，才将 Web 移入 `apps/web/`。
   - 使用 `git mv` 保留历史；不要同时进行视觉重构。

## 5. 目标目录与责任边界

```text
agentic-marketing/
  apps/
    web/                         # Next.js 内部 Portal
    api/
      src/dmt_api/               # FastAPI Control API
  agents/
    content/
      agent.yaml
      prompts/
      workflows/
      policies/
      skills/
    campaign/
      agent.yaml
      prompts/
      workflows/
      policies/
      skills/
  packages/
    harness-core/
    domain-contracts/
      schemas/
    approval/
    audit/
    product-rag/
    compliance/
    connector-sdk/
    observability/
  connectors/
    llm/
    embedding/
    jimeng/
    linkedin/
    google_ads/
  workers/
    content/
    campaign/
    connector/
  migrations/
  config/
    base.yaml
    environments/
      dev.yaml
      sit.yaml
      uat.yaml
      prd.yaml
  tests/
    unit/
    contract/
    workflow/
    integration/
    security/
    performance/
  evals/
    content/
    compliance/
    campaign/
    adversarial/
  infra/
    local/
    dev/
    sit/
    uat/
    prd/
  docs/
    adr/
    runbooks/
```

`harness-core` 不包含营销 Prompt、渠道 SDK 或供应商 Secret。两个 Agent 只通过声明式配置注册 Workflow、Tools、Policies 和 Skills。

## 6. 实现步骤

### 6.1 建立工程与治理文件

新增或更新：

- `docs/adr/ADR-001-shared-harness.md`
- `docs/adr/ADR-002-langgraph-only.md`
- `docs/adr/ADR-003-approval-before-side-effects.md`
- `docs/adr/ADR-004-polling-without-public-webhooks.md`
- `docs/adr/ADR-005-controlled-facts-not-memory.md`
- `docs/adr/ADR-006-idempotent-external-writes.md`
- `CONTRIBUTING.md`
- `AGENTS.md`

`AGENTS.md` 必须要求 coding agent：

1. 先读当前实现、测试和依赖文档，再改代码。
2. 对不明确需求列出假设与阻断点，不静默选择高风险解释。
3. 使用最小实现，不为 P1 能力提前建复杂抽象。
4. 只修改当前任务所需文件，禁止顺手清理无关代码。
5. 使用 RED-GREEN-REFACTOR；先看测试失败，再写最小代码。
6. 完成前运行目标测试、类型检查、构建和影响面审查。
7. 对共享契约、Migration、Tool Policy 变更进行双人审查。

参考方法：

- Karpathy guidelines：Think Before Coding、Simplicity First、Surgical Changes、Goal-Driven Execution。
- Superpowers：设计确认、隔离 Worktree、TDD、规格审查、代码质量审查、完成前验证。
- code-review-graph：对变更符号、调用方、依赖和测试覆盖做本地影响面分析；不得替代测试。

### 6.2 建立 Python API 与 Worker 骨架

在 `apps/api/` 建立受版本锁定的 Python 项目：

- `src/dmt_api/main.py`
- `src/dmt_api/settings.py`
- `src/dmt_api/auth/`
- `src/dmt_api/routes/`
- `src/dmt_api/services/`
- `tests/`
- `pyproject.toml`

建议技术基线：

- FastAPI。
- Pydantic v2。
- SQLAlchemy 2.x。
- Alembic。
- PostgreSQL Driver。
- LangGraph。
- OpenTelemetry SDK。

版本必须锁定；新增依赖前检查许可证、维护状态和安全公告。

先实现：

- `GET /api/health/live`
- `GET /api/health/ready`
- `GET /api/v1/me`
- `POST /api/v1/runs`
- `GET /api/v1/runs/{run_id}`
- `POST /api/v1/runs/{run_id}/cancel`
- `GET /api/v1/tasks`
- `GET /api/v1/approvals`

要求：

- `/live` 只检查进程。
- `/ready` 检查数据库、Queue 和必要配置，不调用外部付费 API。
- 错误响应使用版本化结构：`code`、`message`、`trace_id`、`retryable`、`details`。
- 不向客户端返回堆栈、Secret 或供应商原始 Token。

### 6.3 建立跨语言 Domain Contract

在 `packages/domain-contracts/schemas/` 建立 JSON Schema：

- `run.v1.schema.json`
- `run-event.v1.schema.json`
- `task.v1.schema.json`
- `approval.v1.schema.json`
- `tool-call.v1.schema.json`
- `approved-content-package.v1.schema.json`
- `activation-request.v1.schema.json`
- `connector-error.v1.schema.json`

契约规则：

- `schema_version` 必填。
- ID、时间、状态使用枚举和明确格式。
- 不允许自由文本替代状态。
- 新增字段默认向后兼容；删除、改名或语义改变必须升级主版本。
- Python 使用 Pydantic 做运行时验证。
- TypeScript 使用一个选定的 JSON Schema Validator 做运行时验证。
- CI 用相同 Golden/Invalid fixtures 同时验证 Python 和 TypeScript。

### 6.4 建立 Run / Task / Workflow 持久模型

`Run` 至少包含：

```text
run_id, parent_run_id, agent_type, workflow_name, workflow_version,
tenant, business_unit, requester_id, environment, input_artifact_ids,
model_config_version, policy_version, skill_versions, status,
token_budget, cost_budget, created_at, started_at, finished_at
```

状态机：

```text
CREATED -> PLANNING -> RUNNING -> WAITING_TOOL
        -> WAITING_APPROVAL -> RETRY_SCHEDULED
        -> SUCCEEDED | FAILED | CANCELLED
        -> COMPENSATING -> COMPENSATED
```

新增 Alembic Migration，建立：

- `core.runs`
- `core.run_events`
- `core.tasks`
- `core.task_dependencies`
- `core.workflow_journal`
- `approval.requests`
- `approval.decisions`
- `approval.tokens`
- `audit.events`

约束：

- 状态变化与 Audit 写入同一事务或 Outbox。
- `run_events` 只追加，不更新历史事件。
- Task DAG 必须防循环。
- 领取任务使用租约和版本号，支持 Worker 崩溃后重新领取。
- 审计写失败时，L3/L4 Tool 必须 fail closed。

### 6.5 实现共享 Harness 最小闭环

在 `packages/harness-core/` 分模块实现：

- `loop/`：模型输出、Tool Use、Tool Result 和停止条件。
- `tools/`：类型化 Tool Registry。
- `permissions/`：deny -> policy -> approval 三层门。
- `hooks/`：输入、模型前、Tool 前后、错误、停止、Run 后。
- `context/`：最小上下文和大结果 URI。
- `memory/`：按 Agent/用户/品牌/市场隔离的稳定偏好。
- `tasks/`：Task DAG 和租约。
- `workflow/`：LangGraph Checkpoint 和 Journal。
- `goal/`：只检查结构化产物与证据，不签发 Medical 结论。

Hook 顺序固定：

1. `UserPromptSubmit`
2. `BeforeModel`
3. `PreToolUse`
4. Tool Handler
5. `PostToolUse` 或 `OnToolError`
6. `BeforeStop`
7. `AfterRun`

Tool 权限：

| Level | 动作 | 默认策略 |
|---|---|---|
| L0 | 读取批准资料、状态 | 自动允许并审计 |
| L1 | 草稿、模拟、评估 | Agent Policy 允许 |
| L2 | 收费模型、媒体任务 | 费用和并发限制 |
| L3 | 外部发布、发送、创建/修改 Campaign | 人工审批、单次 Token、幂等、对账 |
| L4 | 提高预算、扩大受众、删除/暂停生产 Campaign | MVP 禁止 |

生产 Tool Registry 禁止：

- 通用 Shell。
- 任意 URL Fetch。
- 原始数据库写入。
- 任意文件路径读写。
- 模型参数携带 Secret。
- 未注册 MCP Tool。

### 6.6 实现审批令牌和职责分离

角色：

- Requester
- Content Creator
- Medical Reviewer
- Marketing Reviewer
- Campaign Operator
- Campaign Approver
- Administrator
- Auditor

审批记录绑定：

- Approval Type、Requester、Approver。
- 角色和授权范围。
- 输入产物哈希。
- Policy、Prompt、Skill、Workflow 版本。
- 预算、渠道、账户和时间范围。
- 单次使用令牌、过期时间和撤销状态。

强制规则：

- 发起人不能批准自己的高风险操作。
- Medical Reviewer 与 Campaign Approver 分离。
- Token 使用必须原子消费。
- 输入、预算、渠道、账户、时间或哈希变化后旧审批立即失效。
- L4 在 MVP 中即使有普通审批也拒绝。

### 6.7 建立 SSO / IAM 适配层

实现两个 Provider：

- `FakeIdentityProvider`：仅本地测试，固定测试用户和组。
- `EnterpriseIdentityProvider`：OIDC 优先；如果企业只提供 SAML，则由 Gateway/Broker 转换或单独 ADR。

安全要求：

- Web 不保存长期 Access Token。
- API 验证 issuer、audience、signature、expiry、nonce/state。
- 组到角色映射由服务端配置，不相信前端声明。
- 会话 Cookie 使用 `Secure`、`HttpOnly`、`SameSite`。
- 所有写 API 有 CSRF 或同等防护。
- DEV/SIT/UAT/PRD 使用独立 SSO App 和 Redirect URI。

### 6.8 建立 Queue、DLQ、Object Storage 和 Secret 接口

接口与 Fake：

- `QueueClient` / `FakeQueueClient`
- `ObjectStore` / `FakeObjectStore`
- `SecretResolver` / `FakeSecretResolver`
- `Clock` / `FakeClock`

Queue 要求：

- 至少一次投递。
- 最大重试次数。
- 指数退避和抖动。
- DLQ 与 Poison Message 隔离。
- 幂等键去重。
- 支持取消、超时和 Worker 心跳。

对象存储键：

```text
/{environment}/{tenant}/{agent}/{run_id}/input/
/{environment}/{tenant}/{agent}/{run_id}/generated/
/{environment}/{tenant}/{agent}/{run_id}/approved/
/{environment}/{tenant}/{agent}/{run_id}/reports/
```

要求：

- KMS 加密、版本控制、MIME/大小校验、Malware Scan、生命周期和访问审计。
- 批准后资产不可原位覆盖。
- PostgreSQL 只保存 URI、哈希、元数据和 Secret Reference。
- PRD 禁止从 `.env` 加载 Secret。

### 6.9 建立配置分层

配置合并顺序：

```text
base -> environment -> agent -> workflow -> tenant/market
```

`config/base.yaml` 只放非敏感默认值。Secret 使用如下形式的引用：

```yaml
secret_ref:
  provider: enterprise_secret_manager
  name_env: DMT_SECRET_REFERENCE_NAME
```

配置加载器必须：

- 拒绝未知字段。
- 拒绝启用真实 Provider 时缺少 endpoint、auth 或 quota。
- 记录配置版本和非敏感哈希。
- 对 Secret 值脱敏，禁止日志、Trace 和错误响应回显。
- 支持 `mode: mock | sandbox | live`；默认 `mock`。

### 6.10 建立本地开发栈

在 `infra/local/` 提供：

- PostgreSQL 16。
- Queue Emulator 或本地兼容服务。
- S3-compatible Object Store Emulator。
- OpenTelemetry Collector。
- Fake Identity Provider。

规则：

- 本地只使用合成数据和 Mock Credential。
- 真实 API 必须由显式 Feature Flag 开启。
- 测试 Campaign 只能使用供应商测试账户。
- 每个 Worktree 使用独立 Compose Project、端口、数据库、Bucket Prefix 和 Queue Prefix。
- Windows 开发机不保存 PRD 数据或长期生产凭据。

### 6.11 建立 CI/CD

新增 `.github/workflows/ci.yml`，至少包含：

1. **Web**
   - `npm ci`
   - `npm test`
   - `npm run lint`
   - `npm run typecheck`
   - `npm run build`
2. **Python**
   - 锁定依赖安装。
   - Unit Test。
   - Formatter/Lint。
   - Type Check。
3. **Contracts**
   - Python/TypeScript 同一 fixtures。
   - Schema 向后兼容检查。
4. **Migration**
   - 空库升级到 head。
   - 降级一个版本。
   - 再次升级。
5. **Security**
   - Secret Scan。
   - 依赖和镜像扫描。
6. **Eval Smoke**
   - Content/Campaign 最小 Mock 场景。

`main` 始终可构建。Critical CI 失败、契约不兼容、Migration 不可回退、Secret 泄漏或 L3 权限测试失败时禁止合并。

### 6.12 建立可观测性

统一 Trace 字段：

```text
trace_id, run_id, task_id, agent_type, workflow_version,
tool_call_id, approval_id, content_package_id, campaign_id,
external_object_id, model, prompt_version, policy_version
```

最小 Dashboard：

- Run 成功/失败/取消率。
- 节点延迟。
- Tool 错误率。
- Queue Depth、Oldest Message Age、DLQ。
- Token 和费用。
- 无审批 Tool 拒绝数。
- Worker 心跳。

最小告警：

- L3/L4 Tool 无有效审批。
- DLQ 非空。
- 审计写入失败。
- 费用超过预算 80%。
- Worker 无心跳。

## 7. 测试策略

### 7.1 TDD 顺序

每个子任务按以下顺序提交证据：

1. 添加会失败的 Unit/Contract/Workflow Test。
2. 运行目标测试并保存失败原因。
3. 编写最小实现。
4. 运行目标测试直到通过。
5. 运行受影响模块测试、类型检查和构建。
6. 做规格符合性审查。
7. 做代码质量和影响面审查。

### 7.2 必测场景

- 非法 Run 状态转换被拒绝。
- Task DAG 循环被拒绝。
- L3 Tool 无审批时 100% 被拒绝。
- 过期、撤销、已使用或哈希不匹配 Token 被拒绝。
- 发起人自批被拒绝。
- Worker 在 Checkpoint 后崩溃并恢复。
- 同一消息重复投递不重复执行副作用。
- Poison Message 进入 DLQ。
- Audit 写失败时高风险 Tool fail closed。
- 两个 Agent 无法读取对方 Session、Memory 和 Credential。
- 配置或日志中不出现 Secret 明文。

## 8. 验收标准

### 8.1 代码与架构

- [ ] 最新 `main` 的原有有效测试保持通过。
- [ ] 目标目录骨架、ADR 和责任边界已建立。
- [ ] Python API 的 live/readiness 健康检查可运行。
- [ ] Python 与 TypeScript 使用同一契约 fixtures 验证。
- [ ] Run、Task、Approval、Audit Migration 可正向、回退、再正向。
- [ ] Fake Content Agent 和 Fake Campaign Agent 使用不同 Tool Set、Queue、Context 和 Credential Namespace。

### 8.2 Harness 行为

- [ ] Fake Run 可完成：创建 -> 执行 -> 等待审批 -> 批准/拒绝 -> 恢复 -> 成功/取消。
- [ ] 无审批 L3 Tool 拒绝率为 100%。
- [ ] 重复队列消息产生的重复副作用为 0。
- [ ] Worker 重启后可从持久 Checkpoint 恢复。
- [ ] 每次权限决策、Tool 调用和状态变化都有 Trace 与 Audit。

### 8.3 安全与配置

- [ ] DEV/SIT/UAT/PRD 配置、SSO App、Database、Queue、Bucket 和 Secret Namespace 独立。
- [ ] PRD 配置不能从 `.env` 读取 Secret。
- [ ] 前端无法提交或覆盖角色、审批结果、Secret 或 Tool 权限。
- [ ] 任意配置/日志/错误响应中没有真实 Key、Token、Client Secret。
- [ ] 未注册 Tool、任意 URL Fetch、通用 Shell 和原始 SQL 不在生产 Agent Tool Set。

### 8.4 可演示里程碑

演示必须包含：

1. 内部测试用户登录。
2. 创建 Fake Content Run。
3. Run 在 L3 Fake Tool 前暂停。
4. 非法自批被拒绝。
5. 合法审批后恢复。
6. Worker 重启后继续。
7. 查看 Run Timeline、权限决策、审批和审计证据。
8. 证明 Campaign Agent 无法访问 Content Agent 的私有上下文和凭据。

## 9. 基础设施验收矩阵

| 环境 | Web | Application | PostgreSQL | 入口并发 | 目标域名 |
|---|---|---|---|---:|---|
| DEV | 2 Core / 4 GB / 60 GB | 4 Core / 8 GB / 100 GB | 4 Core / 8 GB / 200 GB | 20 | `digital-marketing-dev.carstream-int.com` |
| SIT | 2 Core / 4 GB / 60 GB | 4 Core / 8 GB / 100 GB | 4 Core / 8 GB / 200 GB | 50 | `digital-marketing-sit.carstream-int.com` |
| UAT | 2 Core / 4 GB / 60 GB | 4 Core / 8 GB / 100 GB | 4 Core / 8 GB / 200 GB | 100 | `digital-marketing-uat.carstream-int.com` |
| PRD | Web x2 | API/Worker x2 | PostgreSQL 16 multi-AZ HA | 300 | `digital-marketing.carstream-int.com` |

共同约束：

- Region：SG，OS 基线：RHEL 9.7；最终版本由 IT 确认。
- 无公网入站，无 CDN。
- 内部 HTTPS Gateway/LB 在 Gateway 侧卸载证书。
- `/` -> Web `8080/TCP`。
- `/api/*` -> API `8000/TCP`。
- API/Worker -> PostgreSQL HA Endpoint `5432/TCP`。
- 外部服务只允许经批准 Proxy/NAT 的 `443/TCP` 出站。
- 数据库 TLS、静态加密、PITR、30 天备份保留和恢复测试。
- SLA 99.5%，RPO 不高于 15 分钟，RTO 不高于 2 小时。

## 10. 时间估算与里程碑

建议投入：范围冻结 2 个工作日，平台与 Harness 10 个工程工作日；Phase 2 可在共享契约稳定后并行启动。

| 日期 | 里程碑 |
|---|---|
| 2026-08-27 | 仓库基线、差距清单、Owner 和风险台账 |
| 2026-08-28 | MVP 范围、Agent 边界、首发渠道、供应商候选和 API 申请冻结 |
| 2026-09-04 | 目录骨架、契约、Migration、Fake Infra、配置加载和 CI 可运行 |
| 2026-09-08 | Tool Registry、Permission、Hooks、Approval 和 Audit 闭环 |
| 2026-09-11 | Checkpoint/Resume、Queue/DLQ、隔离和阶段演示通过 |

## 11. 风险、缓解与注意事项

| 风险 | 触发信号 | 缓解 | Owner |
|---|---|---|---|
| 用户正在清理仓库，基线变化 | 文件在实施中消失或移动 | 每个 PR 前拉取最新 `main`；不恢复用户删除内容 | Tech Lead |
| 一次性 Monorepo 重构导致回归 | 大量无关 diff、测试路径失效 | 按 PR-A 至 PR-D 渐进迁移 | Tech Lead |
| API 审批晚 | 无 DEV Credential 或测试账户 | Fake Connector + Contract Test 并行；真实晋级保持阻断 | Product Owner |
| SSO/OAuth 无公网回调受阻 | 供应商拒绝内部 Redirect | OAuth Broker 或受控管理员授权 POC | IAM / Network |
| Agent 越权 | Tool Set 或 Credential 混用 | 独立 Namespace、Service Identity 和负向测试 | Security |
| Audit 不可靠 | 高风险动作无证据 | Audit fail closed + Outbox + 告警 | Backend / SRE |
| 双 Workflow Runtime 膨胀 | 引入 CrewAI 依赖或状态 | ADR 明确 MVP 只用 LangGraph | Architect |
| 新依赖过多 | 构建时间和漏洞增加 | 每个依赖需说明用途；优先标准库和已有组件 | Tech Lead |

## 12. AI 输出质量 Checkpoints

### 12.1 统一判定协议

本阶段所有由 AI 生成的计划、代码、Schema、Tool 决策和停止结论都必须经过以下三层检查：

1. **硬性检查**：Schema、测试、权限、Secret、状态机和引用完整性；任一失败即 `FAIL`。
2. **独立评估**：使用确定性规则或独立 Evaluator Run 按冻结 Rubric 评分；Evaluator 不继承 Producer 的对话、Memory、工具权限或结论。
3. **人工复核**：Tech Lead、Security、QA 或业务 Owner 审核高风险产物；AI 自评和自然语言“已完成”不能签发 `PASS`。

每个 Checkpoint 只允许：

- `PASS`：硬门全部通过，评分达到阈值，必需人工签字齐全。
- `FAIL`：输出或证据不达标，必须返回指定节点返工。
- `BLOCKED`：外部依赖或评审人缺失；不得伪装成 `PASS` 或静默降级。

保存 `quality_checkpoint_result.v1`：

```text
checkpoint_id, run_id, artifact_ids, artifact_hashes,
producer_model, prompt_version, policy_version, skill_versions,
rubric_version, dataset_version, evaluator_version,
hard_gate_results, dimension_scores, violations,
decision, reviewer_id, evidence_refs, created_at
```

只保存输出、证据和评分，不保存或要求模型 Chain-of-Thought。软质量维度使用 0–4 分，默认加权平均不低于 3.4，且任何维度不低于 3；Owner 可在首次评估前提高阈值，不能在看到结果后降低。

### 12.2 阶段 Checkpoint 矩阵

| ID | 触发时点与检查对象 | 质量检查 | PASS 阈值 | Owner / 必需证据 | FAIL 后动作 |
|---|---|---|---|---|---|
| P1-CP01 | 范围、ADR、目录和实施计划冻结后 | 需求覆盖、Non-scope、依赖、路径、验收命令、无虚构现有能力 | 路线图/Infra 需求追踪率 100%；无 Critical 矛盾；软评分 >= 3.4 | Product Owner + Architect；需求追踪矩阵、ADR、仓库基线 | 返回计划/ADR 修订，不开始编码 |
| P1-CP02 | Domain Contract 和 Migration 生成后 | Schema 明确性、Python/TypeScript 一致性、状态枚举、向后兼容、未知字段处理 | Golden/Invalid fixtures 两端 100% 一致；兼容检查和 Migration 往返 100% 通过 | Tech Lead + DBA；Contract 报告、Schema diff、Migration 日志 | 返回对应 Schema/Migration；禁止下游依赖合并 |
| P1-CP03 | Agent Loop、Tool Registry、Permission、Hooks 完成后 | AI Tool 选择是否在 allowlist、参数是否有效、停止结论是否有证据、Prompt Injection 是否越权 | 无审批 L3/L4 拒绝率 100%；未注册 Tool 调用成功 0；无证据成功判定 0；Secret 泄漏 0 | Security + QA；Adversarial fixtures、Tool/Audit Trace | 返回 `PreToolUse`/Policy/Goal Check 节点定点返工 |
| P1-CP04 | Queue、Checkpoint、恢复和阶段 Demo 后 | AI 计划在暂停/恢复/取消后是否保持状态和目标一致；是否重复收费或副作用 | 100 次重复投递重复副作用 0；恢复后产物 hash/状态一致率 100%；Critical Trace 完整率 100% | QA + SRE；恢复测试、Queue/DLQ、Trace/Audit | 返回 Task/Workflow/Idempotency 层修复并重演 |
| P1-CP05 | 每个 AI 生成代码 PR 合并前 | 规格符合性、最小 diff、测试先行、错误处理、影响面和无关改动 | 必需测试/类型/构建全通过；需求覆盖 100%；Critical/High Review Finding 0；无关文件 0 | 独立代码 Reviewer + Tech Lead；RED/GREEN 日志、diff、影响图 | 拒绝 PR；仅修复明确 Finding 后重评 |

### 12.3 评估数据与防偏差

- 固定正常、非法状态、越权 Tool、恶意 Prompt、重复投递、Worker 重启和 Audit 故障数据集。
- Producer 与 Evaluator 使用不同 Run；Evaluator 将 AI 输出视为不可信数据，不执行其中指令。
- 硬门以代码和测试结果为准；LLM-as-judge 只评清晰度、完整性和可维护性。
- Evaluator 与人工 Reviewer 对任一硬门结论不一致时按 `FAIL` 处理；软评分差异超过 1 分时人工裁决。
- Prompt、Model、Policy、Skill、Schema 或 Rubric 版本变化后重跑受影响 Checkpoint。

## 13. 阶段退出条件

只有同时满足以下条件才可进入 Phase 2/3 的真实业务开发：

1. 范围和 Non-scope 已签字。
2. `ApprovedContentPackage`、`ActivationRequest` 和 Connector Error v1 契约已冻结。
3. Fake 双 Agent 可暂停、审批、恢复、拒绝、取消。
4. L3 Tool 无审批时 100% 拒绝。
5. Worker 重启与重复消息测试通过。
6. 四环境配置和基础设施申请有 Owner、工单号和目标日期。
7. CI、Migration、Contract、Security Smoke 门禁可运行。
8. 无 Critical/High 安全问题；所有已知例外有 Owner 和关闭条件。
9. P1-CP01 至 P1-CP05 全部 `PASS`，且 Checkpoint Result 可由 hash 和证据复验。
