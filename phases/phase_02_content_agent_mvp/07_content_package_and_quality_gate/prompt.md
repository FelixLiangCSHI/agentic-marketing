# Coding Agent Prompt — Phase 02 / Subphase 07

## 给 Coding Agent 的指令

实现不可变 `ApprovedContentPackage` Builder，集成 Phase 02 全链路并运行全部质量门。不得增加 Campaign 发布能力。

## 必须先读

1. [Phase 02 总计划](../../phase_02_content_agent_mvp.md)
2. [前序 Prompt](../06_compliance_review_and_rework/prompt.md)。
3. Subphase 01–06 的完成响应、P2 Checkpoint 和 Evidence。

## 执行位置与权限

- 模式：`hybrid-dev`。
- 所有代码、测试、配置和 Evidence 模板变更必须在 GitHub 分支/Worktree 中完成并经 PR 审查。
- Repo：Builder、Contract、全量 Eval 和 RC。
- DEV/SIT：受保护 Pipeline 验证 Product/模型/媒体/Reviewer 集成。
- 无直接远端访问、无渠道 Credential、无外部 Campaign 写入。

## 前置条件

- P2-CP01 至 P2-CP05 的前置指标满足或明确 `BLOCKED`。
- Medical/Marketing Reviewer、Product/Provider 门禁可验证。

## 目标

生成只有合法审批、完整引用、有效资产和稳定 hash 才能创建的 `ApprovedContentPackage`，并冻结给 Phase 03 的输入。

## Scope

包含 Package Builder、版本/失效、Content 全链路、Golden/Adversarial、安全/恢复和阶段签字。

不包含 Campaign Draft/Connector 或生产媒体。

## 实施任务

1. 先写未批准、过期、hash 不匹配、缺渠道变体、资产修改和重复构建测试。
2. Builder 只接受已通过 Compliance 和人工 Review 的不可变版本。
3. 计算 canonical content hash，绑定 Claim/source version/excerpt hash、asset hash、Policy/Prompt/Skill/Model、approval 和 expiry。
4. 任一字段变化创建新版本并使旧审批失效；旧 Package 保留审计。
5. 过期/撤销 Product、Skill、Policy 或 Package 阻断消费。
6. 运行 Content Request -> RAG -> Brief -> Copy -> Media -> Compliance -> Review -> Package。
7. 注入 Provider 429/超时、Worker restart、Reject/Rework、恶意附件和 Prompt Injection。
8. 生成 RC 和 Phase 03 Contract fixtures。

## 验证命令与证据

- Package Schema/hash/version/approval Test。
- 全量 Content Workflow/Contract/Security/Recovery。
- Golden/Adversarial Eval 和 DEV/SIT Integration。
- Secret Scan、Trace/Audit 完整性。
- Evidence Pack：SHA、config/model/index/skill/policy versions、Eval、Package/Approval hashes。

## AI 质量 Checkpoint

执行 `P2-CP01`、`P2-CP02`、`P2-CP03`、`P2-CP04`、`P2-CP05`、`P2-CP06`：

- Checkpoint 结果仅允许 `PASS / FAIL / BLOCKED`；AI 自评不能批准。
- Claim 来源 100%；过期/撤销资料 0；Critical 逃逸 0。
- Package Schema/hash/approval 100%，旧审批失效 100%。
- 媒体安全硬门 100%；文案/媒体软评分 >= 3.4。
- 全部 Checkpoint 由 Product、Medical、Marketing、Security、QA 复核。AI 自评不能批准；不收集 Chain-of-Thought。

## 失败与阻断处理

- 任一硬门失败：返回拥有该产物的最小节点和子阶段。
- 真实 Product/Provider/Reviewer 缺失：阶段 `BLOCKED`，不以 Mock 替代退出门。
- 禁止直接修改 Package、来源或审批记录“修复”测试。

## 完成响应格式

```text
Status:
Release candidate:
Changed files:
Full commands/evals:
P2-CP01..P2-CP06:
Package/evidence references:
Open blockers:
Phase 03 readiness:
```
