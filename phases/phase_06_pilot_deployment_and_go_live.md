# Phase 06：受控 Pilot、PRD 部署与生产上线

> 计划窗口：2026-10-19 至 2026-10-30  
> 路线图映射：原 Phase 6 + Phase 7  
> 阶段里程碑：完成小范围真实 Campaign、生产切换、回退演练和 Hypercare，在 2026-10-30 前进入受控正式运行  
> 生产域名：`https://digital-marketing.carstream-int.com`  
> 执行模式：**Controlled PRD Execution**；Repo 保存可审查定义，所有生产动作通过受保护 CI/CD 或具名人工 Runbook 在 PRD 执行

## 1. 阶段目标

1. 将 UAT 签字的不可变 Release Candidate 部署到隔离的 PRD HA 拓扑。
2. 注入经批准的 Production Credential、Quota、FQDN、Secret Reference 和费用上限。
3. 完成小范围真实 Pilot，验证审批、发布、对账、指标、告警、Token Rotation、备份/PITR 和回退。
4. 建立可执行的发布、暂停、应急撤销、供应商故障、数据恢复和业务沟通 Runbook。
5. 2026-10-23 完成 Go/No-Go 门禁；2026-10-26 起受控开放生产流量。
6. 2026-10-30 前完成 Hypercare、问题复盘、业务移交和上线签字。

## 2. Scope / Non-scope

### 2.1 本阶段包含

- PRD Web x2、API/Worker x2、PostgreSQL 16 multi-AZ HA。
- 独立 PRD SSO App、Database、Queue/DLQ、Object Store、Secret、OAuth Client、模型 Project 和渠道账户。
- 内部 Gateway/LB、TLS、Health Check 和路径路由。
- Production Credential 注入、Rotation 和应急撤销。
- 受控真实 LinkedIn/Google Ads Campaign。
- DeepSeek/即梦在正式审批完成时的生产调用；未完成则保持关闭并采用已批准降级范围。
- Production Smoke、Pilot、逐步开放、Dashboard、Alert、Runbook、Rollback。
- Hypercare、问题分级、每日复盘和 Operations 移交。

### 2.2 本阶段不包含

- Meta、Instagram、YouTube、邮件实际发送或其他延期渠道。
- 自动增加预算、修改竞价、扩大受众、自动暂停/删除生产 Campaign。
- 第二媒体供应商或第二 Workflow Runtime。
- 公网入站、供应商 Webhook 或 CDN。
- 在生产服务器手工改代码、配置或数据库。
- 使用 UAT/DEV Credential 顶替 PRD Credential。
- 在上线窗口引入非阻断型功能或视觉改版。

### 2.3 GitHub Repo 与 PRD 远端分工

| GitHub Repo 保留 | PRD 远端执行 |
|---|---|
| 签字后的应用代码、IaC、Migration、配置 Schema、发布/Smoke/回退脚本、Runbook、Dashboard/Alert 定义 | Infra Preflight、Migration、Web/API/Worker 滚动部署、Gateway/LB 健康检查 |
| Release Manifest、SBOM、image digest、变更记录和脱敏 Evidence 模板 | Production Credential/Workload Identity 注入、真实渠道 Pilot、Token Rotation/Revoke |
| Kill Switch/Queue Pause 的声明式配置及验证测试 | PITR、Rollback、Vendor Outage、Go/No-Go、分批开放和 Hypercare |

生产访问规则：

1. Coding Agent 和普通 GitHub Actions Runner 不得获得 PRD SSH/RDP、数据库管理员、Secret Manager 读取或渠道生产写权限。
2. 生产部署只能由签名 Tag/固定 digest 触发受保护 Pipeline，并要求 Operations + Business/Security 的 Environment Approval。
3. 优先使用企业内自托管 Runner、OIDC/Workload Identity 和短期凭据；禁止把长期 PRD Key 放入 Repo、Workflow YAML、普通 GitHub Secret 或构建 Artifact。
4. Migration、Smoke、Pilot 和 Rollback 使用 Repo 中经过评审的幂等脚本；远端禁止手工 SQL、热修代码和覆盖镜像 Tag。
5. Break-glass 仅限具名人类 Operations/Security，经 Bastion、工单和双人复核；Coding Agent 只可分析脱敏证据并生成待审批建议。
6. PRD 日志、Trace、审计和业务数据保留在企业系统；GitHub 只接收状态、hash、脱敏报告和 Evidence Reference。
7. Phase 06 是远端执行阶段：Repo 合并完成不等于上线，必须由真实 PRD Preflight、Pilot、Rotation、Rollback 和人类 Go/No-Go 证明。

