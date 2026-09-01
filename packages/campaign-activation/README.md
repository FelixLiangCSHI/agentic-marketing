# campaign-activation

Phase 03 / Subphase 05: 激活执行、幂等与对账（Activation, Idempotency and Reconciliation）。

## 职责

- **操作台账（Operation Ledger）**：每个逻辑外部写以
  `(tenant, channel, account_id, idempotency_key, input_hash)` 唯一登记；
  同 key 不同 `input_hash` 直接拒绝，状态迁移单调且可重入。
- **原子审批消费**：外部调用前先单次消费 approval token 并落 INTENT +
  Audit + Outbox；任一失败即 fail closed，外部调用次数为 0。
- **ActivationWorker**：消费 `campaign.activation` 队列消息，
  幂等处理重复投递 / 重放 / worker 重启，同一逻辑操作最多创建 1 个外部对象。
- **Reconcile-before-retry**：外部结果 UNKNOWN 时禁止盲目重试，
  先精确对账——查到唯一对象 → `RECONCILED`；确认未创建 → 同 key 重试；
  仍无法判定 → `WAITING_RECONCILIATION` + 人工队列（DLQ），绝不产生第二个对象。
- **补偿任务**：部分成功仅登记 `PENDING_APPROVAL` 补偿任务
  （L4 删除/暂停走人工审批 Runbook），本包不自动执行任何补偿。

## 状态机

`INTENT → SUCCEEDED | UNKNOWN | FAILED | COMPENSATION_PENDING`；
`UNKNOWN → RECONCILED | SUCCEEDED | WAITING_RECONCILIATION`；
`WAITING_RECONCILIATION → RECONCILED | SUCCEEDED`；
终态：`SUCCEEDED / RECONCILED / FAILED / COMPENSATION_PENDING`。
同状态重申（re-assert）幂等允许。

## 边界

仓库内只包含 Fake 实现（`FakeOperationStore` / `FakeApprovalConsumer` /
`FakeAuditLog` / `FakeOutbox` / `FakeCompensationQueue`）与
`connector_sdk.FakeConnector`；真实 DEV/SIT 账户对账仅在受保护流水线执行。
持久化 DDL 见 `apps/api/migrations/versions/0004_connector_operations.py`
（`campaign.connector_operations` / `campaign.compensation_tasks`）。

## 运行

```bash
pip install -e "packages/campaign-activation[dev]"
npm run campaignactivation:test
npm run campaignactivation:typecheck
```
