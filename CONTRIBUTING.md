# Contributing

本仓库正按 Phase 01 计划从单体 Demo 渐进演进为双 Agent Monorepo。所有贡献（人类或 Coding Agent）遵守以下规则。

## 开发流程（TDD）

1. 先读当前实现、测试和依赖文档，再改代码。
2. 使用 RED-GREEN-REFACTOR：先添加会失败的测试并运行确认失败，再写最小实现使其通过，最后重构。
3. 提交前运行目标测试、`npm run lint`、`npm run typecheck`、`npm run build`（引入 Python 代码后同样运行其锁定的 lint/type/test 命令）。
4. 迁移过程中 `src/tests/` 现有回归测试必须持续通过；不得删除或修改无关测试。

## 最小变更原则

- 只修改当前任务所需文件；禁止顺手清理、格式化或重构无关代码。
- 对不明确的需求列出假设与阻断点，不静默选择高风险解释。
- 使用最小实现，不为未来能力提前建复杂抽象。
- 渐进迁移：按独立小 PR 推进（基线/骨架/契约/搬迁），禁止一次性 Monorepo 重构；移动文件使用 `git mv` 保留历史。
- 不恢复用户已删除的内容。

## 双人审查

以下变更必须至少两名审查者（其中一名为 Tech Lead 或对应领域 Owner）：

- 共享契约（`packages/domain-contracts/` 及其 Schema）。
- 数据库 Migration。
- Tool Policy、权限分级（L0–L4）与审批逻辑。
- `harness-core` 行为语义。

## Secret 与配置边界

- 禁止把 API Key、Token、Client Secret 或任何凭据提交到 Git（包括测试 fixture 与文档示例）。
- 配置中只允许 Secret Reference，Secret 值仅存在于企业 Secret Manager。
- 日志、Trace、错误响应不得回显 Secret；发现泄漏立即轮换并记录事件。
- 本地开发只用合成数据和 Mock Credential；真实 Provider 必须显式 Feature Flag 开启，默认 `mode: mock`。

## 远端访问边界

- 普通 PR CI 只运行无 Secret 的 Unit/Contract/Mock/Eval 测试；不得访问 DEV/SIT/UAT/PRD 或真实外部写 API。
- 部署与远端验证走受保护流水线（批准分支/Tag、人工 Environment Approval、自托管 Runner、OIDC 短期身份）。
- 任何人不得从开发机直接连接生产环境执行热修或手工 SQL；生产操作只通过受保护 CI/CD 或经审批 Runbook。
- 远端结果只回传脱敏报告、hash 与 Trace/Audit Reference，不上传凭据或业务原始数据。

## 依赖管理

- 版本必须锁定；新增依赖前检查许可证、维护状态和安全公告，并在 PR 说明用途。
- 优先使用标准库和已有组件。

## ADR

架构决策记录在 `docs/adr/`。改变已接受 ADR 的结论需要新 ADR 并链接旧编号，不直接改写历史决策。
