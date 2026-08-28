# ADR-002：MVP 仅使用 LangGraph 作为 Workflow Runtime

- 状态：Accepted
- 日期：2026-08-28
- 决策者：Architecture（待签字复核）

## 背景

多 Agent 框架（如 CrewAI、AutoGen）各有编排模型。同时引入两套 Runtime 会导致 Checkpoint、Journal、权限 Hook 和恢复语义分裂，验证成本加倍。

## 决策

2026-10-30 MVP 只使用 **LangGraph** 作为唯一 Workflow Runtime。所有 Workflow 的 Checkpoint、状态持久化与 Journal 通过 `harness-core/workflow/` 统一封装。

## 明确禁止

- 引入 CrewAI 或任何第二套 Workflow Runtime 的依赖或运行状态。
- 在 Workflow 之外手写隐式状态机绕过 Checkpoint/Journal。

## 后果

- Checkpoint/Resume、审计与 Trace 只对接一套 Runtime。
- 若未来需要更换/新增 Runtime，必须新 ADR 并升级 Harness 抽象，不在 MVP 范围内。

## 关联

ADR-001。
