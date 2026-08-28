# ADR-003：外部副作用前必须人工审批

- 状态：Accepted
- 日期：2026-08-28
- 决策者：Architecture / Security（待签字复核）

## 背景

Agent 可能触发不可逆或有成本的外部动作（发布、发送、创建/修改 Campaign）。模型输出不可信，不能作为执行授权。

## 决策

Tool 按风险分级，权限门顺序固定为 deny -> policy -> approval：

| Level | 动作 | 默认策略 |
|---|---|---|
| L0 | 读取批准资料、状态 | 自动允许并审计 |
| L1 | 草稿、模拟、评估 | Agent Policy 允许 |
| L2 | 收费模型、媒体任务 | 费用与并发限制 |
| L3 | 外部发布、发送、创建/修改 Campaign | 人工审批 + 单次令牌 + 幂等 + 对账 |
| L4 | 提高预算、扩大受众、删除/暂停生产 Campaign | MVP 一律拒绝（即使有普通审批） |

## 审批与职责分离规则

- 审批记录绑定：类型、Requester、Approver、角色范围、输入产物哈希、Policy/Prompt/Skill/Workflow 版本、预算/渠道/账户/时间范围、单次令牌、过期与撤销状态。
- 发起人不能批准自己的高风险操作；Medical Reviewer 与 Campaign Approver 角色分离。
- 令牌原子消费；输入、预算、渠道、账户、时间或哈希变化后旧审批立即失效。
- 审计写入失败时，L3/L4 Tool 必须 fail closed。

## 后果

- 无审批的 L3 Tool 调用拒绝率必须为 100%（阶段验收硬门）。

## 关联

ADR-001、ADR-006。
