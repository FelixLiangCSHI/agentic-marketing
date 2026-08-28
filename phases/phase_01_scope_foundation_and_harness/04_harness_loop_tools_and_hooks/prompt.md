# Coding Agent Prompt — Phase 01 / Subphase 04

## 给 Coding Agent 的指令

实现共享 Harness 的最小可信闭环：Loop、Tool Registry、Permission、Hooks、Context 和 Goal Check。安全决定由宿主代码执行，不由模型自报。

## 必须先读

1. [Phase 01 总计划](../../phase_01_scope_foundation_and_harness.md)
2. [前序 Prompt](../03_persistence_and_migrations/prompt.md) 及 Run/Task/Audit Contract。
3. `packages/domain-contracts/`、`apps/api/` 和 Migration。

## 执行位置与权限

- 模式：`repo`。
- 所有代码、测试和 Policy 变更必须在 GitHub 分支/Worktree 中完成并经 PR 审查。
- 只使用 Fake Model、Fake Tool 和本地数据库。
- 不暴露 Shell、任意 URL、原始 SQL、文件系统或真实 Secret Tool。

## 前置条件

- Subphase 03 为 `PASS`。
- Run 状态、Tool Level 和 Hook 顺序已冻结。

## 目标

让 Fake Content/Campaign Agent 可通过同一 Harness 执行独立 Run，并在权限、审批、错误和停止点产生可验证证据。

## Scope

包含 `packages/harness-core/loop|tools|permissions|hooks|context|memory|goal`。

不包含真实业务 Workflow、企业 IAM、Queue Broker 或外部 Connector。

## 实施任务

1. 先写以下失败测试：
   - 非法 Tool/参数。
   - 无审批 L3、任意 L4。
   - Prompt Injection 请求扩大工具。
   - Goal Check 无证据却判成功。
   - Hook 顺序错误和 Audit 失败。
2. 实现类型化 Tool Registry，注册 Schema、Handler、Level、Agent Allowlist 和版本。
3. 实现 deny -> policy -> approval 三层 Permission。
4. 固定 Hook 顺序：输入、模型前、Tool 前、Tool 后/错误、停止前、Run 后。
5. Context 只加载最小数据；大结果只传 URI、hash、摘要和关键证据。
6. Memory 只保存稳定偏好，按 Agent/用户/品牌/市场隔离。
7. Goal Check 只检查必需 Artifact/证据，不修改 Workflow 状态或签发 Medical 结论。
8. 为 Content/Campaign 配置不同 Tool Set，证明无法跨域调用。

## 验证命令与证据

- Harness Unit/Workflow/Security Test。
- 运行 Fake Agent：正常、拒绝、无 Tool、无证据停止、恶意 Tool 参数。
- 无审批 L3/L4、未注册 Tool、跨 Agent Tool 拒绝率 100%。
- Trace/Audit 记录 Hook、Permission 和 Tool Result。
- Evidence：Test report、Run timeline、Denied decisions、Tool registry snapshot。

## AI 质量 Checkpoint

执行 `P1-CP03`：

- 无审批 L3/L4 拒绝率 100%。
- 未注册 Tool 调用成功 0；无证据成功结论 0；Secret 泄漏 0。
- Evaluator 与 Producer Run 隔离，Security + QA 复核。
- AI 自评不能批准；结果仅 `PASS / FAIL / BLOCKED`，附 Evidence，不要求 Chain-of-Thought。

## 失败与阻断处理

- Audit 不可用：高风险 Tool fail closed。
- 模型输出无法解析：返回类型化错误，不猜测 Tool 参数。
- Permission 分歧：以宿主 Policy 的拒绝决定为准，进入人工复核。

## 完成响应格式

```text
Status:
Changed files:
Harness behavior implemented:
Commands/results:
P1-CP03:
Denied-tool evidence:
Risks/blockers:
Ready for Subphase 05:
```
