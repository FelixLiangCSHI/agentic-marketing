# Phase 02 / Subphase 07 Evidence — 不可变 ApprovedContentPackage Builder + 全链路 RC

日期：2026-08-28 · 分支：`copilot/phase-02-content-agent-mvp` · 模式：GitHub repo（`mode: mock`，无外部 HTTP）

## 1. 交付物

| 交付物 | 位置 |
|---|---|
| Package 契约（§6.12 权威结构） | `packages/content-package/src/content_package/contracts.py`（`ApprovedContentPackageV1`：schema_version 1.0、`acp_` package_id、version、status、product/market/locale/audience、channel_variants、asset_uris+asset_hashes、`ClaimBindingV1`（text/source_id/source_version/source_excerpt_hash/expires_at）、compliance_result_id、`VersionBindingsV1`（policy/prompt/model/workflow/skill versions）、双轨 `PackageApprovalV1`、approved_at/expires_at、content_hash；frozen + extra=forbid + strict） |
| Canonical content hash | `canonical_content_hash()`：绑定 copy hash、Claim（文本+来源版本+excerpt hash）、资产 hash、Policy/Prompt/Skill/Model/Workflow 版本与渠道变体；任一字段变化 → hash 变化 → 新版本，旧审批（绑定旧 hash）自动失效 |
| 服务端 Builder（唯一 APPROVED 路径） | `builder.py`（`PackageBuilder`）：Compliance 必须 `PASS`、医学+市场双轨审批齐备且非同一身份、审批 hash 必须等于 canonical hash（`StaleApprovalError`）、Claim 100% 有引用（`UncitedClaimError`）、来源/审批/有效期未过期（`ExpiredInputError`）、Product/Skill/Policy 未撤销（`RevokedInputError`）、渠道变体齐备（`MissingChannelVariantError`）、资产未篡改（`AssetTamperedError`）；重复构建幂等（同 package_id/content_hash） |
| 版本化 append-only 账本 | `store.py`（`PackageStore`）：publish 使同 lineage 旧 APPROVED → `SUPERSEDED`（新账本条目，绝不原位修改）；revoke 记录原因；伪造复用 package_id → `DuplicateVersionError`；`audit_trail` 全历史可读 |
| 消费门（Phase 03 侧） | `consumable()`：非 APPROVED 账本状态 / Package 过期 / Product 撤销 / Claim 来源过期 / 审批未绑定 hash → 拒绝并给理由；`verify_package_integrity()` 供 Campaign Agent 独立验证 |
| 全链路 E2E | `tests/test_e2e_chain.py`：Request→RAG（fixtures 摄取）→Brief→Copy→Media→Compliance（内联门+引擎）→Review（approve）→Builder→Store→consumable；含驳回+定向返工后再批准、无引用 Claim 双重拒绝、Prompt Injection 文本当作数据 |
| Phase 03 Contract fixture（RC） | `fixtures/phase03/approved-content-package.sample.json`（确定性 RC 样本；测试逐字节比对 builder 输出并独立验证可消费） |
| CI 门禁 | `.github/workflows/ci.yml` 新增 `content-package` job；npm scripts `package:test`/`package:typecheck` |

## 2. Release Candidate

- RC 样本 package_id：`acp_81a8e00b178d77410a419879`
- RC content_hash：`sha256:08178ce6ccabc78a11414bc2c8aa94ec285cf735e3c284da8f738927efb17282`
- 绑定版本：policy 1.0.0 · prompt 1.0.0 · model `fake-content-model-v1` · workflow 0.1.0 · skill `copywriting@1.0.0`
- 审批：medical `emp-medical` + marketing `emp-marketing`，均绑定 RC content_hash

## 3. 命令与结果

