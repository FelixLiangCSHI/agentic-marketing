# Coding Agent Prompt — Phase 03 / Subphase 03

## 给 Coding Agent 的指令

实现 LinkedIn Advertising Connector。Repo 先用确定性 Mock/Contract 收敛；OAuth 和测试账户写入只通过受保护 DEV/SIT Job。

## 必须先读

1. [Phase 03 总计划及 LinkedIn YAML 模板](../../phase_03_campaign_agent_and_integrations.md)
2. [前序 Prompt](../02_connector_sdk_and_dry_run/prompt.md)。
3. 当前 LinkedIn 官方 Marketing API/OAuth/Versioning 文档和批准记录。

## 执行位置与权限

- 模式：`hybrid-dev-sit`。
- 所有代码、测试、配置、IaC 和 Runbook 变更必须在 GitHub 分支/Worktree 中完成并经 PR 审查。
- Repo：Adapter、Mapper、Mock、Contract、Policy。
- DEV/SIT：受保护 Environment、企业自托管 Runner、Proxy/FQDN、测试广告账户。
- 普通 PR 无 Refresh Token/写权限；Coding Agent 不直接登录远端或渠道后台。

## 前置条件

- P3-CP02 Fake SDK/Dry-run 为 `PASS`。
- Development Access、测试账户、内部 Redirect/OAuth Broker、scope 和 API version 已核验；否则真实路径 `BLOCKED`。

## 目标

实现最小 Campaign Management/Ads Reporting、3-legged OAuth、发布状态和指标读取。

## Scope

包含 `connectors/linkedin/`、父 YAML 配置、OAuth Adapter、Mapper、Metrics、fixtures、DEV/SIT Contract。

不包含有机发帖、Lead Sync、Webhook 或 Production Access。

## 实施任务

1. 默认 `enabled:false/mode:mock`，API version 从配置注入。
2. 实现 Authorization Code 3-legged OAuth；Token 仅在 Secret Manager。
3. 最小 scope 按批准配置，不自行扩大。
4. Mapper 只处理官方已核验字段；保存 request/response hash。
5. 实现 Dry-run、execute、get status、reconcile、metrics 分页/游标。
6. 写入前验证 Approval Token、input hash 和 idempotency key。
7. 超时/断开先对账；未知状态不创建第二对象。
8. Mock 覆盖 429、Token 到期、超时已创建、重复投递和部分层级成功。
9. DEV/SIT 使用命名前缀、硬预算和清理清单。

## 验证命令与证据

- Mock/Contract/OAuth state/mapper Unit Test。
- 无审批/重复消息/超时对账 Security/Recovery Test。
- 受保护 DEV/SIT：Draft -> Dry-run -> Approval -> Publish -> Reconcile -> Metrics。
- Evidence：官方核验、配置 hash、测试 external IDs、Audit、清理状态。

## AI 质量 Checkpoint

执行 `P3-CP02`、`P3-CP03`：

- Checkpoint 结果仅允许 `PASS / FAIL / BLOCKED`；AI 自评不能批准。
- 渠道规格违规拦截率 100%。
- 无效审批写调用 0；100 次重复消息重复对象 0。
- 未知结果先对账 100%；Audit 完整率 100%。
- API Owner + QA + Security 复核。无真实权限则 `BLOCKED`，Mock 不能替代；AI 自评不能批准，不保存 Chain-of-Thought。

## 失败与阻断处理

- OAuth/Access Tier/Redirect 未批准：只提交 Mock/Contract，状态 `BLOCKED`。
- 429/超时：按配置退避和对账，不盲目重试。
- 远端 Schema 变化：回 Repo 更新 Adapter/fixture/核验记录，禁止热补丁。

## 完成响应格式

```text
Status:
Changed files:
LinkedIn version/scopes:
Mock and protected-job results:
P3-CP02/P3-CP03:
External evidence/cleanup:
Blockers:
Ready for Subphase 04:
```
