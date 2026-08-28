<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

# Coding Agent 工作规则

任何在本仓库工作的 coding agent 必须遵守：

1. 先读当前实现、测试和依赖文档，再改代码。
2. 对不明确需求列出假设与阻断点，不静默选择高风险解释。
3. 使用最小实现，不为 P1 能力提前建复杂抽象。
4. 只修改当前任务所需文件，禁止顺手清理无关代码；不恢复用户已删除的内容。
5. 使用 RED-GREEN-REFACTOR：先看测试失败，再写最小代码使其通过。
6. 完成前运行目标测试、类型检查、构建和影响面审查；`src/tests/` 现有回归必须持续通过。
7. 对共享契约、Migration、Tool Policy 变更进行双人审查（见 `CONTRIBUTING.md`）。

## Secret 与远端边界

- 禁止把任何凭据写入代码、配置、fixture、日志或文档；配置只允许 Secret Reference。
- 本地与普通 CI 只用合成数据和 Mock Credential，默认 `mode: mock`；不访问 DEV/SIT/UAT/PRD 或真实外部写 API。
- 不直接连接远端服务器；部署与远端验证只走受保护流水线或经审批 Runbook。

## 架构约束

- 架构决策见 `docs/adr/`（共享 Harness、仅 LangGraph、副作用前审批、轮询无公网 Webhook、受控事实、幂等外部写）。
- 精确数值由确定性代码计算，模型输出不得覆盖原始指标。
- Content Agent 与 Campaign Agent 的 Session、Memory、Tool Set 与 Credential Namespace 相互隔离。
