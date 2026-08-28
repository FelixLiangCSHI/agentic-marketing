# Coding Agent Prompt — Phase 01 / Subphase 01

## 给 Coding Agent 的指令

在 `agentic-marketing` 仓库的独立分支或 Worktree 中执行本子阶段。先调查、再修改；实际完成文件和验证，不要只给建议。保持变更外科式，不恢复用户已删除的内容。

## 必须先读

1. [Phase 01 总计划](../../phase_01_scope_foundation_and_harness.md)
2. 仓库根目录的 `README.md`、`AGENTS.md`、`package.json`、`requirements.txt` 和现有测试入口。
3. 当前 `git status`、最近提交和目录树。

本子阶段是起点，没有前序 Prompt。

## 执行位置与权限

- 模式：`repo`。
- 仅在 GitHub Repo/本地 Worktree 修改架构文档、ADR、贡献规则和基线记录。
- 普通 CI 不使用真实 Secret，不访问 DEV/SIT/UAT/PRD。
- 不连接远端服务器，不执行基础设施变更，不申请或读取生产 Credential。

## 前置条件

- 能读取仓库当前默认分支。
- 已确认工作区现有未提交变更的归属；不得覆盖他人修改。
- Product、Medical、Marketing、Architecture、Security、IAM、Network、DBA、Operations Owner 至少有待确认清单。

## 目标

冻结 2026-10-30 MVP、Agent 边界、关键技术选择、API/Infra 阻断项和渐进迁移策略，建立所有后续子阶段可验证的单一事实来源。

## Scope

包含：

- 记录 HEAD、运行环境、现有测试和可复用资产。
- 定义 Scope/Non-scope、两个 Agent 的隔离边界和外部 API 状态。
- 创建 Phase 01 要求的 ADR、贡献规则和需求追踪。

不包含：

- 移动现有代码。
- 引入 FastAPI、LangGraph 或数据库实现。
- 真实 API、SSO、Queue 或云资源连接。
- 与本阶段无关的格式化、依赖升级或 UI 修改。

## 实施任务

1. 运行并记录：
   - `git rev-parse HEAD`
   - `git status --short`
   - `npm ci`
   - `npm test`
   - `npm run lint`
   - `npm run typecheck`
   - `npm run build`
   - `python -m unittest discover -s python_tests -v`
2. 记录基线失败，但只修复会阻断本阶段文档/测试的直接问题。
3. 盘点 `src/data-processing/`、`src/analysis/`、`src/domain/`、`src/agents/`、`src/tests/` 和 Python 本地原型，标记“复用/兼容/替换/延期”。
4. 创建或更新 Phase 01 指定的 ADR：
   - Shared Harness。
   - LangGraph only。
   - Approval before side effects。
   - Polling without public webhooks。
   - Controlled facts not memory。
   - Idempotent external writes。
5. 在 `CONTRIBUTING.md` 和 `AGENTS.md` 中写入 TDD、最小变更、双人审查、Secret 和远端访问边界。
6. 建立需求追踪矩阵，覆盖路线图、Infra、API 时间门禁、Definition of Done 和 Owner。
7. 对未决事项输出 `BLOCKED` 清单，不替业务方做高风险假设。

## 验证命令与证据

- 重新运行成功的基线命令，确认文档变更未破坏构建。
- 检查 ADR 链接、编号和相互结论没有冲突。
- 检查需求追踪率为 100%，每项都有 Owner、目标 Phase 和验证方法。
- Evidence：HEAD、命令结果、目录盘点、ADR、追踪矩阵、阻断项。

## AI 质量 Checkpoint

执行 `P1-CP01`：

- 硬门：Scope/Non-scope、依赖、路径、验收命令和 Infra/API 门禁全部可追踪。
- 质量门：无虚构现有能力、无 Critical 矛盾；软评分不低于 3.4/4。
- 由 Product Owner 和 Architect 复核。AI 自评不能签发 `PASS`。
- 输出 `PASS / FAIL / BLOCKED`、artifact hash 和 Evidence Reference；不提供 Chain-of-Thought。

## 失败与阻断处理

- 基线命令失败：记录原始错误和最小复现，标为 `FAIL`；不要宽泛修复。
- Owner/API/Infra 决策缺失：标为 `BLOCKED`，列出负责人和最晚日期。
- ADR 冲突：返回对应 ADR 修订，不进入 Subphase 02。

## 完成响应格式

```text
Status: PASS | FAIL | BLOCKED
Changed files:
Baseline commands and results:
P1-CP01 result:
Evidence references:
Assumptions and blockers:
Risks:
Ready for Subphase 02: yes | no
```
