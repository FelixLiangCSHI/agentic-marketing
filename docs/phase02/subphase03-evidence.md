# Phase 02 / Subphase 03 — Skill Registry 与 Content Workflow 骨架 证据记录

> 记录日期：2026-08-28（UTC）
> 执行模式：`repo`；仅 Fake Model / Fake Media / Fake Reviewer 与合成 fixtures，无真实 LLM/媒体 API、Credential 或 Medical Approval。
> 依据：git 历史中的 Phase 02 总控文档（blob `dd3c002…`）与 Subphase 03 Prompt（blob `f1439dc…`）；`phases/` 目录按规则不恢复。

## 1. 交付物

| 交付物 | 位置 |
|---|---|
| Skill 元数据 + Registry（最小加载、过期/撤销类型化阻断、guidance hash 校验） | `packages/content-workflow/src/content_workflow/skills.py` |
| 版本化节点 Contract（Brief/Copy/Media/Compliance/Review/Package，`schema_version 1.0`） | `packages/content-workflow/src/content_workflow/contracts.py` |
| LangGraph Content Workflow（Checkpoint/Journal、interrupt 暂停、定点返工、取消、Worker 重启恢复） | `packages/content-workflow/src/content_workflow/workflow.py` |
| Run Journal（节点/输入输出 hash/Workflow 版本） | `packages/content-workflow/src/content_workflow/journal.py` |
| Fake Model / Fake Media（结构化草稿；可脚本化无来源 Claim 与非法输出） | `packages/content-workflow/src/content_workflow/fakes.py` |
| Goal Check 证据桥接（harness-core，仅验证据存在） | `packages/content-workflow/src/content_workflow/evidence.py` |
| 合成 Skill fixtures（APPROVED/DRAFT/过期/撤销，brand/medical/market/channel） | `packages/content-workflow/fixtures/skills.json` |
| 测试（Registry 10 + Workflow 18） | `packages/content-workflow/tests/` |
| CI 门禁 | `.github/workflows/ci.yml`（新增 `content-workflow` job；security job 安装本包）；`package.json`（`contentworkflow:test`/`contentworkflow:typecheck`） |
| harness-core `py.typed` 标记（使下游 strict mypy 可消费其类型） | `packages/harness-core/{pyproject.toml,src/harness_core/py.typed}` |

API 路由未改动（用户要求：API 接口后续自行接线）；接入点 = `ContentWorkflow.start/resume/cancel/snapshot` 与 `WorkflowSnapshot` 读模型。

## 2. Workflow / Skill 版本

| 项 | 值 |
|---|---|
| Workflow 版本 | `content-workflow/1.0.0`（写入每条 Journal 与 Approved Package） |
| Workflow 图 | `ValidateInput -> RetrieveProductFacts -> BuildBrief -> GenerateCopy -> GenerateMedia -> ComplianceCheck -> HumanReview(interrupt) -> PackageApproved`；条件路由：无事实/合规失败 -> BLOCKED；返工 -> 责任节点 |
| Runtime | LangGraph `1.2.11`（ADR-002 唯一 Runtime；Checkpointer = InMemorySaver，可注入持久实现） |
| Skill fixtures 版本 | `skill-brand-core@1.2.0`、`skill-medical-us@2.0.0`、`skill-market-us@1.1.0`、`skill-channel-linkedin@1.0.0`（APPROVED）；`skill-channel-googleads-draft@0.1.0`（DRAFT）；`skill-medical-de-expired@1.0.0`（过期）；`skill-market-cn-revoked@1.0.0`（撤销） |
| Fake Model / Media | `fake-content-model-v1` / `fake-media-v1` |

## 3. 命令与结果

| 命令 | 结果 |
|---|---|
| `cd packages/content-workflow && python -m pytest` | PASS（28/28） |
| `cd packages/content-workflow && python -m mypy`（src 与 tests） | PASS（strict） |
| `cd packages/product-rag && python -m pytest && python -m mypy` | PASS（55/55 回归） |
| `cd apps/api && python -m pytest && python -m mypy` | PASS（97 passed, 48 skipped=需 Postgres，回归） |
| `cd packages/harness-core && python -m pytest && python -m mypy` | PASS（45/45 回归） |
| `cd packages/infra-core && python -m pytest` | PASS（43/43 回归） |
| `python -m pytest evals` / `python -m pytest integration` | PASS（5 / 12 回归） |
| `npm test` / `npm run lint` / `npm run typecheck` / `npm run build` | PASS（回归） |
| `python scripts/check_no_secrets.py` | PASS（clean） |