## 3. 前置条件与 Go/No-Go 门禁

### 3.1 UAT 退出条件

必须全部满足：

- Marketing、Medical、Security、Architecture、Operations、QA 签字。
- Critical/High 缺陷为 0。
- 100/300 并发和 PRD Sizing 通过。
- RPO <= 15 分钟、RTO <= 2 小时有实际演练证据。
- 未审批写、重复对象、Secret 泄漏、跨域访问为 0。
- Token Rotation/Revoke、Backup/PITR、Vendor Outage 和回退 Runbook 通过。
- 最终 RC 有 commit SHA、image digest、SBOM、Migration revision 和 Evidence Pack。

### 3.2 2026-10-16 API 门禁

所有首发 API 必须具备：

- PRD Credential 或 Workload Identity。
- Production Access Tier。
- 批准 Quota 和费用上限。
- 精确 FQDN Allowlist。
- Security/Legal/Procurement 审批。
- Token Rotation、Revoke 和离职处理。
- Vendor SLA 和 Incident Contact。

未完成的 Provider：

- 不得启用 `live`。
- 不得在 Pilot 临时降低安全门槛。
- Product Owner 必须选择已批准的降级范围或 No-Go。

### 3.3 2026-10-23 Go/No-Go

| 门禁 | Go 条件 | No-Go 条件 |
|---|---|---|
| Release | SHA、digest、SBOM、Migration 冻结 | 任一无法复现 |
| Security | 无 Critical/High；Secret Scan 通过 | 未关闭发现或凭据泄漏 |
| Business | Pilot 场景和预算获批 | 无 Owner/Approver |
| Medical | 内容包和 Claims 已签字 | Claim/引用/有效期不完整 |
| External APIs | PRD 权限、Quota、FQDN、Token 有效 | 使用测试权限或未核验配置 |
| Reliability | HA、PITR、RPO/RTO、Rollback 演练通过 | 恢复或回退失败 |
| Operations | Dashboard、Alert、Runbook、值班就绪 | 告警无 Owner 或无法执行 |
| Data | Retention、Encryption、Audit、Backup 就绪 | 数据分类或删除策略未批准 |

No-Go 不得通过口头豁免改成 Go。任何例外需要书面 Risk Acceptance、Owner、到期日和补偿控制；未审批外部写、Medical 风险、Secret 泄漏、数据丢失和无法回退不可接受。

## 4. PRD 目标架构

### 4.1 计算与数据

| Role | 数量 | 端口 | 要求 |
|---|---:|---|---|
| Web | 2 | 8080/TCP | 同镜像、不同实例、Gateway/LB 健康检查 |
| API/Worker | 2 | 8000/TCP；443 出站 | API 与各 Queue Worker 使用独立进程/并发 |
| PostgreSQL | multi-AZ HA | 5432/TCP | 单一 HA Endpoint、TLS、PITR、30 天备份 |

基线：

- Region：SG。
- OS：RHEL 9.7 基线，最终小版本由 IT 确认。
- SLA：99.5%，服务窗口 9:00–23:00（周一至周日）。
- RPO：不高于 15 分钟。
- RTO：不高于 2 小时。
- 数据增长：100–500 GB/年。
- 媒体和大型产物进入对象存储，不进入 VM 本地磁盘或 PostgreSQL Large Object。

### 4.2 网络

```text
Internal User
  -> Internal HTTPS Gateway/LB :443
     -> /       -> Web back pool :8080
     -> /api/*  -> API back pool :8000

API/Worker
  -> PostgreSQL HA private endpoint :5432
  -> Queue/Object Store/Secret/Monitoring private endpoints
  -> Approved HTTPS Proxy/NAT :443
     -> approved external API FQDNs only
```

要求：