| 命令 | 结果 |
|---|---|
| `packages/content-package: python3 -m pytest` | 33 passed（未批准×4、过期/撤销×5、hash 绑定×4、渠道变体×2、重复构建×2、Store 版本/审计/撤销×8、E2E×4、fixture×2、其余不可变性等） |
| `packages/content-package: python3 -m mypy` / `mypy tests` | strict，0 错误 |
| 全量回归 | harness 45、infra 43、product-rag 55、content-workflow 28、deepseek 36、jimeng 44、compliance 27、content-package 33、apps/api 112/48skip、evals+integration 17、contract 37+ts |
| `npm test` / `typecheck` / `lint` / `build` | 121 pass / 全绿 |
| Secret 扫描 | 0 发现 |
| CodeQL（python/javascript/actions） | 见最终提交（目标 0 告警） |

## 4. Prompt 任务映射

| 任务 | 状态 |
|---|---|
| 1. 测试先行：未批准/过期/hash 不匹配/缺渠道变体/资产修改/重复构建 | 完成 |
| 2. Builder 只接受已通过 Compliance + 人工 Review 的不可变版本 | 完成（typed 硬门，无任何静默修复路径） |
| 3. Canonical content hash 绑定 Claim/source version/excerpt hash/asset/Policy/Prompt/Skill/Model/approval/expiry | 完成 |
| 4. 任一字段变化 → 新版本 + 旧审批失效；旧 Package 保留审计 | 完成（StaleApprovalError + append-only 账本） |
| 5. 过期/撤销 Product、Skill、Policy 或 Package 阻断消费 | 完成（build 侧 + consume 侧双门） |
| 6. Content Request→RAG→Brief→Copy→Media→Compliance→Review→Package | 完成（E2E 测试） |
| 7. 注入 429/超时/Worker restart/Reject-Rework/恶意附件/Prompt Injection | Reject-Rework 与 Injection 在本包 E2E 覆盖；429/超时/重启/恶意附件由 deepseek(36)/jimeng(44) 既有对抗套件持续回归覆盖 |
| 8. 生成 RC 和 Phase 03 Contract fixtures | 完成（§2 RC + 逐字节校验 fixture） |

## 5. P2-CP01..P2-CP06

| Checkpoint | 结果 |
|---|---|
| P2-CP01（Product/RAG 引用） | Mock 基线 `PASS` 证据（Claim 来源 100%、过期/撤销资料 0——builder 与规则双门）；真实 Product API `BLOCKED`（B-01） |
| P2-CP02（Copy 质量/LLM） | Mock 基线 `PASS` 证据；真实 DeepSeek `BLOCKED`（B-03） |
| P2-CP03（媒体 Connector） | Mock 基线 `PASS` 证据；真实即梦 `BLOCKED`（B-10/B-05） |
| P2-CP04（合规评测门） | Mock 标注集 Critical Recall 100%、总体 100%、节点 100%、逃逸 0；真实数据集 `BLOCKED` |
| P2-CP05(人工审核 UAT) | `BLOCKED`（B-09 实名 Reviewer、B-05 DEV SSO） |
| P2-CP06（Package 门） | Mock 基线 `PASS` 证据：Schema/hash/approval 100% 通过（33 tests）、未批准或过期产物 0、修改后旧审批失效 100%；Medical/Marketing 实名签字 `BLOCKED` |

全部 Checkpoint 需 Product/Medical/Marketing/Security/QA 人工复核；AI 自评不能批准。未收集 Chain-of-Thought。

## 6. 风险与阻断

- 沿用：B-01（Product schema/API）、B-03（企业 LLM 审批）、B-05（DEV Credential/SSO）、B-09（实名 Medical/Marketing Reviewer）、B-10（即梦供应商确认）
- 说明：PackageStore 为进程内 append-only 实现（语义完整、可测试）；Postgres 持久化沿用既有 UnitOfWork 模式属后续接线
- 说明：`approved-content-package.v1` 双语言契约（domain-contracts）保持不变以不破坏既有门禁；Python 侧 §6.12 富结构为 Phase 03 权威输入，两者映射在 Phase 03 接线时统一

## 7. Phase 03 readiness

Mock 链路就绪：Phase 03 可用 `fixtures/phase03/approved-content-package.sample.json` + `verify_package_integrity`/`consumable` 独立验证开发 Campaign Agent。真实环境交接需先解除 B-01/B-03/B-05/B-09/B-10 并完成 P2-CP01..CP06 人工签字。