## 4. 实施任务映射（Prompt 任务 1–8）

| 任务 | 结果 | 证据 |
|---|---|---|
| 1 先写失败测试（Skill 过期/非法输出/拒绝返工/取消/Worker restart） | 完成 | `tests/test_skills.py`、`tests/test_workflow.py`（TDD；先 RED 后实现） |
| 2 Skill 元数据 + 最小加载 | 完成 | `SkillRegistry.load(agent/tenant/market/locale/channel/as_of)` 每 kind 只装一个最高版本 |
| 3 Skill 过期/撤销阻断；版本写入 Run | 完成 | `SkillExpiredError`/`SkillRevokedError`；`skill_versions` 入 State/Journal/Package；Skill frozen 只读 |
| 4 Content Brief（事实/禁用 Claim/披露/语气/渠道约束/来源） | 完成 | `ContentBriefV1`：facts 带 Citation、banned_phrases、required_disclosures、tone、max_headline_chars、skill_versions |
| 5 节点版本化 Schema + Journal/Checkpoint | 完成 | 所有节点 I/O 为 `schema_version 1.0` frozen 模型；每节点一条 `JournalEntryV1`（输入/输出 hash + workflow 版本） |
| 6 定点返工与失效图 | 完成 | `fact_issue -> RetrieveProductFacts`（失效 facts/brief/copy/media）；`copy_issue -> GenerateCopy`（保留 media）；`asset_issue -> GenerateMedia`；Journal 节点计数证明无关节点不重跑 |
| 7 Fake Model 结构化草稿；无来源 Claim 标记并阻断 | 完成 | `claim_citation_required` 违规 + `uncited_claims` 记录，状态 `BLOCKED`（人工审核前） |
| 8 Goal Check 只查证据 | 完成 | `CONTENT_GOAL_SPEC` + `build_goal_evidence`（harness-core `check_goal`）；缺 review_decision 即不通过，不代替 Reviewer |

## 5. P2-CP02 / P2-CP05（Fake 基线）结果

| 硬门 | 结果 | 证据 |
|---|---|---|
| Claim 来源覆盖率 100% | 满足 | 正常草稿全部 Claim 携带 Citation（`test_all_copy_claims_carry_citations`）；无来源 Claim → 标记+阻断 |
| 事实错误/虚构数字 = 0 | 满足（Fake 基线） | Claim 文本仅来自检索到的批准事实；虚构 Claim 场景被合规阻断 |
| 必需 Brief/Review 字段 100% | 满足 | frozen `extra="forbid"` 契约，全字段必填；非法 Review 决定 → 类型化失败 |
| 渠道硬规则通过 | 满足 | `headline_max_chars`/`banned_phrase`/`disclosure_required`/`media_present` 确定性检查 |
| 返工重跑无关节点 = 0 | 满足 | `TestTargetedRework` 三种 issue 的节点计数断言 |
| 模型输出非法 → 类型化失败 | 满足 | `InvalidNodeOutputError`，无默认值伪造成功 |
| Skill 未批准 → 只能 DRAFT | 满足 | google_ads DRAFT Skill：人工批准后仍 `DRAFT`，`package=None` |
| 软评分 >= 3.4/4 | BLOCKED | 需 Marketing/Medical 用 fixtures 人工复核；AI 自评不能 PASS，不收集 Chain-of-Thought |

**P2-CP02 / P2-CP05 状态：`BLOCKED`（非 FAIL）**

- AI 自评不能签发 `PASS`；需 Marketing/Medical Reviewer 按 fixtures 复核（B-09：真实 Medical Reviewer 未指定）。
- 真实 Model/媒体质量与软评分验收保持阻断（B-03/B-05：Credential 不进仓库/CI）。

## 6. 外部阻断项（沿用 docs/phase01/blocked.md）

- B-09：真实 Medical Reviewer 未指定 → HumanReview 仅 Fake Reviewer fixtures。
- B-03/B-05：真实 LLM/媒体 API Credential 不进仓库/CI → GenerateCopy/GenerateMedia 保持 Fake。
- B-01：Product Schema 未确认 → 事实来源沿用 Fake RAG 基线。
- Brand/Medical/Market/Channel Skill Owner 正式批准流程未建立 → fixtures 中的 APPROVED 状态为合成基线。

## 7. Ready for Subphase 04

Workflow 骨架、Skill Registry、Journal/Checkpoint 与返工语义就绪；Subphase 04（真实模型适配/持久化 Checkpoint/API 接线）可基于 `ContentWorkflow` 接入点启动。阶段退出仍受 P2-CP02/P2-CP05 人工复核约束。
