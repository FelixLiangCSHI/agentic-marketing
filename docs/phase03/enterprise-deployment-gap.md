# Phase 03 → 企业级部署 Gap Summary

日期：2026-09-01 · 基线：`ebaeaf2`（Phase 03 SP07 合入后）· 来源：Phase 03 代码审查 + `docs/phase03/subphase07-evidence.md`

本文档回答一个问题：**当前"本地 + GitHub repo + mock"的开发模式下，哪些 gap 现在就能修，哪些必须等接入企业云端环境（Vault / Postgres / Redis / OIDC IdP / 真实渠道账户 / 受保护流水线）之后才能关闭。**

判定原则：

- **现在可改**：纯代码逻辑缺陷，用现有的 fake/mock 测试基建即可验证，不依赖任何真实外部系统。
- **云端才能改（本文重点）**：修复本身依赖企业基础设施的存在（共享存储、密钥系统、真实凭据、多实例运行时、受保护流水线），本地只能做到"接口预留 + mock 验证"，无法真正关闭风险。

---

## 1. 现在改不了的 Gap（必须连上企业云端）

### G1. 进程内状态 → 共享持久化状态（多实例部署失效点）

| 位置 | 现状 | 为什么本地改不了 |
|---|---|---|
| `connectors/linkedin/.../connector.py`、`connectors/google_ads/.../connector.py` 的 `self._ledger` / `_audit_hashes` | 幂等账本、审计哈希均为进程内 dict | 真正的修复是落到共享数据库（迁移 `0004_connector_operations` 已建表但连接器未接线到真实 DB）。本地可以把接口抽成 Protocol，但"多实例下不重复外部写"只有在企业 Postgres + 多副本运行时才验证得了 |
| `connectors/jimeng/.../worker.py`、`connectors/llm/deepseek/.../governance.py` | 限流器、预算控制、任务 journal 为进程内 | 集群级限流/预算需要 Redis 或等价共享组件；本地没有多实例拓扑，改了也只是 mock 自证 |
| `apps/api/.../repositories.py:866` outbox 轮询 | 无 `FOR UPDATE SKIP LOCKED` 租约 | SQL 改动本身可以先写（见 §2 F8 的"可预写部分"），但**并发正确性验证**需要真实 Postgres 多连接压测；本仓库 DB 门禁在 CI 中带 Postgres 才运行，本地 50 个 DB 测试是 skipped |

### G2. 凭据与密钥系统对接

| 项 | 现状 | 依赖 |
|---|---|---|
| `secretref://vault/...` 解析 | `config/*.yaml` 全部是引用，`infra_core/secrets.py` 只有引用校验和 fake resolver | 企业 Vault/Secret Manager 实例 + 运行时身份（K8s SA / IAM role）。本地永远拿不到真值，也不应拿到 |
| OAuth 3-legged 全流程 | `linkedin/auth.py`、`google_ads/auth.py` 只在 mock transport 上测试；LinkedIn rotated refresh token 未持久化 | 真实 LinkedIn Developer Access、Google Ads Developer Token、内部 OAuth/Redirect Broker。`expires_in` fail-closed 的代码可以先写（§2 F6），但 token 轮换闭环（`docs/runbooks/channel-token-rotation.md`）必须在 DEV/SIT 真实执行一次才算关闭 |
| OIDC IdP 对接 | `identity/oidc.py` 只对 fake JWKS 验证；readiness 在 IdP 未配置时仍 200 | 企业 IdP（issuer/audience/JWKS endpoint）就绪后才能做真实 token 验证与 fail-closed readiness 联调 |

### G3. 真实渠道验证（Evidence Pack §5 已列为阻断项）

- **每渠道 ≥ 10 个测试账户场景的受保护 E2E**：`integration/fixtures/phase04_sit/scenarios.json` 清单已备好，但执行需要 LinkedIn / Google Ads 测试账户凭据，本地无法运行。
- **Dry-run 规则 vs 官方规格核验**：预算/币种/市场/排期等校验矩阵目前只对 mock 规格拦截 100%；真实渠道 API 的实际错误语义（配额、政策拒绝、账户状态）只有连上测试账户才能校准。
- **对账（reconcile）真实性**：超时后"先对账再重试"的逻辑在 mock transport 上通过，但真实渠道的最终一致性延迟、供应商侧去重行为无法在本地模拟到位。
- **P3-CP01..CP06 具名人工签字**：QA / API Owner / Marketing / Security / Data Owner 的复核流程本身就是云端/组织侧动作。

