# Coding Agent Prompt — Phase 03 / Subphase 05

## 给 Coding Agent 的指令

集成审批发布、幂等操作表、Outbox、reconcile-before-retry 和补偿状态。目标是任何重试、崩溃或未知结果都不创建重复外部对象。

## 必须先读

1. [Phase 03 总计划](../../phase_03_campaign_agent_and_integrations.md)
2. [前序 Prompt](../04_google_ads_connector/prompt.md)。
3. LinkedIn/Google Connector、Approval、Audit、Queue、Migration 和 Run 状态。

## 执行位置与权限

- 模式：`hybrid-dev-sit`。
- 所有代码、测试、Migration、配置和 Runbook 变更必须在 GitHub 分支/Worktree 中完成并经 PR 审查。
- Repo：状态机、Migration、Worker、Fake fault test。
- DEV/SIT：受保护 Job 使用测试账户验证真实未知结果和对账。
- 不直接 SSH、不手工改操作表、不执行 L4 自动补偿。

## 前置条件

- 两个 Connector 的 Mock Contract 为 `PASS`。
- 至少一个测试渠道具备远端 Credential；否则远端结果 `BLOCKED`。

## 目标

建立从 Approval 到外部 ID 的一次逻辑写入和可恢复证据链。

## Scope

包含 connector operation/idempotency/outbox Migration、Activation Worker、Token 原子消费、Reconcile 和人工补偿任务。

不包含指标、报告或自动删除/暂停。

## 实施任务

1. 先写 Token 重用、同 key 不同 hash、100 次重复消息、请求超时已创建、响应后崩溃和部分层级成功测试。
2. 建立唯一键 `(tenant, channel, account, idempotency_key, input_hash)`。
3. 外部调用前原子消费 Token、写 operation intent 和 Audit/Outbox。
4. `UNKNOWN` 状态停止盲目重试，按 operation ID/object ID/fingerprint 精确对账。
5. 唯一对象转 `RECONCILED`；确认未创建才重试相同 key。
6. 仍未知进入人工队列/DLQ，不创建第二对象。
7. 记录每层外部 ID；L4 删除/暂停只生成待审批 Runbook 任务。
8. Worker lease/restart/replay 保持状态单调和可重入。

## 验证命令与证据

- Migration/transaction/idempotency Unit/Integration。
- 100 次重复、restart、timeout-after-create、partial success。
- DEV/SIT 测试账户 fault/reconcile。
- Audit/Trace/Outbox 完整性和 Secret scan。
- Evidence：operation rows、external IDs、request hashes、reconcile trace。

## AI 质量 Checkpoint

执行 `P3-CP03`：

- 无效 Approval 写调用 0。
- 100 次重复投递重复对象 0。
- 外部未知结果先对账遵守率 100%。
- Approval/hash/idempotency/Audit/Reconcile 完整率 100%。
- Campaign Approver + Security + SRE 复核；AI 自评不能批准，不收集 Chain-of-Thought。

## 失败与阻断处理

- 状态未知：`BLOCKED/WAITING_RECONCILIATION`，不标失败后重建。
- 重复对象：Critical `FAIL`，关闭 Connector 写开关并人工对账。
- Audit/Outbox 写失败：fail closed。

## 完成响应格式

```text
Status:
Changed files/migrations:
Fault scenarios/results:
P3-CP03:
Operation/external evidence:
Open reconciliation:
Ready for Subphase 06:
```
