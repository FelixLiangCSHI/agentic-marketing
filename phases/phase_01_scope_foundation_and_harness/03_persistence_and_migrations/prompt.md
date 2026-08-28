# Coding Agent Prompt — Phase 01 / Subphase 03

## 给 Coding Agent 的指令

实现 PostgreSQL 持久模型、Alembic Migration 和事务边界。不得让模型或 API 直接执行原始 SQL；所有状态变化必须可恢复、可审计。

## 必须先读

1. [Phase 01 总计划](../../phase_01_scope_foundation_and_harness.md)
2. [前序 Prompt](../02_monorepo_api_and_contracts/prompt.md) 和已冻结 Contract。
3. `apps/api/`、`packages/domain-contracts/`、现有数据库配置约定。

## 执行位置与权限

- 模式：`repo`。
- 所有代码、测试、Migration 和配置变更必须在 GitHub 分支/Worktree 中完成并经 PR 审查。
- 使用本地 PostgreSQL 16/Fake Clock 测试；不连接 DEV/SIT/UAT/PRD。
- 不使用真实数据库 Credential，不手工修改远端 Schema。

## 前置条件

- Subphase 02 的 Contract 和 API 骨架为 `PASS`。
- PostgreSQL 逻辑 Schema 和 Migration Owner 已确认。

## 目标

建立 Run、Event、Task DAG、Workflow Journal、Approval、Audit 和 Outbox 的权威持久模型及可逆 Migration。

## Scope

包含 `core`、`approval`、`audit` 的初始 Migration、Repository/Service 和数据库测试。

不包含 Agent Loop、Queue Broker、SSO 或业务 Content/Campaign 表。

## 实施任务

1. 先编写非法状态、Task 循环、Token 重用、并发领取和 Migration 往返失败测试。
2. 创建 Alembic 配置及：
   - `core.runs`
   - `core.run_events`
   - `core.tasks`
   - `core.task_dependencies`
   - `core.workflow_journal`
   - `approval.requests/decisions/tokens`
   - `audit.events`
   - Transactional Outbox。
3. `run_events` 和 `audit.events` 只追加。
4. Task DAG 在写入时防循环；领取使用租约、版本号和条件更新。
5. Approval Token 使用 hash/opaque reference、唯一约束和原子消费。
6. 状态变化、Audit 和 Outbox 在同一事务或明确可恢复模式下完成。
7. Repository 返回类型化 Domain 对象，不向 Agent 暴露 Session/SQL。
8. 编写空库升级、降级一个版本、再次升级和并发测试。

## 验证命令与证据

- API/Domain Unit Test。
- Migration：empty -> head -> down one -> head。
- PostgreSQL Integration Test：非法转换、循环 DAG、lease、Token 并发消费、Outbox。
- 原有 Web 测试、类型检查和构建。
- Evidence：Schema diff、Migration 日志、事务测试、查询计划或索引理由。

## AI 质量 Checkpoint

执行 `P1-CP02`：

- Checkpoint 结果仅允许 `PASS / FAIL / BLOCKED`；AI 自评不能批准。
- Contract 与数据库字段/枚举一致率 100%。
- Migration 往返 100% 通过。
- Token 双重消费成功数 0；Task 循环写入成功数 0。
- 历史 Event/Audit 被更新次数 0。
- Tech Lead + DBA 复核；AI 自评不能 `PASS`。保存结果和 Evidence，不保存 Chain-of-Thought。

## 失败与阻断处理

- Migration 不可逆或会锁大表：`FAIL`，改为 expand/migrate/contract。
- 事务无法保证 Audit：阻断高风险路径，不加入静默补偿。
- 数据库工具缺失：只在项目既有依赖机制中恢复，不全局安装不相关工具。

## 完成响应格式

```text
Status:
Changed files/migrations:
Schema and transaction decisions:
Commands/results:
P1-CP02:
Evidence:
Rollback result:
Ready for Subphase 04:
```
