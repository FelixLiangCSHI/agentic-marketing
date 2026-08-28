# Coding Agent Prompt — Phase 01 / Subphase 06

## 给 Coding Agent 的指令

实现 Queue/DLQ、Object Store、Secret Resolver、配置分层和持久恢复接口。Repo 中使用 Fake；企业 DEV 服务只通过受保护远端作业验证。

## 必须先读

1. [Phase 01 总计划](../../phase_01_scope_foundation_and_harness.md)
2. [前序 Prompt](../05_identity_approval_and_audit/prompt.md)。
3. Run/Task/Workflow Journal、Outbox、环境和 Secret 规范。

## 执行位置与权限

- 模式：`hybrid-dev`。
- 所有代码、测试、配置、IaC 和 Runbook 变更必须在 GitHub 分支/Worktree 中完成并经 PR 审查。
- Repo/普通 CI：Fake Queue/Object Store/Secret/Clock。
- DEV：企业自托管 Runner 连接独立 DEV Namespace。
- 不在 Repo、数据库或日志存 Secret 值；Coding Agent 不直接操作远端服务。

## 前置条件

- Subphase 05 Repo 部分为 `PASS`；DEV IAM 可 `PASS` 或明确 `BLOCKED`。
- Queue、Storage、Secret/KMS 工单和 Owner 已登记。

## 目标

使长任务支持至少一次投递、幂等、租约、重试、DLQ、取消、Checkpoint 恢复和受控对象存储。

## Scope

包含 Client Protocol/Fake、配置加载、对象键、Retry Policy、Worker 心跳和 DEV Contract。

不包含 Content/Campaign 业务 Worker 或 PRD 资源。

## 实施任务

1. 先写重复投递、Poison Message、Worker 崩溃、取消、Secret 缺失、未知配置字段和对象覆盖测试。
2. 实现 `QueueClient/FakeQueueClient`、`ObjectStore/FakeObjectStore`、`SecretResolver/FakeSecretResolver`、`Clock/FakeClock`。
3. Queue：至少一次、最大重试、指数退避+抖动、DLQ、lease、heartbeat、idempotency。
4. Object Store：环境/tenant/agent/run 前缀、hash、版本、MIME/大小、Malware Scan hook、不可原位覆盖。
5. 配置顺序：base -> environment -> agent -> workflow -> tenant/market；拒绝未知字段。
6. `mode: mock|sandbox|live` 默认 mock；真实模式缺 endpoint/quota/proxy/Secret Reference 即启动失败。
7. PRD 配置禁止 `.env` Secret。
8. 在 DEV 受保护 Job 运行最小 Queue/Storage/Secret Contract，不上传敏感响应。

## 验证命令与证据

- Queue/Storage/Config Unit/Contract/Recovery Test。
- 100 次重复消息、Worker restart、DLQ replay 和对象版本测试。
- DEV Namespace 隔离和 Secret 脱敏检查。
- Evidence：Queue events、object hashes、config hash、heartbeat、脱敏 Contract report。

## AI 质量 Checkpoint

执行 `P1-CP04`：

- 100 次重复投递重复副作用 0。
- Worker 恢复后 artifact hash/状态一致率 100%。
- Secret 泄漏 0；环境前缀串用 0。
- QA + SRE 复核；AI 自评不能批准。输出 `PASS / FAIL / BLOCKED` 和 Evidence，不保存 Chain-of-Thought。

## 失败与阻断处理

- DEV 服务未交付：Repo Fake 可 `PASS`，远端部分必须 `BLOCKED`。
- 重复副作用或对象覆盖：`FAIL`，返回 idempotency/version 层。
- 远端问题只通过 Repo 配置/IaC 修复，禁止控制台临时改动。

## 完成响应格式

```text
Status:
Changed files:
Fake and DEV results:
Recovery/duplicate results:
P1-CP04:
Evidence:
Blockers:
Ready for Subphase 07:
```
