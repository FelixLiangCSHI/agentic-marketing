# Phase 01 需求追踪矩阵

> 版本：2026-08-28。来源：Phase 01 总控文档（git 历史 `9f5defe`）。
> 状态图例：`DONE`（本子阶段完成）/ `PLANNED`（已排入后续子阶段）/ `BLOCKED`（见 `blocked.md`）。

## 1. 路线图需求追踪

| ID | 需求 | 目标子阶段 | Owner | 验证方法 (Definition of Done) | 状态 |
|---|---|---|---|---|---|
| R-01 | 仓库基线记录（HEAD、环境、命令结果、资产盘点） | 01 | Tech Lead | `docs/phase01/baseline.md` 存在且命令结果可复现 | DONE |
| R-02 | Scope/Non-scope、Agent 边界、外部 API 状态冻结 | 01 | Product Owner + Architect | baseline.md §5–6 + 本矩阵；P1-CP01 人工签字 | DONE（待签字） |
| R-03 | ADR-001..006 | 01 | Architect | `docs/adr/` 六份 ADR，编号/链接/结论无冲突 | DONE（待签字） |
| R-04 | CONTRIBUTING.md 与 AGENTS.md 治理规则 | 01 | Tech Lead | 覆盖 TDD、最小变更、双人审查、Secret、远端边界 | DONE |
| R-05 | 需求追踪矩阵（100% 覆盖、每项有 Owner/Phase/验证法） | 01 | Product Owner | 本文件 | DONE |
| R-06 | Monorepo 目录骨架（apps/packages/connectors/workers/…） | 02 | Tech Lead | 目录建立且现有 Next.js 路径可运行，78 回归通过 | PLANNED |
| R-07 | FastAPI Control API 骨架（health/me/runs/tasks/approvals） | 02 | Backend | `/api/health/live`、`/ready` 可运行；错误结构版本化 | PLANNED |
| R-08 | 跨语言 Domain Contract（8 个 v1 JSON Schema + 双端 fixtures） | 02–03 | Tech Lead + DBA | Golden/Invalid fixtures Python/TS 双端 100% 一致（P1-CP02） | PLANNED |
| R-09 | Run/Task/Approval/Audit Alembic Migration 与状态机 | 03 | DBA + Backend | 空库升级 head -> 降级一版 -> 再升级全部通过 | PLANNED |
| R-10 | harness-core 最小闭环（loop/tools/permissions/hooks/…） | 04 | Backend | 必测场景通过；Hook 顺序固定 | PLANNED |
| R-11 | 审批令牌、职责分离、SSO/IAM 适配层（含 Fake IdP） | 05 | Security + Backend | 自批拒绝、Token 原子消费、失效规则测试通过（P1-CP03） | PLANNED |
| R-12 | Queue/DLQ/ObjectStore/Secret 接口 + Fake、配置分层 | 06 | Backend | 重复投递副作用 0；未知配置字段拒绝；默认 `mode: mock` | PLANNED |
| R-13 | CI/CD（web/python/contracts/migration/security/eval smoke） | 07 | Tech Lead + SRE | `.github/workflows/ci.yml` 六段门禁绿色 | PLANNED |
| R-14 | 可观测性字段、Dashboard/告警定义、本地开发栈 | 07 | SRE | Trace 字段统一；infra/local 可启动 | PLANNED |
| R-15 | 集成质量门与阶段演示（8 步演示脚本，P1-CP04） | 08 | QA + SRE | 暂停/审批/恢复/取消/重启/隔离演示全部通过 | PLANNED |

## 2. Infra 申请追踪

| ID | 项 | Owner | 最晚日期 | 验证方法 | 状态 |
|---|---|---|---|---|---|
| I-01 | DEV/SIT/UAT/PRD VM、域名、网络（见总控 §9 矩阵） | Operations / Network | 2026-09-04 | 工单号 + 连通性验证 | BLOCKED（B-06） |
| I-02 | 托管 PostgreSQL 16（各环境独立） | DBA | 2026-09-04 | 工单号 + 连接测试 | BLOCKED（B-06) |
| I-03 | 对象存储、Queue/DLQ、Secret/KMS、监控、出站 Proxy | Operations / Security | 2026-09-04 | 工单号 | BLOCKED（B-06） |

## 3. API 时间门禁追踪

| ID | 项 | Owner | 最晚日期 | 状态 |
|---|---|---|---|---|
| A-01 | Product Data DEV 只读权限 | Product Data Owner | 2026-08-28 | BLOCKED（B-01） |
| A-02 | SSO DEV App | IAM | 2026-08-28 | BLOCKED（B-02） |
| A-03 | DeepSeek/企业 LLM 与 Embedding 内部审批申请 | Architecture / Security | 2026-08-28 | BLOCKED（B-03） |
| A-04 | LinkedIn Marketing API 与 Google Ads Developer Token 申请 | Product Owner | 2026-08-28 | BLOCKED（B-04） |
| A-05 | 即梦企业 API 区域/租户/认证/数据条款确认 | Marketing / Procurement | 2026-09-04 | BLOCKED（B-05) |
| A-06 | OAuth 回调形式（内部 Redirect / Broker / 管理员授权） | IAM / Network | 2026-09-04 | BLOCKED（B-07） |

所有 BLOCKED 项在解除前保持 `mode: mock` / Fake Connector；真实晋级保持阻断（见 ADR 与 blocked.md）。
