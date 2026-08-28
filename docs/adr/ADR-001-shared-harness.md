# ADR-001：双 Agent 共享 Harness

- 状态：Accepted
- 日期：2026-08-28
- 决策者：Architecture（待 Product Owner / Architect 签字复核）

## 背景

MVP 需要 Content Agent 与 Campaign Agent 两个自治 Agent。若各自实现循环、权限、审批、审计与恢复逻辑，将产生重复代码、不一致的安全语义和双倍验证成本。

## 决策

两个 Agent 共用同一个 `packages/harness-core`，其中包含：Agent Loop、类型化 Tool Registry、deny -> policy -> approval 三层权限门、Hooks、Context 管理、隔离 Memory、Task DAG 与租约、LangGraph Checkpoint/Journal、Goal Check。

Agent 仅通过声明式配置（`agents/<name>/agent.yaml`、prompts、workflows、policies、skills）注册到 Harness。

## 边界约束

- `harness-core` 不包含营销 Prompt、渠道 SDK 或供应商 Secret。
- 两个 Agent 使用独立的配置、Session、Tool Set、Memory Namespace、Queue 与 Service Identity；互相不可读取对方私有上下文与凭据（负向测试验证）。

## 后果

- 权限、审批、审计与恢复语义只实现和验证一次。
- Harness 的变更属于共享契约变更，必须双人审查（见 CONTRIBUTING.md）。

## 关联

ADR-002（单一 Workflow Runtime）、ADR-003（副作用前审批）、ADR-005（受控事实）、ADR-006（幂等外部写）。