- 无公网入站。
- 无 CDN。
- Gateway 侧证书卸载；后端链路按公司标准加密。
- 外部服务不得绕过 Proxy/NAT。
- 每个 FQDN 有业务用途、Owner、批准记录和流量日志。
- 任何供应商要求公网 Callback/Webhook 时必须单独安全评审，不得开放现有 `/api/*`。

### 4.3 环境隔离

PRD 不与 DEV/SIT/UAT 共享：

- SSO App。
- Database/Schema Role。
- Bucket/Prefix 和 KMS Key。
- Queue/DLQ。
- Secret Namespace。
- OAuth Client/Redirect URI。
- 渠道账户。
- 模型 Project、Quota 和费用预算。
- Service Account。
- Log/Metric/Trace/Audit 索引。

## 5. 交付物与目标路径

```text
infra/prd/
  deployment/
  config/
  network/
  observability/
  backup/
docs/
  runbooks/prd-deployment.md
  runbooks/prd-smoke-test.md
  runbooks/campaign-kill-switch.md
  runbooks/channel-token-rotation.md
  runbooks/vendor-outage.md
  runbooks/queue-dlq.md
  runbooks/backup-pitr.md
  runbooks/rollback.md
  runbooks/security-incident.md
  runbooks/hypercare.md
  release/go-no-go.md
  release/production-signoff.md
scripts/release/
  verify_config.py
  preflight.py
  smoke_test.py
  reconcile_pilot.py
  verify_rollback.py
tests/
  smoke/prd/
  pilot/
  recovery/prd/
```

脚本必须幂等、默认只读，并要求显式 `--confirm-production` 才允许生产写。脚本日志不得打印 Secret。

## 6. 实现步骤与发布

### 6.1 冻结 Production Release

记录：

- Git commit SHA 和签名 Tag。
- Web/API/Worker image digest。
- SBOM 和依赖扫描结果。
- Alembic Migration revision。
- Domain Contract 版本。
- Prompt/Model/Policy/Skill/Workflow 版本。
- DeepSeek、即梦、LinkedIn、Google Ads Connector 版本。
- 非敏感配置 hash。
- Feature Flag 和 Kill Switch 默认值。

冻结后只接受：

- 阻断上线的缺陷修复。
- Security/Operations 明确要求的配置修正。
- Runbook 和证据修正。

每次代码变化都创建新 Release Candidate 并重新跑 Critical 门禁。

### 6.2 验证 PRD 基础设施

`scripts/release/preflight.py` 只读检查：

- DNS、TLS、Gateway/LB、Web/API Health。
- Web x2、API/Worker x2 实例和健康状态。
- PostgreSQL HA Endpoint、TLS、备份、PITR、Role。
- Queue/DLQ、Retention、并发和 Worker Identity。
- Object Store、KMS、Versioning、Lifecycle、Malware Scan。
- Secret Manager Namespace 和 Access Policy。
- Log/Metric/Trace/Audit、Dashboard 和 Alert。
- Proxy/NAT、静态出口 IP 和 FQDN Allowlist。
- SSO App、Redirect/Logout URI 和角色组。

检查失败即退出非零，不执行任何修改。

### 6.3 生产 Secret 与 Credential 注入

顺序：

1. 创建 PRD Secret Reference，不在流水线参数中传 Secret 值。
2. 由企业 Secret Manager 向对应 Service Identity 授权。
3. Connector 启动时解析引用并验证最小权限。
4. 运行只读 Credential Health Check。
5. 记录 Secret 版本、创建/到期时间和 Owner，不记录值。

渠道要求：

- LinkedIn 使用批准的 Production App、3-legged OAuth、最小广告/报告权限和 API version 配置。
- Google Ads 使用批准的 Developer Token；企业自有账户才可在 IAM/Security 批准后使用 Service Account/Workload Identity，否则使用 OAuth。
- DeepSeek/即梦只有在数据处理、区域、训练、保留和 Quota 均批准后启用。
- Refresh Token、AK/SK、Client Secret、Developer Token 不进入 Prompt、UI、日志、Trace 或数据库明文。

### 6.4 数据库 Migration 与回退准备

上线前：

