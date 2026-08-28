# Coding Agent Prompt — Phase 03 / Subphase 04

## 给 Coding Agent 的指令

实现 Google Ads Connector、Developer Token 认证、测试账户发布和 GAQL 报告。Repo 使用 Mock；真实操作通过受保护 DEV/SIT Job。

## 必须先读

1. [Phase 03 总计划及 Google Ads YAML 模板](../../phase_03_campaign_agent_and_integrations.md)
2. [前序 Prompt](../03_linkedin_connector/prompt.md)。
3. 当前 Google Ads API OAuth、Service Account、Developer Token、Quota 和 Test Account 官方文档。

## 执行位置与权限

- 模式：`hybrid-dev-sit`。
- 所有代码、测试、配置、IaC 和 Runbook 变更必须在 GitHub 分支/Worktree 中完成并经 PR 审查。
- Repo：Adapter、Mapper、Mock、GAQL fixtures、Contract。
- DEV/SIT：自托管 Runner、Proxy/FQDN、测试 Manager/Customer Account。
- 普通 PR 不获得 Developer Token/Refresh Token；不直接访问生产账户。

## 前置条件

- Connector SDK/Dry-run 为 `PASS`。
- Developer Token、Cloud Project、测试账户和认证方案有批准记录；否则真实路径 `BLOCKED`。

## 目标

实现最小 Google Ads Campaign 创建/查询、状态对账和 GAQL Raw Metrics。

## Scope

包含 `connectors/google_ads/`、父 YAML 配置、OAuth/批准的企业身份、Mapper、Metrics 和 DEV/SIT Contract。

不包含生产账户、虚构 Reporting API 或自动预算优化。

## 实施任务

1. 默认 `enabled:false/mode:mock`；API version/Quota 从批准配置注入。
2. Developer Token 仅 Secret Reference。
3. 企业自有账户且 IAM/Security 批准时可用 Workload Identity/Service Account；其他情况使用 OAuth。
4. 验证 customer/login-customer ID、Manager 关系和测试账户。
5. 实现 Dry-run、最小 mutate/query、status/reconcile。
6. GAQL 使用 `GoogleAdsService.Search/SearchStream`，保存原始字段、时区、游标和 response hash。
7. 所有写入验证 Approval/hash/idempotency；未知结果先对账。
8. Mock 覆盖 quota、Token 到期、超时已创建、重复投递、部分 mutate 和分页中断。
9. 远端测试有硬预算、命名前缀和对象清理。

## 验证命令与证据

- Auth/config/mapper/GAQL Unit/Contract Test。
- 未审批/重复/超时/部分成功 Recovery Test。
- 受保护 DEV/SIT 端到端发布、对账和读取。
- Evidence：官方核验、API/config version、external IDs、GAQL hash、Audit/cleanup。

## AI 质量 Checkpoint

执行 `P3-CP02`、`P3-CP03`：

- Checkpoint 结果仅允许 `PASS / FAIL / BLOCKED`；AI 自评不能批准。
- Dry-run 违规拦截 100%，无副作用。
- 未审批写 0，重复对象 0，对账遵守率 100%。
- Service Account 未批准时调用成功 0；Secret 泄漏 0。
- API Owner + IAM/Security + QA 复核；AI 自评不能 `PASS`，不保存 Chain-of-Thought。

## 失败与阻断处理

- Developer Token/测试账户/Quota 未批准：真实路径 `BLOCKED`。
- 不允许用 Service Account 代表非企业自有账户。
- API 版本变化：更新 Repo Contract 并重跑，不在远端热修。

## 完成响应格式

```text
Status:
Changed files:
Google API/auth mode:
Mock and protected-job results:
P3-CP02/P3-CP03:
Evidence/cleanup:
Blockers:
Ready for Subphase 05:
```
