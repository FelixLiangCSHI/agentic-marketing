# Coding Agent Prompt — Phase 01 / Subphase 08

## 给 Coding Agent 的指令

集成 Phase 01 全部产物，运行 Fake 双 Agent Demo、恢复/权限测试和 DEV 门禁，形成可供 Phase 02/03 使用的签字基线。不要增加新功能。

## 必须先读

1. [Phase 01 总计划](../../phase_01_scope_foundation_and_harness.md)
2. [前序 Prompt](../07_ci_observability_and_local_dev/prompt.md)。
3. Subphase 01–07 的完成响应、Checkpoint 和 Evidence。

## 执行位置与权限

- 模式：`hybrid-dev`。
- 所有缺陷修复、测试、配置、IaC 和 Evidence 模板变更必须在 GitHub 分支/Worktree 中完成并经 PR 审查。
- Repo：全量回归、Fake Demo、Review 和 Release Candidate。
- DEV：仅通过受保护 Pipeline 验证 SSO、DB、Queue、Storage、Secret、Gateway/Proxy。
- Coding Agent 无直接服务器/生产权限；缺远端资源即 `BLOCKED`。

## 前置条件

- Subphase 01–07 无未关闭 Critical/High。
- Contract、Migration、Policy、CI 和本地栈均有可复验证据。

## 目标

证明共享 Harness 可安全支撑两个隔离 Agent，并冻结 Phase 02/03 的可信基础版本。

## Scope

包含集成、缺陷修复、全量回归、DEV Contract、质量门和阶段签字。

不包含 Product RAG、真实内容生成或渠道发布。

## 实施任务

1. 从干净 checkout 构建不可变 RC，记录 SHA、依赖锁、Migration 和配置 hash。
2. 演示 Fake Content/Campaign：
   - 创建、执行、等待审批、拒绝、批准、恢复、取消。
   - 不同 Tool/Context/Memory/Credential Namespace。
3. 注入：非法状态、无审批 L3/L4、恶意 Tool、Audit 故障、重复消息、Worker restart、Poison Message。
4. 在 DEV 受保护 Job 验证 SSO、PostgreSQL、Queue、Object Store、Secret 和网络；不执行真实渠道写。
5. 运行 Web/Python/Contract/Migration/Workflow/Security/Eval 全量门禁。
6. 复核所有 ADR、Runbook、Owner、API/Infra 工单和 Phase 02/03 输入。
7. 只修复范围内缺陷；任何架构变化更新 ADR 并重跑受影响门禁。

## 验证命令与证据

- 所有 Subphase 指定命令。
- Fake 双 Agent Demo 和恢复测试。
- DEV Integration/Isolation Test。
- Secret/依赖/镜像扫描和 SBOM。
- Evidence Pack：SHA、image/config/schema hash、测试、Trace/Audit、Checkpoint、阻断项。

## AI 质量 Checkpoint

执行 `P1-CP01`、`P1-CP02`、`P1-CP03`、`P1-CP04`、`P1-CP05`：

- 五个 Checkpoint 全部 `PASS`。
- 无审批 L3/L4 成功 0，重复副作用 0，跨 Agent 访问 0。
- Contract/Migration/CI 100% 通过；Critical/High Finding 0。
- Product Owner、Architect、Security、QA、SRE 具名复核。AI 自评不能批准，不保存 Chain-of-Thought。

## 失败与阻断处理

- 任一硬门失败：阶段 `FAIL`，返回拥有该缺陷的最小子阶段。
- DEV 外部资源缺失：`BLOCKED`，不得用 Fake 结果宣称阶段完成。
- 禁止整体重写、降低门槛或关闭安全检查。

## 完成响应格式

```text
Status:
Release candidate SHA/digest:
Changed files:
Full validation results:
P1-CP01..P1-CP05:
DEV evidence:
Open risks/blockers:
Phase 02/03 readiness: yes | no
```
