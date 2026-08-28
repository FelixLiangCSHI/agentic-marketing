# Coding Agent Prompt — Phase 02 / Subphase 03

## 给 Coding Agent 的指令

实现 Content Skill Registry、结构化 Brief/Copy Contract 和可暂停/恢复的 LangGraph Content Workflow，暂时通过 Fake Model/Media 执行。

## 必须先读

1. [Phase 02 总计划](../../phase_02_content_agent_mvp.md)
2. [前序 Prompt](../02_approved_rag_and_citations/prompt.md)。
3. Harness Loop/Checkpoint、Product RAG Contract 和 Skill 元数据规范。

## 执行位置与权限

- 模式：`repo`。
- 所有代码、测试、Prompt、Skill 和 Policy 变更必须在 GitHub 分支/Worktree 中完成并经 PR 审查。
- 普通 CI 使用 Fake Model、Fake Media、Fake Reviewer。
- 不连接真实 LLM/媒体，不签发真实 Medical Approval。

## 前置条件

- P2-CP01 Repo 指标通过。
- Brand/Medical/Market/Channel Skill Owner 和初始版本存在；缺正式批准时只生成草稿。

## 目标

建立 `ValidateInput -> RetrieveProductFacts -> BuildBrief -> GenerateCopy -> GenerateMedia -> ComplianceCheck -> HumanReview -> PackageApproved` 的可信骨架。

## Scope

包含 Skill Registry、节点 Contract、Workflow Journal/Checkpoint、Fake 节点和定点返工路由。

不包含真实 DeepSeek/即梦、完整 Compliance 规则或 Package 批准实现。

## 实施任务

1. 先写 Skill 过期、节点输出非法、拒绝返工、取消和 Worker restart 测试。
2. 实现 Skill 元数据和按 agent/market/locale/channel 最小加载。
3. Skill 过期/撤销阻断相关节点；内容只读且版本写入 Run。
4. 创建 Content Brief：事实、禁用 Claim、披露、语气、渠道约束和来源。
5. 每个 Workflow 节点输入/输出使用版本化 Schema 并写 Journal/Checkpoint。
6. Rework 根据 `fact_issue/copy_issue/asset_issue` 返回指定节点，仅失效相关下游。
7. Fake Model 输出结构化草稿；无来源 Claim 标记并阻断。
8. Goal Check 只检查产物/证据，不代替人工 Reviewer。

## 验证命令与证据

- Skill Registry Unit Test。
- Workflow 正常/拒绝/定点返工/取消/恢复 Test。
- Brief/Copy Schema 和 Claim 引用测试。
- Fake Agent Trace/Audit。
- Evidence：Workflow graph/version、Journal、节点 hash、Skill versions。

## AI 质量 Checkpoint

执行 `P2-CP02`、`P2-CP05` 的 Fake 基线：

- Checkpoint 结果仅允许 `PASS / FAIL / BLOCKED`；AI 自评不能批准。
- Claim 来源覆盖率 100%，事实错误/虚构数字 0。
- 必需 Brief/Review 字段 100%，渠道硬规则通过。
- 软评分 >= 3.4/4。
- Marketing/Medical 使用 fixtures 复核；AI 自评不能 `PASS`，不收集 Chain-of-Thought。

## 失败与阻断处理

- Skill 未批准：允许 Workflow 到 `DRAFT`，禁止 Package Approved。
- 返工重跑无关节点：`FAIL`，修复依赖/失效图。
- 模型输出非法：类型化失败，不用默认值伪造成功。

## 完成响应格式

```text
Status:
Changed files:
Workflow/Skill versions:
Commands/results:
P2-CP02/P2-CP05:
Evidence:
Blockers:
Ready for Subphase 04:
```
