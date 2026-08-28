# Coding Agent Prompt — Phase 03 / Subphase 06

## 给 Coding Agent 的指令

实现 Raw Metrics 摄取、独立 Normalization、Performance Report 和只读 Strategy Recommendation。精确数值由确定性代码计算，模型只解释证据。

## 必须先读

1. [Phase 03 总计划](../../phase_03_campaign_agent_and_integrations.md)
2. [前序 Prompt](../05_activation_idempotency_and_reconciliation/prompt.md)。
3. 两渠道 Metrics Adapter、现有确定性 `src/analysis/` 和报告导出。

## 执行位置与权限

- 模式：`hybrid-dev-sit`。
- 所有代码、测试、公式、配置和报告模板变更必须在 GitHub 分支/Worktree 中完成并经 PR 审查。
- Repo：指标模型、公式、报告/Strategy、fixtures 和 Eval。
- DEV/SIT：受保护 Job 拉取测试账户 Raw Metrics。
- OAuth/渠道 Secret 只留在企业 Secret Manager；GitHub 仅保存引用、公式和脱敏 Evidence。
- Strategy 无渠道写 Tool；普通 PR 无远端数据/Credential。

## 前置条件

- 外部对象映射和 Reconcile 状态可靠。
- LinkedIn/Google 测试报告权限可用；缺失渠道标 `BLOCKED`。

## 目标

保存不可变供应商原始指标，生成可重算统一指标、可追溯报告和不自动执行的策略建议。

## Scope

包含 Raw/Normalized Migration、watermark/cursor、公式、Report/Strategy Contract、UI/API 和 Eval。

不包含自动优化、预算/受众写回。

## 实施任务

1. 先写缺失 vs 0、币种/时区/归因不一致、重复拉取、分页中断、过期数据和虚构因果测试。
2. Raw 只追加，保存 provider field/value/type/currency/timezone/window/version/retrieved/hash。
3. 以 source hash 去重，不覆盖供应商修订。
4. Normalized 独立保存 Decimal、公式版本和 source raw IDs。
5. 无法可靠转换返回 `not_available`，不插补。
6. 定时拉取保存 watermark/cursor，Worker 重启后恢复。
7. Report 每个数字/结论引用 Raw IDs、公式和新鲜度。
8. Strategy 标记 `DRAFT`，建议绑定证据/风险/置信度；任何执行创建新 Activation Request。
9. 复用现有确定性分析逻辑前先写兼容测试。

## 验证命令与证据

- Raw/Normalized/Formula Unit/Property Test。
- Cursor/restart/duplicate Integration Test。
- Report/Strategy Golden/Adversarial Eval。
- DEV/SIT 双渠道 metrics pull。
- Evidence：Raw response hash、formula version、report-source graph、Denied write trace。

## AI 质量 Checkpoint

执行 `P3-CP04`、`P3-CP05`：

- Checkpoint 结果仅允许 `PASS / FAIL / BLOCKED`；AI 自评不能批准。
- 数值与确定性计算一致率 100%，Raw 追溯 100%。
- 虚构数字/因果结论 0，缺失值变 0 次数 0。
- Strategy 证据链接 100%，越权/直接写 0，软评分 >= 3.4。
- Data Owner + Marketing/Campaign Approver 复核；AI 自评不能批准，不保存 Chain-of-Thought。

## 失败与阻断处理

- 原始指标权限缺失：渠道报告为 `BLOCKED/not_available`，不生成估算。
- 数值错误：隐藏受影响报告，修复公式后重算；Raw 不可改。
- Strategy 越权：`FAIL`，移除写 Tool 并重跑安全 Eval。

## 完成响应格式

```text
Status:
Changed files/migrations:
Metric/formula versions:
Commands/evals:
P3-CP04/P3-CP05:
Evidence:
Blockers:
Ready for Subphase 07:
```
