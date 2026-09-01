# Runbook — Campaign Reconciliation（reconcile-before-retry 与人工队列）

适用范围：Phase 03 双渠道（LinkedIn Advertising、Google Ads）外部写操作的
`UNKNOWN` / `WAITING_RECONCILIATION` / `COMPENSATION_PENDING` 处理。
执行环境：受保护 DEV/SIT 流水线或经审批的 Runbook 会话；本仓库内只允许
mock 演练（`integration/test_phase03_gate.py`）。

## 1. 触发信号

| 信号 | 来源 | 含义 |
|---|---|---|
| `activation_unknown` 审计事件增长 | `campaign.connector_operations.status = UNKNOWN` | 外部写超时/连接中断，结果未知 |
| `reconcile_undecided` 审计事件 | Worker 对账抛错 | 供应商查询不可用，操作已停住 |
| DLQ `campaign.activation` 消息 | 队列 Dead Letter | 重试用尽，进入人工队列 |
| `compensation_pending` 事件 | `campaign.compensation_tasks` | 部分层级成功，等待人工审批的补偿 |

## 2. 原则（不可越过）

1. **先对账再重试**：任何 `UNKNOWN` 都禁止盲目重试；必须先用幂等键 /
   operation id 做供应商精确查询（`connector.reconcile`），确认“已创建 /
   未创建 / 无法判定”。
2. **绝不创建第二个对象**：找到唯一对象 → 记录 `external_object_id` 并转
   `RECONCILED`；无法判定 → 停在 `WAITING_RECONCILIATION` / DLQ。
3. **补偿不是回滚**：生产对象的删除/暂停是 L4，MVP 不自动执行；补偿任务
   只生成待审批工单，执行需新的 Approval、input hash 和审计。
4. **对账不覆盖**：供应商后台被人工修改时，只报告差异（get_status 漂移），
   不自动“修复”，不改写本地 ledger。

## 3. 处理步骤（DLQ 消息）

1. 从 DLQ 读取消息，记录 `tenant / channel / account / idempotency_key`。
2. 查询 `campaign.connector_operations` 中该键的记录与 `input_hash`。
3. 在受保护环境用只读凭据调用 `connector.reconcile`（精确查询，禁止宽泛
   搜索）。
4. 结果分派：
   - 找到唯一对象 → 人工确认后把操作转 `RECONCILED`，回填
     `external_object_id`，重放消息（幂等，worker 会去重）。
   - 确认未创建 → 重放同一幂等键（同一 Approval 已消费，无需二次审批）。
   - 仍无法判定 → 升级 Connector Owner + API Owner，保持停住状态。
5. 全程写审计；每一步带 `trace_id` 与工单号。

## 4. 补偿任务（`campaign.compensation_tasks`）

1. 核对 `created_object_ids` 与供应商实际对象。
2. Campaign Approver + Security 审批后才可执行供应商支持的草稿撤销；
   生产对象删除/暂停一律人工在供应商后台完成并记录。
3. 完成后将操作转 `COMPENSATED` 并附证据（对象 ID、时间、执行人）。

## 5. 演练与证据

- 仓内演练：`python -m pytest integration -k "timeout or undecidable or partial or duplicate"`。
- DEV/SIT 演练在受保护流水线执行，证据（外部 ID、审计、清理记录）归档到
  `docs/phase03/subphase07-evidence.md` 引用的 Evidence Pack。

Owner：Backend/SRE（对账）、Campaign Owner（补偿）、Security（审批）。
