# ADR-005：受控事实（Controlled Facts），而非自由 Memory

- 状态：Accepted
- 日期：2026-08-28
- 决策者：Architecture / Compliance（待签字复核）

## 背景

让模型自由累积长期 Memory 会引入不可审计的事实来源、跨租户/跨 Agent 泄漏风险，以及模型幻觉被固化为"事实"的风险。医疗营销场景对事实来源要求严格。

## 决策

- Agent 可依赖的事实只能来自**受控来源**：批准的产品资料（版本化 RAG）、确定性计算指标、审批记录与结构化 Run 产物。
- Memory 仅存放按 Agent/用户/品牌/市场隔离的**稳定偏好**（如语气、模板选择），不存放业务事实、数值或医疗声明。
- 精确数值一律由确定性代码计算；模型输出不得覆盖原始指标（延续现有 `src/analysis/` 原则）。
- Memory Namespace 跨 Agent 隔离；一个 Agent 不可读取另一个 Agent 的 Memory。

## 后果

- 任何"Agent 知道 X"的断言都可追溯到受控来源、版本与哈希。
- RAG 语料在 Product Data Owner 批准前保持 Fake Contract（见 BLOCKED 清单）。

## 关联

ADR-001、ADR-003。
