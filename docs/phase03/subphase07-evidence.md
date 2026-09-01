# Phase 03 / Subphase 07 — Campaign Integration Quality Gate（Evidence Pack）

日期：2026-09-01 · 分支：`copilot/phase-03-align-with-repo` · 模式：`hybrid-dev-sit`（本仓库仅 mock/fake 部分）

## 1. Release Candidate 记录

| 项 | 值 |
|---|---|
| 被测代码基线（SP01–06 全部合入） | `3c86784ccfcbfd91d3dfa232fc2da17fe9675019` |
| RC 定稿方式 | 最终 RC SHA/Tag 由受保护流水线在打 Tag 时固化（本仓库 PR 无 Tag 权限） |
| 契约（Schema，冻结、additionalProperties: false） | `activation-request.v1`、`campaign-proposal.v1`、`campaign-dry-run.v1`、`connector-error.v1`、`performance-report.v1`、`strategy-recommendation.v1` |
| Migration head | `0005_raw_normalized_metrics`（0001→0005 正向/回退/再正向由 `apps/api/tests/db` 门禁覆盖） |
| 指标公式版本 | `fv1`（ctr、cpc、cpm、conversion_rate；缺失→`not_available`，绝不为 0） |
| Connector 配置 | `config/linkedin.yaml`、`config/google_ads.yaml`（`mode: mock`，API version 由 `env://` 注入，未硬编码） |
| Connector 版本 | `linkedin` 0.1.0（3-legged OAuth only）、`google_ads` 0.1.0（OAuth 默认；SA 需审批记录） |
| Runbooks | `docs/runbooks/campaign-reconciliation.md`、`docs/runbooks/channel-token-rotation.md` |
| Phase 04 SIT fixtures | `integration/fixtures/phase04_sit/scenarios.json`（每渠道 20 个确定性场景清单） |

## 2. 门禁运行结果（本仓库，全部 deterministic mock/fake）

| 门禁 | 命令 | 结果 |
|---|---|---|
| Phase 03 集成质量门 | `python -m pytest integration` | 58 passed（Phase 01 gate 12 + Phase 03 gate 46；每渠道 ≥ 10 场景，100% 通过） |
| campaign-draft | `pytest packages/campaign-draft` | 31 passed |
| connector-sdk | `pytest packages/connector-sdk` | 66 passed |
| linkedin connector | `pytest connectors/linkedin` | 46 passed |
| google_ads connector | `pytest connectors/google_ads` | 58 passed |
| campaign-activation | `pytest packages/campaign-activation` | 32 passed |
| campaign-metrics | `pytest packages/campaign-metrics` | 52 passed |
| 双语言契约 | `npm run contracts:test` + `pytest apps/api/tests/contracts` | TS 37 passed / Py 49 passed |
| apps/api（含 Migration） | `pytest apps/api` | 168 passed, 50 skipped（DB 门禁需 Postgres，CI 中运行） |
| 既有分析回归 | `npm test` / `npm run typecheck` / `npm run lint` | 134 passed / clean / clean |
| Secret 扫描 | `scripts/check_no_secrets` + runtime secret scanning | 0 命中 |
| CodeQL | python / javascript / actions | 0 alerts |

Phase 03 门禁覆盖（`integration/test_phase03_gate.py`，两渠道各自参数化）：

1. 闭环：批准包 → Draft → Dry-run → Approval → Publish → Reconcile 证据 → Raw Metrics → Normalize → Report → DRAFT Strategy（策略步骤外部调用为 0）。
2. Dry-run 违规矩阵（未知账户、总/日预算越限、币种、目标、市场、排期时长、名称超长）：拦截率 100%，外部副作用 0。
3. 审批安全：无 Token / 哈希不匹配 → 外部写 0，拒绝率 100%。
4. 故障/恢复：Token 过期（fail closed，0 对象）、429（恢复后恰好 1 个对象）、超时已创建（先对账再重试，`RECONCILED`，0 重复）、供应商侧重复（收编不重建）、100 次重复投递（1 个对象）、Worker 重启重放（ledger 去重）、部分成功（停写 + 待审批补偿）、对账不可判定（DLQ 人工队列，0 重复创建）、后台手工修改（报告漂移、不覆盖）。
5. 指标/报告/策略 Eval：重复拉取幂等去重、缺失值保持 `not_available` 不为 0、报告数字 100% 携带 `source_raw_metric_ids` + `formula_version`、虚构证据触发 `StrategyEvidenceError`、strategy 模块零写工具（源码级断言）。