### G4. 网络与出口治理

- **SSRF 防护的真实生效**：deepseek/jimeng 真实模式 endpoint 的 HTTPS + `allowed_fqdns` 白名单校验代码可以先写（§2 F7），但企业出口 Proxy、FQDN 白名单、私网拒绝策略需要在企业网络环境里联调。
- **TLS/Proxy 配置**：`config/*.yaml` 的 proxy 段目前无真实 proxy 可验证。

### G5. 发布与运行时基建

- **RC Tag 固化**：仓库 PR 无 Tag 权限，需受保护流水线打 Tag（Evidence Pack §1）。
- **CodeQL/Secret 扫描在受保护流水线的门禁化**：本地已跑，但作为发布闸门需要企业 CI 策略配置。
- **容器运行时验证**：`apps/api/Dockerfile` 的 digest 锁定、`HEALTHCHECK`、非 root 运行可以先改文件（§2 F9），但镜像扫描、准入策略、探针联调依赖企业 K8s/镜像仓库。
- **可观测性落地**：`docs/observability.md` 描述的指标/日志/追踪需要企业侧 collector 与告警系统。

---

## 2. 现在就能改的 Gap（不依赖云端，mock 测试即可验证）

以下均为纯逻辑缺陷，来自 Phase 03 代码审查，建议在接入云端之前先行修复：

| # | 严重度 | 位置 | 问题 | 
|---|---|---|---|
| F3 | High | `packages/campaign-activation/.../worker.py:232-248` | 状态置 `SUCCEEDED` 与 outbox/audit 写入非原子，事件可能永久丢失 |
| F4 | High | `packages/campaign-activation/.../worker.py:201-216` | 忽略 `reconcile_required`，可重试错误直接重试，可能重复外部副作用 |
| F5 | High | `packages/campaign-metrics/normalize.py` + `report.py` | normalize/report 不校验输入行同属一个 tenant/account/campaign/时间窗；dedupe key 与 `metric_id` 缺 tenant/account |
| F6 | Medium | `connectors/{linkedin,google_ads}/.../auth.py` | `expires_in` 缺失/为 0 未 fail-closed；rotated refresh token 被丢弃（持久化接线属 G2，fail-closed 逻辑可先改） |
| F7 | Medium | `connectors/{jimeng,llm/deepseek}` | `normalize_error()` 未复用 SDK 脱敏；endpoint 未做 HTTPS/白名单校验（校验代码可先写，真实生效属 G4） |
| F8 | Medium | `apps/api/.../repositories.py` | 锁序不一致（token↔approval 死锁风险）；outbox `SKIP LOCKED` SQL 可预写（并发验证属 G1） |
| F9 | Low | `apps/api/Dockerfile`、`routes/health.py` | digest 锁定、`HEALTHCHECK`、IdP 未配置时 readiness 应失败（真实探针联调属 G5） |
| F10 | Medium | 连接器 `execute()` | 仅做非空/前缀校验，应在连接器侧复核审批哈希（纵深防御），mock 即可测 |

---

## 3. Gap 关闭顺序建议

1. **现在（本地/CI）**：修完 §2 全部条目，保持 `src/tests/`、各 package pytest、契约 parity、CodeQL 持续绿色。
2. **接入企业云端第一步（DEV）**：Vault 引用解析 → Postgres 接线（连接器 ledger 落库、outbox 租约压测）→ OIDC IdP 联调（G1/G2 前半）。
3. **DEV/SIT**：OAuth 真实流程 + token 轮换 Runbook 演练、SSRF/Proxy 出口联调（G2/G4）。
4. **SIT（Phase 04）**：每渠道 ≥10 测试账户场景受保护 E2E、真实对账验证、Checkpoint 人工签字、RC Tag 固化（G3/G5）。

任一 §1 gap 未关闭时，Phase 03 判定维持 `BLOCKED`（与 Evidence Pack §3 判定协议一致），不得宣称企业级就绪。
