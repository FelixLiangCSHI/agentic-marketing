# Phase 02 / Subphase 06 Evidence — 合规引擎 + Critic + 医学/市场双轨审核 + 定向返工

日期：2026-08-28 · 分支：`copilot/phase-02-content-agent-mvp` · 模式：GitHub repo（`mode: mock`，无外部 HTTP）

## 1. 交付物

| 交付物 | 位置 |
|---|---|
| 确定性合规规则（10 条） | `packages/compliance/src/dmt_compliance/rules.py`（`CHECKED_RULES` 注册表；R-CITE-001 无引用 Claim、R-EXP-002 来源过期、R-MKT-003 跨市场引用、R-BAN-004 禁用表达、R-CMP-005 竞品对比、R-APR-006 伪造监管批准、R-DIS-007 缺失披露、R-LEN-008 标题超长、R-MED-009 缺失媒体、R-SPEC-010 推测当事实） |
| 结构化输出 | `contracts.py`（`ComplianceIssueV1`：rule_id/claim_id/severity/detail/source_reference/suggested_rework_node；`ComplianceResultV1`：policy_version/content_version_id/checked_rules/automated_status/result_hash） |
| 版本化政策 | `policy.py` + `fixtures/content-policy.json`（`ContentPolicyV1` v1.0.0，`extra=forbid`） |
| Critic（仅提问） | `critic.py`（`Critic` 协议只能返回 `CriticQuestionV1`，无判定通道；`FakeCritic(attempt_override=True)` 敌意模式证明"VERDICT: PASS"只能以问题形式出现） |
| 引擎（规则不可被覆盖） | `engine.py`（`automated_status` 在读取 Critic 之前由规则单独推导——结构上不存在从模型到状态的代码路径） |
| 评测门 | `evals.py`（`score_cases` → 每规则混淆矩阵、Critical/总体召回率、节点建议正确率、Critical 逃逸数、误报清单） |
| 定向返工验证 | `tests/test_workflow_rework.py`（建议节点 → `ReviewDecisionV1.rework_target` → journal 断言只有责任节点与受影响下游重跑；错误返工不清除问题） |
| Review API（双轨） | `apps/api/src/dmt_api/review_service.py` + `routes/reviews.py`（医学 + 市场双轨都批准才通过；轨道由服务端角色解析，前端字段被 `extra=forbid` 拒绝） |
| Review UI（只读） | `src/app/reviews/page.tsx` + `src/domain/review.ts`（并排：内容/Claim/来源/政策版本/内容版本；域模型含 BLOCKED 禁批、驳回必填理由+节点的客户端预校验） |
| CI 门禁 | `.github/workflows/ci.yml` 新增 `compliance` job；npm scripts `compliance:test`/`compliance:typecheck` |

## 2. 合规评测指标（P2-CP04 Mock 基线）

14 个标注案例（3 golden + 11 adversarial，覆盖全部 10 条规则 + 组合案例）：

| 指标 | 门槛 | 实测 |
|---|---|---|
| Critical Recall | 100% | **100%**（R-CITE-001/R-EXP-002/R-MKT-003/R-BAN-004/R-APR-006 全命中） |
| 总体 Recall | ≥95% | **100%** |
| 建议返工节点正确率 | ≥95% | **100%** |
| Critical 逃逸 | 0 | **0** |
| 误报（golden 案例 FP） | 0 | **0**（含 near-miss 措辞案例） |

每规则混淆矩阵（tp/fn/fp/tn）：R-APR-006 2/0/0/12 · R-BAN-004 2/0/0/12 · R-CITE-001 2/0/0/12 · R-CMP-005 1/0/0/13 · R-DIS-007 1/0/0/13 · R-EXP-002 1/0/0/13 · R-LEN-008 1/0/0/13 · R-MED-009 1/0/0/13 · R-MKT-003 1/0/0/13 · R-SPEC-010 1/0/0/13。
另有负向测试证明门禁语义：故意漏检的 Critical 案例使 `critical_recall=0`、`critical_escapes=1`（逃逸可被发现）。

## 3. 审核与返工语义（服务端强制）

