# Coding Agent Prompt — Phase 01 / Subphase 02

## 给 Coding Agent 的指令

建立渐进式 Monorepo、Python Control API 骨架和跨语言 Domain Contract。先写失败测试，再写最小实现；保留现有 Next.js 和确定性分析能力可运行。

## 必须先读

1. [Phase 01 总计划](../../phase_01_scope_foundation_and_harness.md)
2. [前序 Prompt](../01_baseline_scope_and_adrs/prompt.md) 及其 `PASS` Evidence。
3. 当前 `AGENTS.md`、`package.json`、`tsconfig.json`、Next.js App Router 代码和现有 Domain 类型。

## 执行位置与权限

- 模式：`repo`。
- 在 GitHub Worktree 中完成代码、Schema 和测试。
- 不访问企业远端服务或真实 Secret；所有外部依赖使用 Fake。

## 前置条件

- Subphase 01 为 `PASS`。
- MVP ADR 和 Agent 边界已冻结。
- 当前基线测试结果可复现。

## 目标

新增生产目录骨架、可启动的 Python API、版本化 JSON Schema 和 Python/TypeScript 双端契约验证，同时避免一次性搬迁现有代码。

## Scope

包含：

- `apps/api/` Python 项目和健康检查。
- `packages/domain-contracts/schemas/` 的 v1 Contract。
- TypeScript/Python 使用同一 Golden/Invalid fixtures。
- 新目录骨架与兼容层。

不包含：

- 数据库 Migration 实现。
- Harness Loop、SSO、审批、Queue 或真实 Connector。
- 将整个 Web 立即移动到 `apps/web/`。

## 实施任务

1. 为 API 健康检查和契约验证先添加失败测试。
2. 建立 `apps/api/src/dmt_api/`、`apps/api/tests/` 和受版本锁定的 `pyproject.toml`。
3. 实现：
   - `GET /api/health/live`
   - `GET /api/health/ready`
   - Run/Task/Approval 路由的类型化占位，不返回虚假成功。
4. 在 `packages/domain-contracts/schemas/` 创建：
   - Run、Run Event、Task、Approval、Tool Call。
   - `ApprovedContentPackage`、`ActivationRequest`、`ConnectorError`。
5. 所有 Schema 限制状态枚举、格式、未知字段和 `schema_version`。
6. 创建共享 Golden/Invalid fixtures；Python 使用 Pydantic，TypeScript 使用一个受控 JSON Schema Validator。
7. 为现有 `src/domain/` 添加兼容 Adapter；不要同时移动和重写。
8. 更新开发命令和 CI 占位，使 Web 与 API 可分别验证。

## 验证命令与证据

- 运行现有 `npm test`、`npm run typecheck`、`npm run build`。
- 运行新 API Unit Test 和 Python Type Check。
- 运行 Python/TypeScript 同一 fixtures，结果必须 100% 一致。
- 验证 `/live` 只检查进程，`/ready` 不调用付费外部 API。
- Evidence：目录 diff、依赖理由、Contract 报告、健康检查响应、兼容测试。

## AI 质量 Checkpoint

执行 `P1-CP01` 和 `P1-CP02`：

- 需求/目录/接口覆盖率 100%。
- Golden/Invalid fixtures 双端一致率 100%。
- 状态不得使用自由文本；未知字段必须按契约拒绝。
- Critical/High Contract Finding 为 0。
- Tech Lead 独立复核；AI 自评不能批准。结果为 `PASS / FAIL / BLOCKED`，附 hash/Evidence，不收集 Chain-of-Thought。

## 失败与阻断处理

- 新依赖缺乏必要性或许可证/维护状态不明：`BLOCKED`。
- Contract 不一致：只修复 Contract/Adapter，不通过类型断言绕过。
- 现有测试回归：`FAIL`，定位影响面后最小修复。

## 完成响应格式

```text
Status:
Changed files:
Contracts and compatibility decisions:
Commands/results:
P1-CP01/P1-CP02:
Evidence:
Risks/blockers:
Ready for Subphase 03:
```