- 对当前 PRD 空库/预置 Schema 运行 Migration Dry-run。
- 生成 Schema diff 和锁影响报告。
- 创建并验证上线前备份/恢复点。
- 确认向后兼容窗口：旧 API/Worker 与新 Schema 可在滚动部署期间共存。
- 对不可逆 Migration 使用 expand -> migrate -> contract，不在同一上线窗口删除旧列。

执行：

1. 暂停会产生冲突的后台任务。
2. 记录 Queue watermark。
3. 运行向后兼容 Migration。
4. 验证 Schema、Role 和审计。
5. 部署 API/Worker。
6. 恢复 Queue。

数据库回退不得使用破坏性命令。若已产生新数据，优先关闭新 Feature、回滚应用并保留兼容 Schema，后续经过评审再收缩。

### 6.5 部署顺序

通过企业 CI/CD 执行，不在服务器手工操作：

1. 配置和 Secret Preflight。
2. Database Migration。
3. Observability Collector/Config。
4. API 节点 1，再节点 2。
5. Content/Campaign/Connector Worker；初始消费暂停。
6. Web 节点 1，再节点 2。
7. Gateway/LB Health Check。
8. 只读 Smoke。
9. 恢复 Worker 消费。
10. 外部写 Kill Switch 保持关闭，直到 Pilot 获批。

每步失败自动停止后续步骤，并保留当前状态和证据。

### 6.6 Production Smoke Test

`scripts/release/smoke_test.py` 默认只读：

- 内部 SSO 登录和角色映射。
- `/api/health/live`、`/api/health/ready`。
- Run/Task/Approval 查询。
- PostgreSQL、Queue、Object Store、Secret Reference、Trace。
- Product 只读检索。
- DeepSeek/即梦/LinkedIn/Google Ads Credential Health；不创建付费/外部对象。
- Web/API 双节点轮询健康。

获批准的写 Smoke 使用专用 Production Pilot Account：

- 一个已批准 Content Package。
- 最小允许预算。
- 单一 LinkedIn 和 Google Ads 测试/Pilot 对象。
- Approval Token、input hash、idempotency key。
- 发布后立即对账和记录外部 ID。
- 按批准计划暂停/结束；L4 操作由人工 Runbook 执行。

### 6.7 2026-10-19 至 2026-10-23 受控 Pilot

Pilot 边界：

- 只对指定内部用户开放。
- 只使用已批准产品、市场、语言和渠道。
- Campaign 数量、预算、受众和时间有硬上限。
- DeepSeek/即梦每日费用有硬上限。
- 所有外部写仍逐次人工审批。
- 自动优化、自动互动和邮件发送保持关闭。

每日执行：

1. 上午检查 Credential、Quota、Queue、DLQ、Policy/Skill/Package 过期。
2. 提交批准的 Content 任务。
3. Medical/Marketing 审核。
4. Campaign Draft、Dry-run 和 Campaign Approval。
5. 发布、对账和外部对象清单。
6. 指标拉取、新鲜度和报告。
7. 费用、告警、缺陷和风险复盘。

Pilot 成功标准：

- 未审批写：0。
- 重复 Campaign/媒体 Job：0。
- Critical Claim 逃逸：0。
- Secret 泄漏：0。
- 所有外部写有 Approval、Hash、Idempotency、External ID、Reconcile 和 Audit：100%。
- Queue/DLQ、费用和 Quota 在批准阈值内。

### 6.8 Token Rotation 与应急撤销

在 2026-10-23 前实际演练：

1. 创建新 Credential/Token 版本。
2. 更新 Secret Reference。
3. 滚动刷新 Connector/Worker。
4. 验证新版本可用。
5. 撤销旧版本。
6. 验证旧版本调用失败。
7. 记录 Audit、时间和 Owner。

应急撤销验证：

- 关闭外部写 Kill Switch。
- 暂停对应 Connector Queue。
- 撤销渠道/模型 Credential。
- 保持只读 Portal、Audit 和对账能力。
- 通知 Security、Business Owner 和 Vendor。

### 6.9 Dashboard 与告警上线

生产 Dashboard：