- 轨道映射：`TRACK_FOR_ROLE`（medical_reviewer→医学、marketing_reviewer→市场）；客户端伪造 `track` 字段 → 422
- Artifact hash 绑定：决策必须携带当前 `artifact_hash`，过期 → 409 `stale_artifact`
- 职责分离：创建者不能审核自己内容（403）；同一身份不能同时决定两条轨道（403）
- 规则权威：`automated_status=BLOCKED` 时任何人批准 → 422 `invalid_decision`；只能驳回并指定返工节点
- 驳回必填：理由 + `rework_target ∈ {fact_issue, copy_issue, asset_issue}`
- 内容变更：`/content-changed`（仅创建者）→ 旧批准 `INVALIDATED`、revision+1、旧 hash 立即失效
- 定向返工（journal 证据）：copy_issue → 仅 `generate_copy`+`compliance_check` 重跑（facts/media 各 1 次）；fact_issue → 全下游重跑；asset_issue → 仅 `generate_media` 重跑；错误返工目标不会清除确定性 Issue（同一 issue_id 集合再次命中）

## 4. 命令与结果

| 命令 | 结果 |
|---|---|
| `packages/compliance: python3 -m pytest` | 27 passed（规则×10、引擎/敌意 Critic、评测门、定向返工×4） |
| `packages/compliance: python3 -m mypy` / `mypy tests` | strict，0 错误 |
| `apps/api: python3 -m pytest` | 112 passed / 48 skipped（新增 review 路由 15 项） |
| `apps/api: python3 -m mypy` | 0 错误（tests 下 2 个既有 db 测试告警为存量，与本次无关） |
| `npm test` / `npm run typecheck` / `npm run lint` / `npm run build` | 121 pass（新增 review-ui 8 项）/ 全绿 |
| 全量回归 | harness 45、infra 43、product-rag 55、content-workflow 28、deepseek 36、jimeng 44、evals+integration 17、contract 37+ts |
| Secret 扫描 | 0 发现 |
| CodeQL（python/javascript/actions） | 见最终提交（目标 0 告警） |

## 5. Prompt 任务映射

| 任务 | 状态 |
|---|---|
| 1. 测试先行：禁用词/过期 Claim/缺披露/跨市场/竞品对比/伪造批准/自我批准/错误返工 | 完成 |
| 2. 规则输出 rule ID、claim ID、严重度、来源、建议节点 | 完成 |
| 3. Critic 仅提问，不能翻转规则失败 | 完成（结构性保证 + 敌意 Critic 测试） |
| 4. Review UI 并排展示内容/Claim/来源/政策/版本 | 完成（只读；决策走 API） |
| 5. 驳回需理由+目标节点，仅相关下游失效 | 完成 |
| 6. 服务端医学/市场角色校验、artifact hash、职责分离 | 完成 |
| 7. 内容变更使旧批准失效 | 完成 |
| 8. 混淆矩阵、Critical/总体召回、误报分析 | 完成（见 §2） |
| 9. DEV 实名审核人 UAT | `BLOCKED`（B-09：真实 Medical/Marketing Reviewer 与 DEV SSO 未就绪） |

## 6. P2-CP04 / P2-CP05

**P2-CP04（合规评测门）：Mock 基线 `PASS` 证据已备 / 真实数据集 `BLOCKED`**
- Mock 标注集达标：Critical Recall 100%、总体 100%、节点正确率 100%、逃逸 0（§2）
- 真实市场政策与真实内容样本的标注集未提供 → 真实数据集评测 `BLOCKED`

**P2-CP05（人工审核 UAT）：`BLOCKED`**
- 双轨审核、hash 绑定、职责分离、失效语义均有 API 级测试证据
- 实名 Medical/Marketing Reviewer 在 DEV 完成端到端 UAT 依赖 B-09（审核人任命）与 B-05（DEV SSO/Credential）→ `BLOCKED`；AI 自评不能替代人工批准。未保存 Chain-of-Thought

## 7. 风险与阻断

- B-09 沿用：真实 Medical/Marketing Reviewer 未任命 → UAT `BLOCKED`
- B-05 沿用：DEV SSO/Portal 会话桥接未发放 → Review UI 决策操作保持只读
- 新增说明：Review 存储为进程内注入实现（语义完整、可测试）；Postgres 持久化沿用既有 UnitOfWork 模式接入，属后续接线工作
- 沿用：B-01（Product schema）、B-03（企业 LLM 审批）、B-10（即梦供应商确认）

## 8. Ready for Subphase 07

是 —— 确定性合规门 + Critic + 双轨人工审核 + 定向返工全链路已在 Mock 下证明；规则失败无法被模型或人工绕过，内容变更强制重新审核。
