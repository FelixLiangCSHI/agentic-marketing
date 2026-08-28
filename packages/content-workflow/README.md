# content-workflow — Content Agent Workflow 骨架（Phase 02 / Subphase 03）

Skill Registry、版本化节点 Contract 和可暂停/恢复的 LangGraph Content
Workflow（ADR-002 唯一 Runtime）。本包只使用 Fake Model / Fake Media /
Fake Reviewer 与合成 fixtures；不连接真实 LLM/媒体 API，不签发真实
Medical Approval。

## 模块

| 模块 | 职责 |
|---|---|
| `skills` | Skill 元数据 + Registry：按 agent/market/locale/channel 最小加载；过期/撤销 → 类型化阻断；DRAFT 可用但只能产出草稿；guidance hash 校验 |
| `contracts` | 版本化节点输入/输出契约（Brief/Copy/Media/Compliance/Review/Package，`schema_version 1.0`，frozen） |
| `workflow` | LangGraph 图：`ValidateInput -> RetrieveProductFacts -> BuildBrief -> GenerateCopy -> GenerateMedia -> ComplianceCheck -> HumanReview -> PackageApproved`；Checkpoint/Journal、`interrupt` 暂停、定点返工路由、取消与 Worker 重启恢复 |
| `journal` | 每个节点一条证据记录：节点、输入/输出 hash、Workflow 版本 |
| `fakes` | FakeContentModel（结构化草稿；可脚本化输出无来源 Claim / 非法结构）与 FakeMediaGenerator |
| `evidence` | 将产物桥接为 harness-core Goal Check 证据（只验存在，不代替人工审核） |

## 关键不变量（测试验证）

- Claim 来源覆盖率 100%：无来源 Claim 被标记且在人工审核前阻断。
- 返工只重跑责任节点及其失效下游（`fact_issue`/`copy_issue`/`asset_issue`）。
- 模型非法输出 → 类型化失败，不用默认值伪造成功。
- Skill 过期/撤销 → 阻断；DRAFT Skill → 只能 `DRAFT`，永不 Approved Package。
- 取消后的 Run 不可恢复；Worker 重启后从 Checkpoint 恢复。

## 开发命令

```bash
python3 -m pip install -e "../product-rag" -e "../harness-core" -e ".[dev]"
python3 -m pytest     # 28 tests
python3 -m mypy       # strict
```

仓库根目录亦提供 `npm run contentworkflow:test` 与
`npm run contentworkflow:typecheck`。

## 边界

不包含真实 DeepSeek/即梦适配器、完整 Compliance 规则库、真实 Reviewer
集成或 API 路由（API 接入点由 `WorkflowSnapshot`/`ContentWorkflow` 提供，
API 层接线在后续完成）。
