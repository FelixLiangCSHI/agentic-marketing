# P1-CP03 证据：共享 Harness 最小闭环（Phase 01 / Subphase 04）

结果：**BLOCKED（待 Security + QA 人工评审）**

按 Subphase 04 提示词规则，AI 自评不允许给出 PASS。本文件汇总证据，供人工评审后改判。

## 变更范围

- 新增 `packages/harness-core`（Python 包 `harness_core`）：
  - `tools.py`：类型化 Tool Registry（pydantic Schema、Handler、L0–L4 Level、Agent Allowlist、版本、`freeze()`）。
  - `permissions.py`：deny -> policy -> approval 三层权限门；宿主裁决；L4 一律拒绝；L3 需宿主验证的一次性审批令牌。
  - `hooks.py`：冻结 Hook 顺序状态机 + 强制审计（`AuditSink`），审计失败抛 `AuditUnavailableError`。
  - `context.py`：`ArtifactRef(uri, sha256, summary)` 最小上下文打包。
  - `memory.py`：Key Allowlist + 512 字节上限，按 Agent/用户/品牌/市场命名空间隔离。
  - `goal.py`：仅基于必需证据 Artifact 的纯函数 Goal Check。
  - `model.py`：类型化 ModelAction 与脚本化 FakeModel。
  - `loop.py`：`HarnessLoop.run()` —— 时间线、拒绝清单、证据聚合、`max_steps` 防失控、审计失败 fail closed。
- 测试 `packages/harness-core/tests/`：45 个测试（RED-GREEN：先写失败的负向测试，再实现使其通过）。
- CI：`.github/workflows/ci.yml` 新增 `harness` Job（pytest + mypy strict）。
- 根 `package.json` 新增 `harness:test` / `harness:typecheck`。

## 决策

- Harness 为 Python 包（Worker/API 为 Python；ADR-001 共享 Harness）。
- 本 Subphase 不引入 LangGraph 依赖：范围仅要求 Fake Model + Fake Tool 的最小闭环；Workflow Runtime 集成留待后续 Subphase（不违反 ADR-002——未引入第二套 Runtime）。
- Registry 在 Run 前必须 `freeze()`；运行时注册抛 `ToolRegistrationError`，从机制上封死 Prompt Injection 扩大工具集的路径。
- 模型自报的"已批准/权限"字段无效：审批只认宿主 `ApprovalVerifier` 校验的一次性令牌。

## 命令与结果

| 命令 | 结果 |
|---|---|
| `packages/harness-core: python -m pytest` | 45 passed |
| `packages/harness-core: python -m mypy`（strict） | Success: no issues found in 10 source files |
| `apps/api: python -m pytest` | 35 passed, 29 skipped（DB 集成测试需本地 Postgres，CI 中运行） |
| 根 `npm test` | 97 pass, 0 fail |

## 门禁指标（来自负向测试）

| 指标 | 结果 |
|---|---|
| 未审批 L3 调用拒绝率 | 100%（`content.publish` 无令牌 / 伪造令牌 / 令牌复用均拒绝） |
| L4 调用拒绝率 | 100%（`campaign.delete_production` 即使带令牌也拒绝） |
| 未注册 Tool 成功次数 | 0（未注册 / 冻结后注册均拒绝或抛错） |
| 跨 Agent Tool 调用拒绝率 | 100%（Content Agent 调 campaign.* 被 policy 层拒绝，反向同理） |
| 非法参数导致 Handler 执行次数 | 0（Schema 校验失败只回类型化错误观察） |
| 无证据 Stop 判定 SUCCEEDED 次数 | 0 |
| 审计不可用时 Tool 执行次数 | 0（Run 以 `audit_unavailable` FAILED，fail closed） |
| Hook 乱序执行 | 0（非法转移抛 `HookOrderError`，状态机表冻结） |
| 测试输出中的 Secret 泄漏 | 0（无任何真实凭据；全部合成数据） |

## 被拒工具调用证据（示例，摘自测试断言）

- `content.publish`（L3，无审批令牌）→ `Decision(allowed=False, layer="approval", reason="approval_required")`；Handler 未执行；拒绝记入 `RunReport.denied_decisions` 与审计时间线。
- `campaign.delete_production`（L4）→ `Decision(allowed=False, layer="deny", reason="level_l4_denied")`。
- Content Agent 调 `campaign.plan` → `Decision(allowed=False, layer="policy", reason="agent_not_allowed")`。
- 注入文本诱导调用 `shell.exec`（未注册）→ `layer="deny", reason="tool_not_registered"`。

## 阻断与后续

- P1-CP03 判定 BLOCKED，待 Security + QA 评审：权限门语义、审计 fail-closed 行为、Memory 隔离与 Hook 顺序表。
- 后续 Subphase 05 将在本 Harness 上接入双 Agent 骨架与错误分级恢复策略。
