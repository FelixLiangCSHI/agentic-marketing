# Coding Agent Prompt — Phase 02 / Subphase 06

## 给 Coding Agent 的指令

实现确定性 Compliance、模型 Critic、人工 Medical/Marketing Review UI/API 和定点返工。规则失败不能被模型覆盖，人工角色不能由前端伪造。

## 必须先读

1. [Phase 02 总计划](../../phase_02_content_agent_mvp.md)
2. [前序 Prompt](../05_jimeng_media_connector/prompt.md)。
3. Content Workflow、Skill/Policy、Approval/Audit 和 Review UI 现状。

## 执行位置与权限

- 模式：`hybrid-dev`。
- 所有代码、测试、规则、Prompt、Policy 和 UI 变更必须在 GitHub 分支/Worktree 中完成并经 PR 审查。
- Repo：规则、Critic Contract、UI/API、Golden/Adversarial Eval。
- DEV：受保护 Pipeline 验证 SSO 角色、真实 Reviewer 和脱敏内容。
- 真实身份凭据和 Secret 只留在企业 Secret Manager；GitHub 仅保存引用和脱敏 Evidence。
- 无人类 Medical 签字时只能生成草稿；Coding Agent 不能代签。

## 前置条件

- Copy/Media 节点和 P2-CP02/P2-CP03 基线可用。
- Medical Policy v1、Reviewer 和严重度定义已冻结。

## 目标

建立规则 + Critic + 人工审批三层门，并让拒绝意见准确回到 Fact/Copy/Media 节点。

## Scope

包含 Compliance Engine、结构化 issue、Review UI/API、角色校验、审批失效和 Rework。

不包含 Campaign 或 Package 最终 Builder。

## 实施任务

1. 先写禁用表达、过期 Claim、缺披露、跨市场、竞品比较、伪造批准、自批和错误返工测试。
2. 确定性规则输出 rule ID、claim ID、severity、source、suggested node。
3. Critic 只提出补充问题，不得把规则失败改为通过。
4. Review UI 并排显示内容、Claim、来源、Policy、Prompt/Model/Skill 版本。
5. Reject 必填原因和目标节点；只失效相关下游。
6. 服务端验证 Medical/Marketing 角色、artifact hash 和职责分离。
7. 输入/内容变化使旧审批失效。
8. 构建 confusion matrix、Critical/总体 Recall 和误报分析。
9. DEV 由具名 Reviewer 执行脱敏 UAT，不把身份/评论原文上传普通 Artifact。

## 验证命令与证据

- Compliance Unit/Golden/Adversarial Eval。
- Review/RBAC/Approval Security Test。
- Workflow targeted-rework/restart Test。
- DEV Reviewer Integration。
- Evidence：confusion matrix、Rule/Issue IDs、Review decision、Journal diff、Audit。

## AI 质量 Checkpoint

执行 `P2-CP04`、`P2-CP05`：

- Checkpoint 结果仅允许 `PASS / FAIL / BLOCKED`；AI 自评不能批准。
- Critical Recall 100%，总体 Recall >= 95%，Critical 逃逸 0。
- 建议返工节点正确率 >= 95%。
- Review 必需字段/来源展示 100%，推测写成事实 0，软评分 >= 3.4。
- Medical + Marketing 具名复核；AI 自评/Critic 不能批准，不收集 Chain-of-Thought。

## 失败与阻断处理

- Critical 漏检：立即 `FAIL`，停止 Package 路径。
- Reviewer/Policy 缺失：`BLOCKED`，不降低到 AI 审批。
- 返工范围过大：修复依赖图，不盲目重跑。

## 完成响应格式

```text
Status:
Changed files:
Compliance metrics:
Review/rework results:
P2-CP04/P2-CP05:
Evidence:
Risks/blockers:
Ready for Subphase 07:
```
