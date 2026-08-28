# Coding Agent Prompt — Phase 03 / Subphase 07

## 给 Coding Agent 的指令

集成 Phase 03 的双渠道链路、运行全部质量门并生成 SIT 可用 RC。不得用 Mock 代替要求的测试账户证据。

## 必须先读

1. [Phase 03 总计划](../../phase_03_campaign_agent_and_integrations.md)
2. [前序 Prompt](../06_metrics_reports_and_strategy/prompt.md)。
3. Subphase 01–06 的完成响应、P3 Checkpoint、外部对象和清理记录。

## 执行位置与权限

- 模式：`hybrid-dev-sit`。
- 所有缺陷修复、测试、配置、IaC 和 Evidence 模板变更必须在 GitHub 分支/Worktree 中完成并经 PR 审查。
- Repo：全量回归、RC、Contract/Eval 和 Review。
- DEV/SIT：受保护 Pipeline、独立 Credential、Proxy/FQDN 和测试账户。
- 无直接远端访问；Production Account/Secret 不可用。

## 前置条件

- Subphase 01–06 无未关闭 Critical/High。
- 两个渠道官方文档、测试账户和清理 Owner 可验证。

## 目标

证明从批准 Package 到双渠道 Draft、Dry-run、Approval、Publish、Reconcile、Metrics、Report 和 Strategy 的安全闭环。

## Scope

包含双渠道 E2E、故障/恢复、安全、Checkpoint、缺陷修复和 Phase 04 交付。

不包含生产发布或新渠道。

## 实施任务

1. 构建不可变 RC，记录 SHA、image/config/schema/connector/API version。
2. LinkedIn/Google 各运行至少 10 个确定性场景。
3. 覆盖预算/币种/时区/受众/素材错误、Token 过期、429、超时已创建、重复消息、后台手工修改。
4. 验证 100 次重复投递、Worker restart、部分成功和 DLQ。
5. 拉取 Raw/Normalized Metrics，生成 Report/Strategy 并验证 Strategy 无写 Tool。
6. 检查 Secret、Trace/Audit、费用、外部对象和清理。
7. 运行双语言 Contract、Migration、安全、恢复和现有分析回归。
8. 生成 Phase 04 SIT fixtures、Runbook 和 Evidence Pack。

## 验证命令与证据

- 所有 Subphase 测试/构建/扫描。
- 两渠道受保护 E2E。
- Idempotency/Reconcile/Metric/Report/Strategy Eval。
- Evidence：RC、Approval、external IDs、Raw hashes、Checkpoint、清理状态。

## AI 质量 Checkpoint

执行 `P3-CP01`、`P3-CP02`、`P3-CP03`、`P3-CP04`、`P3-CP05`、`P3-CP06`：

- Checkpoint 结果仅允许 `PASS / FAIL / BLOCKED`；AI 自评不能批准。
- 两渠道每个至少 10 场景且 100% 通过。
- 未审批写/重复对象/违规参数/Secret 泄漏均为 0。
- Raw/Report 追溯、Approval/Hash/Idempotency/Reconcile/Audit 均为 100%。
- Critical/High Finding 0；QA、API Owner、Marketing、Security 具名复核。
- AI 自评不能 `PASS`，不收集 Chain-of-Thought。

## 失败与阻断处理

- 任一真实渠道门禁缺失：Phase 03 `BLOCKED`，不得宣称完成。
- 硬门失败：返回拥有缺陷的最小子阶段。
- 禁止扩 scope、降低预算/安全门或用 Mock 包装真实失败。

## 完成响应格式

```text
Status:
Release candidate:
Changed files:
Full validation:
P3-CP01..P3-CP06:
External/evidence/cleanup refs:
Open blockers:
Phase 04 readiness:
```