- Availability 和 Gateway/Web/API 健康。
- Run 成功/失败/取消率。
- 节点延迟。
- Queue Depth、Oldest Message Age、DLQ。
- Worker 心跳、CPU、Memory。
- DB HA、连接、IOPS、慢查询、备份。
- Tool 429/5xx/超时/熔断。
- Token、模型、媒体和 Campaign 费用。
- OAuth/Policy/Skill/Package 到期。
- Audit 写入。

Critical 告警：

- 无有效审批的 L3/L4 Tool。
- 外部写未知且无法对账。
- 重复外部对象。
- 未批准 Claim 进入 Package。
- Secret/DLP 命中。
- Audit 写失败。
- PRD Worker 无心跳。
- DLQ 非空。
- DB HA/备份失败。

每个告警必须有 Owner、值班、Runbook、通知渠道、去重和升级时间。

### 6.10 上线前回退演练

演练：

- 回滚 Web/API/Worker 到上一镜像 digest。
- Feature Flag 关闭新 Workflow。
- 外部写 Kill Switch。
- Queue 暂停和安全 Replay。
- 兼容 Schema 下应用回退。
- Object Store 版本恢复。
- PostgreSQL PITR。
- Token 撤销和替换。

回退触发：

- 未审批外部写。
- 重复 Campaign。
- Critical Medical Claim。
- Secret 泄漏。
- 跨 Tenant/环境。
- 数据损坏或 Audit 丢失。
- 无法在批准窗口内对账的外部写。
- Availability、Queue 或 DB 指标超过 Go/No-Go 阈值。

回退后：

- 不删除证据。
- 保留 Run、Approval、Audit 和 External ID。
- 对外部对象进行人工对账。
- 创建 Incident 和复盘。

### 6.11 2026-10-26 至 2026-10-30 生产上线

#### 10 月 26 日：配置冻结与最终 Smoke

- 核对 Release Manifest。
- 核对 Production Credential、Quota、FQDN、预算。
- 核对值班和 Vendor 联系人。
- 执行只读 Smoke 和最小写 Smoke。
- Go/No-Go 签字。

#### 10 月 27–28 日：受控业务开放

- 分批开放内部用户/业务单元。
- 每批开始前检查 Queue、DLQ、费用、Token 和 Alert。
- 保持外部写逐次审批。
- 每批后对账外部对象和原始指标。

#### 10 月 29 日：稳定性确认

- 验证 99.5% SLA 指标。
- 验证备份、PITR、Queue、Worker、Token 到期告警。
- 清理已批准的 Pilot 测试对象。
- 关闭所有 Critical/High 问题。

#### 10 月 30 日：正式移交

- Product/Marketing、Medical、Security、Architecture、Operations、QA 签字。
- 移交 Dashboard、Runbook、值班、Access Review 和 Vendor 联系人。
- 发布已知限制和 P1 Backlog。
- 启动上线后定期 Access、Policy、Model、Skill、Quota 和成本审查。

### 6.12 Hypercare

上线周每日：

- 09:00 健康、备份、Credential、Quota、Queue 检查。
- 业务时段持续监控 Critical Alert。
- 每个生产外部写抽样核对 Approval/Hash/Idempotency/Reconcile。
- 17:00 缺陷、费用、供应商和风险复盘。
- 形成日结报告和次日行动。

严重度：

| Severity | 示例 | 响应 |
|---|---|---|
| SEV-1 | 未审批发布、Secret 泄漏、Critical Claim、跨 Tenant、数据丢失 | 立即 Kill Switch/Incident/回退 |
| SEV-2 | 重复对象、主要路径不可用、无法对账 | 暂停对应 Queue/渠道并修复 |
| SEV-3 | 有安全绕行的局部问题 | 当日评估和计划 |
| SEV-4 | 非关键 UI/文档 | 进入 Backlog |

## 7. 发布验证命令

只通过受控流水线运行，以下为脚本接口约定：

```powershell
python scripts\release\verify_config.py --environment prd
python scripts\release\preflight.py --environment prd --read-only
python scripts\release\smoke_test.py --environment prd --read-only
python scripts\release\verify_rollback.py --environment prd --dry-run
```

获批 Pilot 写入：

```powershell
python scripts\release\smoke_test.py `
  --environment prd `
  --pilot-manifest-ref "secret://dmt/prd/pilot/manifest" `
  --confirm-production
