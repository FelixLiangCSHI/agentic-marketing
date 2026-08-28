# P1-CP02 — Phase 01 / Subphase 03 持久层与 Migration 证据

> 记录日期：2026-08-28（UTC）
> Checkpoint 结果：**BLOCKED**（等待 Tech Lead + DBA 复核；按规则 AI 自评不能 `PASS`）
> 执行模式：`repo`；仅本地一次性 PostgreSQL 16 与 CI `postgres:16` 服务容器；未连接 DEV/SIT/UAT/PRD，未使用真实数据库 Credential。

## 1. 变更范围

| 区域 | 内容 |
|---|---|
| `apps/api/src/dmt_api/persistence/` | 域对象（frozen dataclass）、状态机、Repository、UnitOfWork、错误类型、测试辅助 |
| `apps/api/alembic.ini`、`apps/api/migrations/` | Alembic 配置与初始可逆 Migration `0001_core_approval_audit` |
| `apps/api/tests/db/` | PostgreSQL 集成测试（29 个用例；无 `DMT_TEST_DATABASE_URL` 时自动跳过） |
| `.github/workflows/ci.yml` | api job 增加一次性 `postgres:16` 服务容器（trust 认证，无长期口令） |
| `apps/api/pyproject.toml` | 新增 sqlalchemy 2.0.52、alembic 1.19.1、psycopg[binary] 3.3.4 |

## 2. Schema 摘要（Schema diff：空库 → `0001_core_approval_audit`）

| Schema.Table | 关键约束/索引 |
|---|---|
| `core.runs` | PK `run_id`；status/agent_type/environment CHECK；`version` 乐观锁列；`ix_core_runs_status` |
| `core.run_events` | PK `event_id`；`UNIQUE(run_id, sequence)`；event_type CHECK；**append-only 触发器** |
| `core.tasks` | PK `task_id`；status/attempt/max_attempts CHECK；lease_owner/lease_expires_at/version；`ix_core_tasks_run_id_status` |
| `core.task_dependencies` | 复合 PK；`task_id <> depends_on_task_id` CHECK；反向边索引（供递归可达性查询） |
| `core.workflow_journal` | PK `journal_id`；`UNIQUE(run_id, sequence)` |
| `core.outbox` | PK `outbox_id`；部分索引 `ix_core_outbox_pending`（`dispatched_at IS NULL`） |
| `approval.requests` | PK `approval_id`；approval_type/status CHECK；`version` |
| `approval.decisions` | PK `decision_id`；`UNIQUE(approval_id)`（一票制）；decision CHECK |
| `approval.tokens` | PK `token_id`；`UNIQUE(token_hash)`、`UNIQUE(approval_id)`；只存 SHA-256 hash |
| `audit.events` | PK `audit_id`；run/resource 索引；**append-only 触发器** |

## 3. 事务与设计决策

1. **同事务写入**：状态变化 + Run Event + Audit + Outbox 全部经 `UnitOfWork` 单事务提交；异常时整体回滚（有回滚负向测试）。
2. **只追加**：`core.run_events` 与 `audit.events` 由数据库触发器 `core.forbid_mutation()` 拒绝任何 UPDATE/DELETE，与应用角色无关。
3. **Task DAG 防循环**：写入依赖前锁定所属 Run 行序列化同一 Run 的 DAG 写入，再用递归 CTE 做可达性检查；自依赖由 CHECK + 代码双重拒绝。
4. **租约领取**：`UPDATE ... WHERE status='READY' AND version=:expected AND attempt < max_attempts ... RETURNING` 条件更新；并发领取只有一个成功；过期租约由 `reclaim_expired`（`lease_expires_at < now`）接管。
5. **Approval Token**：明文只在签发时返回一次，库中仅存 `sha256:` hash（唯一约束）；消费为原子条件更新（`consumed_at IS NULL AND expires_at > now`），双重/并发消费只有一个成功；审批人与请求人分离（`SeparationOfDutiesError`）。
6. **Repository 边界**：所有方法只返回 frozen Domain 对象；Session/SQL 不暴露给 Agent 或 API 层；模型/Agent 无原始 SQL 执行路径。
7. **Migration 可逆**：初始 Migration 在空库执行，无大表锁风险；downgrade 精确删除本版本创建的全部对象。

## 4. 命令与结果

| 命令 | 结果 |
|---|---|
| `python -m pytest`（无 DB 环境变量） | PASS：35 passed, 29 skipped（DB 测试正确跳过） |
| `DMT_TEST_DATABASE_URL=… python -m pytest` | PASS：64 passed / 0 fail |
| `python -m mypy`（strict） | PASS：18 源文件无错误 |
| `alembic upgrade head`（空库） | PASS |
| `alembic downgrade -1` → 全部表/触发器/Schema 移除 | PASS（`tests/db/test_migrations.py` 断言） |
| 再次 `alembic upgrade head` | PASS；append-only 触发器重建（断言 4 行触发器记录） |
| Web 回归 `npm test` | PASS：97 pass / 0 fail |
| `npm run typecheck` | PASS |

## 5. 门禁指标

| 指标 | 要求 | 实测 |
|---|---|---|
| Contract 与数据库字段/枚举一致率 | 100% | 100%（状态/类型枚举逐字取自 `dmt_api.contracts` v1 枚举，CHECK 约束同源） |
| Migration 往返 | 100% 通过 | 通过（empty → head → down one → head，pytest + CLI 双重验证） |
| Token 双重消费成功数 | 0 | 0（顺序 + 线程并发测试均只有一个赢家） |
| Task 循环写入成功数 | 0 | 0（自依赖与 3 节点环均被拒绝且无部分写入） |
| 历史 Event/Audit 被更新次数 | 0 | 0（数据库触发器直接报错） |

## 6. 索引理由与查询计划

- `ix_core_outbox_pending`（部分索引）：Outbox 分发器只扫描未分发消息 —
  `EXPLAIN SELECT * FROM core.outbox WHERE dispatched_at IS NULL ORDER BY created_at`
  → `Bitmap Index Scan on ix_core_outbox_pending`。
- `ix_core_tasks_run_id_status`：Worker 按 Run 轮询 READY 任务 —
  `EXPLAIN SELECT * FROM core.tasks WHERE run_id=… AND status='READY'`
  → `Index Scan using ix_core_tasks_run_id_status`。
- `ix_core_task_dependencies_depends_on`：递归可达性（防循环）沿反向边遍历。
- `UNIQUE(run_id, sequence)`：兼作事件顺序读取索引，防序列冲突。

## 7. 阻断与后续

- P1-CP02 最终 `PASS` 需 Tech Lead + DBA 复核本文件与 PR diff；本文件不含 Chain-of-Thought，仅保留结果与证据。
- 真实数据库（DEV 起）连接、Credential 注入与远端 Migration 执行仍走受保护流水线（见 Phase 01 总计划 §2.3），保持 `docs/phase01/blocked.md` 中的阻断项不变。