## 3. AI 质量 Checkpoint 判定

依据 §19 判定协议（结果只有 PASS / FAIL / BLOCKED；AI 自评不能批准，真实渠道证据缺失必须 BLOCKED，不得用 Mock 包装为通过）：

| Checkpoint | 仓内硬门（mock/fake） | 真实渠道（DEV/SIT 测试账户） | 综合判定 |
|---|---|---|---|
| P3-CP01 Draft 忠实映射 | 内容 hash 匹配 100%、必填字段 100%、确定性指纹 | 需 Marketing + Campaign Operator 具名复核 | 仓内 PASS / 阶段 **BLOCKED**（待人工签字） |
| P3-CP02 Dry-run 拦截 | 违规拦截率 100%、外部副作用 0 | 需真实账户/官方规格核验 | 仓内 PASS / 阶段 **BLOCKED** |
| P3-CP03 Approval/幂等/对账 | 无效审批写调用 0、100 次重复投递重复对象 0、未知结果先对账 100%、审计完整 | 需受保护 E2E 的 Approval/External ID/Audit 证据 | 仓内 PASS / 阶段 **BLOCKED** |
| P3-CP04 Report 数值/追溯 | 确定性计算一致率 100%、Raw 追溯 100%、虚构数值 0、缺失→0 次数 0 | 需 Data Owner + Marketing 复核真实拉数 | 仓内 PASS / 阶段 **BLOCKED** |
| P3-CP05 Strategy 证据/只读 | 证据链接率 100%、直接写 Tool 调用 0、恒为 DRAFT | 需 Marketing + Campaign Approver 抽样复核 | 仓内 PASS / 阶段 **BLOCKED** |
| P3-CP06 双渠道一致性/退出 | 每渠道 ≥10 mock 场景 100% 通过、未核验配置 0、Critical/High Finding 0 | **每渠道 ≥10 个测试账户场景**未执行（无凭据） | **BLOCKED** |

结论：任一真实渠道门禁缺失时 Phase 03 为 `BLOCKED`，不得宣称完成。本仓库交付的是可复核的 mock 证据 + 受保护流水线的执行清单；不存在被 Mock 包装的真实失败。

## 4. 外部对象 / 费用 / 清理

- 本仓库运行产生的“外部对象”全部位于进程内 mock transport，测试结束即销毁；真实外部对象 0，费用 0，需清理项 0。
- DEV/SIT 执行后：每个外部对象必须有 cleanup ticket 与 Owner，归档进本 Evidence Pack 的远端附录。

## 5. 未关闭阻断项（Phase 04 待办）

| 阻断项 | Owner | 出口 |
|---|---|---|
| LinkedIn / Google Ads 测试账户每渠道 ≥10 场景的受保护 E2E | QA + API Owner | 运行 `integration/fixtures/phase04_sit/scenarios.json` 清单并归档证据 |
| P3-CP01..CP06 具名人工签字（QA、API Owner、Marketing、Security、Data Owner） | 各 Owner | 签字记录附在远端 Evidence 附录 |
| OAuth/Developer Token/Proxy/FQDN 官方核验记录定稿 | IAM + Security | 按 `docs/runbooks/channel-token-rotation.md` 完成后方可 `sandbox` |
| RC Tag 固化 | Release Owner | 受保护流水线打 Tag 并回填本表 |

## 6. Phase 04 就绪度

- 代码/契约/迁移/门禁/Runbook/SIT 清单齐备，Repo 侧无未关闭 Critical/High。
- Phase 04 SIT 可直接消费：RC 基线 SHA、场景清单、Runbook、Secret 引用名（无值）、清理要求。