```

要求：

- `--confirm-production` 不得由默认值或 CI 普通分支自动添加。
- Pilot Manifest 绑定账户、产品、预算、受众、审批和截止时间。
- 脚本执行前再次验证 Approval Token 和 input hash。
- 日志只显示 Secret Reference，不显示值。

## 8. 验收标准

### 8.1 PRD 基础设施

- [ ] Web x2、API/Worker x2、PostgreSQL HA 正常。
- [ ] Gateway `/` 和 `/api/*` 路由、TLS、Health Check 通过。
- [ ] 无公网入站、无 CDN、外部请求只经批准 Proxy/NAT。
- [ ] Database、Queue、Bucket、Secret、SSO、OAuth、渠道账户和模型 Project 与非生产隔离。
- [ ] 备份/PITR 30 天保留和恢复验证通过。

### 8.2 Pilot 与业务

- [ ] LinkedIn/Google Ads 小范围真实 Pilot 通过。
- [ ] 最终 Claim 来源覆盖率 100%，Critical Claim 逃逸 0。
- [ ] 未审批写 0，L4 自动执行 0。
- [ ] 重复 Campaign/媒体 Job 0。
- [ ] 所有外部写的 Approval/Hash/Idempotency/Reconcile/Audit 完整率 100%。
- [ ] Strategy 只生成草稿。

### 8.3 安全与运维

- [ ] Production Credential、Quota、FQDN、Security/Legal 审批完成。
- [ ] Secret 泄漏、跨 Tenant/环境访问 0。
- [ ] Token Rotation 和旧 Token 撤销演练通过。
- [ ] Kill Switch、Queue Pause、Credential Revoke、Rollback 可执行。
- [ ] Critical Alert 均有 Owner、值班和 Runbook。
- [ ] Audit 写失败时高风险 Tool 100% fail closed。

### 8.4 SLA 与恢复

- [ ] 业务服务 SLA 99.5% 的监控和报告已启用。
- [ ] RPO <= 15 分钟。
- [ ] RTO <= 2 小时。
- [ ] 单 Web/App/Worker 节点故障后服务和任务恢复。
- [ ] DB/Queue/Object Store/Vendor 故障 Runbook 通过。

### 8.5 上线签字

- [ ] 2026-10-23 Go/No-Go 签字完成。
- [ ] 2026-10-26 配置冻结和最终 Smoke 通过。
- [ ] 2026-10-30 Product、Marketing、Medical、Security、Architecture、Operations、QA 完成移交签字。
- [ ] 已知限制、风险和 P1 Backlog 已发布。

## 9. Production Evidence Pack

至少包含：

- Release Manifest：SHA、Tag、digest、SBOM、Migration。
- Config/Prompt/Model/Policy/Skill/Workflow/Connector 版本。
- PRD Infra、Network、DNS、TLS、SSO、Database、Queue、Object Store、Secret 证明。
- Production API、Quota、FQDN、Credential 和审批。
- Pilot Approval、Campaign ID、Reconcile 和清理记录。
- Smoke、Rotation、Revoke、Rollback、PITR、RPO/RTO 结果。
- Dashboard、Alert、On-call 和 Vendor Contact。
- Hypercare 日报。
- 最终签字。

Evidence 存放于受控文档/审计系统，按公司政策保留和删除，不提交真实 Secret 或敏感原始响应。

## 10. 时间估算与里程碑

建议投入：10 个工程工作日；前 5 个工作日完成 Pilot 和 Go/No-Go，后 5 个工作日完成分批上线和 Hypercare。

| 日期 | 里程碑 |
|---|---|
| 2026-10-19 | PRD Infra、Release Manifest、Preflight、配置和 Credential 就绪 |
| 2026-10-20 | 部署、Migration、只读 Smoke、Dashboard/Alert |
| 2026-10-21 | 最小真实 Pilot、外部对象对账、费用检查 |
| 2026-10-22 | PITR、Rollback、Vendor Outage、Kill Switch 演练 |
| 2026-10-23 | Token Rotation/Revoke、Go/No-Go 签字 |
| 2026-10-26 | Production 配置冻结和最终 Smoke |
| 2026-10-27 | 第一批内部用户/业务流量 |
| 2026-10-28 | 第二批流量、指标和容量复核 |
| 2026-10-29 | SLA、备份、告警、问题关闭和移交准备 |
| 2026-10-30 | 正式签字、Operations 移交和 Hypercare 总结 |

## 11. 风险、缓解与注意事项

| 风险 | 触发信号 | 缓解 | Owner |
|---|---|---|---|
| PRD 资源未按时交付 | 节点/VIP/域名/DB 缺失 | 每日升级 IT；无 HA 不上线 | PM / Infra |
| Production API 权限/Quota 未完成 | Credential 或 Access Tier 缺失 | 对应 Provider 保持关闭；No-Go 或批准降级范围 | API Owner |
| Pilot 产生超预算费用 | 费用/Quota 快速增长 | 硬预算、80% 告警、100% 停止 | Marketing / SRE |
| 外部写结果未知 | 超时且无法对账 | 暂停 Queue、人工对账、禁止重复创建 | Campaign Owner |
| Token 泄漏/过期 | DLP 命中、401 增加 | Kill Switch、Revoke、Rotate、Incident | Security |
| Migration 影响服务 | 锁等待/不兼容 | Expand/Migrate/Contract、备份、应用回退 | DBA |
| 单节点失效暴露共享状态 | 任务丢失或重复 | Queue lease、Checkpoint、幂等、HA 演练 | SRE |
| Medical/Marketing 临时变更 | 已批准内容需修改 | 新版本和重新审批；不原位修改 | Product Owner |
| 上线窗口引入新功能 | 非阻断 PR 请求 | Freeze；进入 P1 Backlog | Tech Lead |
| Runbook 无法执行 | 演练失败/Owner 缺席 | No-Go；修正后重演 | Operations |

## 12. Coding Agent 执行纪律

- 上线阶段默认不写代码；优先配置、验证、Runbook 和证据。
- 必须修复时先复现、加失败测试、做最小 diff、跑完整 Critical 回归并生成新 RC。
- 不热修服务器，不手工改数据库，不覆盖镜像 Tag。
- 不通过关闭审批、审计、TLS、DLP、限流或预算来恢复服务。
- 未知外部写先对账，不盲目重试。
- 不把失败包装为成功，不用测试 Credential 顶替生产 Credential。
- Contract、Migration、Approval、Policy、Secret 和 Network 变化必须双人审查。
- 回退和 Incident 保留全部证据，不删除 Run/Audit/External ID。

## 13. 项目 Definition of Done

项目只有同时满足以下条件才算按期交付：

1. 两个 Agent 在同一 DMT 平台独立运行和扩缩。
2. 两个 Agent 不共享对话、Memory 和外部写 Credential。
3. Content Agent 只使用批准、未过期、未撤销的 Product 资料。
4. 所有最终 Claim 有可验证引用。
5. 未通过 Medical 和人工审批的内容技术上无法进入 Campaign。
6. Campaign Agent 只消费批准且哈希匹配的内容包。
7. 所有外部写有 Approval Token、input hash、idempotency key 和 reconcile 证据。
8. Retry 和重复消息不产生重复 Campaign 或发送。
9. Prompt、Model、Skill、Policy、Tool、Approval 和 Connector 版本可追溯。
10. Worker 重启后 Workflow 可恢复。
11. DEV/SIT/UAT/PRD 数据、Secret、OAuth App、Queue 和账户相互隔离。
12. Security、Medical、Marketing、Architecture、Operations、QA 签字。
13. 99.5% SLA、RPO <= 15 分钟、RTO <= 2 小时完成验证。
14. Production API、Quota、FQDN、Token Rotation、Rollback 和 Hypercare 就绪。

## 14. AI 输出质量 Checkpoints

### 14.1 生产判定协议

- Pilot 范围内的 AI 内容、Campaign Draft、报告和 Strategy 输出执行 100% Checkpoint；正式开放后再按签字的风险分层抽样。
- 所有外部副作用、Medical Claim、Approval 和 Incident 决策由确定性控制及人类 Owner 判定；AI 自评、总结或建议不能签发 `PASS`、Go-Live 或 Risk Acceptance。
- 结果仅为 `PASS / FAIL / BLOCKED`。PRD Credential、Evidence、Reviewer 或监控缺失时必须 `BLOCKED`。
- Evaluator Run 与 Producer 隔离，只读生产脱敏 Artifact/Evidence，不读取 Secret 或 Chain-of-Thought。
- 事实、安全、审批、数值、幂等、对账为硬门；软质量默认平均 >= 3.4/4、单项 >= 3，并以 UAT 签字基线为最低标准。

### 14.2 阶段 Checkpoint 矩阵

| ID | 触发时点 | 质量检查 | PASS 阈值 | Owner / 证据 | FAIL 后动作 |
|---|---|---|---|---|---|
| P6-CP01 | PRD Preflight 与只读 Smoke 后 | 配置、版本、模型、Policy、Skill、知识索引和 AI 输出 Contract 是否与 UAT 基线一致 | 未批准版本 0；Contract/Golden Smoke 100% 通过；测试/PRD 数据串用 0 | Tech Lead + Security + QA；Release Manifest、Config hash、Smoke | `BLOCKED` 部署或关闭对应 Provider |
| P6-CP02 | 每个 Pilot Content Package 前 | Claim Grounding、Medical/品牌、媒体安全、有效期和人工审核可读性 | Claim 引用 100%；Critical 逃逸 0；软评分 >= 3.4；Medical/Marketing 具名批准 100% | Medical + Marketing；Package/Checkpoint/Approval | 阻断 Campaign；返回 Content 指定节点 |
| P6-CP03 | 每个 Pilot Campaign 发布前后 | Draft 忠实度、预算/受众/排期、Approval、幂等、外部 ID 和对账 | 未审批写 0；重复对象 0；违规参数 0；Reconcile/Audit 完整率 100% | Campaign Approver + Operations；Request/Token/External ID/Audit | Kill Switch；暂停 Connector Queue 并人工对账 |
| P6-CP04 | 每份生产 Report/Strategy 后 | 数值、Raw 来源、新鲜度、因果措辞、建议权限和业务帮助度 | 数值一致率 100%；虚构结论 0；直接生产写建议 0；软评分 >= UAT 基线 - 0.2 | Data Owner + Marketing；Raw/Formula/Report/Strategy | 隐藏错误报告；返回 Metrics/Report 节点 |
| P6-CP05 | 每日 Hypercare / 漂移检测 | 与 UAT Golden 的事实、合规、品牌、拒绝率和软评分漂移 | 硬门失败 0；软评分下降 <= 0.2/4；异常拒绝率/成本在签字阈值内 | QA + Medical + SRE；Daily Eval、Drift Dashboard | 关闭受影响 Feature/Model；回滚版本并 Incident |
| P6-CP06 | 10-23 Go/No-Go 和 10-30 移交前 | AI 生成的发布摘要是否与原始 Evidence 一致，是否遗漏阻断项或夸大完成度 | Evidence 引用 100%；错误/遗漏门禁 0；所有 Go/No-Go 和移交签字均来自人类 Owner | PM + 全体签字人；Evidence Pack、会议决定、hash | `NO-GO`；修正证据，AI 不得自动豁免 |

### 14.3 生产抽样、告警与回退

- Pilot 的 AI 输出、Medical Claim、外部写和异常结果全部人工复核；扩大开放后，普通低风险输出每日分层抽样不少于 10% 且不少于 30 条。
- Critical/High Alert、用户投诉、Reviewer Reject 和模型/Prompt/Policy/Skill 版本变化触发 100% 受影响回溯。
- 线上 Checkpoint 只读取脱敏 Artifact 和 Evidence Reference；不得将生产 Secret 或完整敏感输入发送给 Evaluator。
- 任一硬门失败立即关闭对应 Feature/Provider；涉及未审批发布、Critical Claim、Secret、跨 Tenant 或重复 Campaign 时执行 Kill Switch 和 Incident Runbook。
- 连续两天软评分下降 > 0.2/4、单日下降 > 0.5/4 或 Reviewer Reject 超过签字阈值时回滚到 UAT 签字版本。
- P6-CP01 至 P6-CP06 全部 `PASS` 才能完成 Go-Live 和最终移交。
