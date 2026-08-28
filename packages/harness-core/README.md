# harness-core — 双 Agent 共享 Harness（Phase 01 / Subphase 04）

Content Agent 与 Campaign Agent 共用的最小可信闭环（ADR-001）。
Phase 01 只使用 Fake Model / Fake Tool / 本地数据；不暴露 Shell、任意 URL、
原始 SQL、文件系统或真实 Secret Tool。

## 模块

| 模块 | 职责 |
|---|---|
| `tools` | 类型化 Tool Registry：Schema（pydantic）、Handler、Level（L0–L4）、Agent Allowlist、版本；运行前冻结，运行时不可扩大 |
| `permissions` | deny -> policy -> approval 三层权限门；宿主代码裁决，模型自报无效；L4 一律拒绝，L3 需宿主验证的一次性审批令牌 |
| `hooks` | 冻结 Hook 顺序：`on_input -> before_model -> (before_tool -> after_tool/on_tool_error -> before_model)* -> before_stop -> after_run`；每个 Hook 强制写审计，审计不可用即 fail closed |
| `context` | 最小上下文：大结果只以 URI + sha256 + 摘要（`ArtifactRef`）进入上下文 |
| `memory` | 只保存稳定偏好（Key Allowlist + 尺寸上限），按 Agent/用户/品牌/市场命名空间隔离 |
| `goal` | Goal Check 只验证必需证据 Artifact 是否存在；不修改 Workflow 状态，不签发业务/Medical 结论 |
| `loop` | HarnessLoop：单 Run 时间线、权限裁决记录、被拒决定清单、证据聚合、max_steps 防失控 |
| `model` | 类型化 ModelAction（ToolCall/Stop）与脚本化 FakeModel；不可解析输出 -> 类型化错误 |

## 安全不变量（负向测试验证）

- 未注册 Tool、跨 Agent Tool、无审批 L3、任意 L4：拒绝率 100%。
- Registry 冻结后注册直接抛错 —— Prompt Injection 无法在运行时扩大工具集。
- 无证据的 Stop 永远不会产生 `SUCCEEDED`。
- 审计 Sink 失败时 Tool 不执行，Run 以 `audit_unavailable` 失败（fail closed）。
- 恶意/非法参数只产生类型化错误反馈，Handler 不执行。

## 开发命令

```bash
python3 -m pip install -e ".[dev]"
python3 -m pytest     # 45 个 Unit/Workflow/Security 测试
python3 -m mypy       # strict
```

仓库根目录亦提供 `npm run harness:test` 与 `npm run harness:typecheck`。

## 边界

不包含真实业务 Workflow、企业 IAM、Queue Broker、外部 Connector 或营销
Prompt/渠道 SDK/供应商 Secret（ADR-001 边界约束）。LangGraph Workflow 封装
与持久化 Checkpoint 集成在后续 Subphase 接入；本包不引入第二套 Runtime
（ADR-002）。
