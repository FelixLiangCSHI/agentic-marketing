# Phase 01 → 企业级部署 Gap Summary

> 版本：2026-08-28。
> 背景：Phase 01 全部在本地环境与 GitHub 仓库中完成，所有外部能力保持 `mode: mock` / Fake 实现（见 `config/base.yaml`、`docs/phase01/blocked.md`）。
> 本文档回答两个问题：**哪些 gap 现在就能在仓库里修**，**哪些 gap 必须等接入企业云端后才能关闭**。
> 主要焦点是后者（现在改不了的 gap）。

---

## 1. 现在改不了的 Gap（必须连上企业云端 / 依赖企业侧交付）

这些 gap 的共同点：需要真实 Credential、真实基础设施或企业侧 Owner 决策。按治理规则（`AGENTS.md`、`CONTRIBUTING.md`），Secret 值不进入仓库/CI，真实接入只走受保护流水线，因此这些项在仓库内**只能保留扩展点与 Fake 实现，无法提前关闭**。

### 1.1 身份与访问（IAM / SSO）

| Gap | 当前状态（仓库内） | 关闭条件（企业侧） | 阻断项 |
|---|---|---|---|
| 真实 SSO 登录 | `FakeIdentityProvider`（`apps/api/src/dmt_api/identity/provider.py`）；OIDC 适配层已就绪但未接真实 IdP | IAM 交付 DEV SSO App（OIDC 或 SAML+Broker），提供 issuer/client 配置 | B-02 |
| 真实角色/组映射 | 角色来自 Fake principal（`identity/roles.py`） | 企业目录的组→角色映射规则确认 | B-02 |
| OAuth 回调形式 | 仅保留扩展点，渠道真实授权阻断 | IAM/Network 决定内部 Redirect / Broker / 管理员授权 | B-07 |

### 1.2 基础设施（存储 / 队列 / Secret / 网络）

| Gap | 当前状态（仓库内） | 关闭条件（企业侧） | 阻断项 |
|---|---|---|---|
| 真实对象存储 | `FakeObjectStore`（内存实现，含大小/覆盖/恶意文件校验语义） | 对象存储工单交付 + endpoint/bucket 配置 | B-06 |
| 真实 Queue/DLQ | `FakeQueueClient`（内存 lease/attempt 语义） | 企业消息队列交付 | B-06 |
| 真实 Secret/KMS | `FakeSecretResolver`；配置只允许 `secretref://` 引用 | 企业 Secret Manager 交付并对接解析器 | B-06 |
| 托管 PostgreSQL（DEV/SIT/UAT/PRD） | 本地/CI 一次性 postgres:16 容器；44 个 DB 测试在无 `DMT_TEST_DATABASE_URL` 时 skip | 四环境托管 PG 工单交付 | B-06 |
| VM、域名、出站 Proxy、监控 | 无 | Operations/Network 工单交付 | B-06 |
| `deploy-dev.yml` 真实部署步骤 | fail-closed 占位（OIDC 短期身份框架已定义） | DEV 环境交付后填入真实部署目标 | B-06 |

### 1.3 外部 API / 供应商

| Gap | 当前状态（仓库内） | 关闭条件（企业侧） | 阻断项 |
|---|---|---|---|
| DeepSeek / 企业 LLM 真实调用 | `llm.mode: mock`；申请已获批但 Credential 不进仓库 | 受保护流水线注入 secretref，远端环境验证 | B-03（部分解除） |
| Embedding / 批准 RAG | 仅 Fake Contract | Product Data Owner/Schema/批准确认 | B-01、B-03 |
| 即梦媒体生成 | `media.mode: mock` | 区域/租户/认证/数据条款确认 | B-05（部分解除） |
| LinkedIn Marketing API | Fake Connector + Contract Test | 真实 Token 经企业侧注入（Phase 03 门禁） | B-04（部分解除） |
| Google Ads | Fake Connector | Developer Token 获批（未确认） | B-04 |

### 1.4 只能在真实环境验证的质量属性

即使代码在仓库内写完，以下验证**必须**在企业环境执行，本地无法给出可信结论：

- 真实 DB 下的并发行为与锁竞争（如 run-event 序号分配在高并发下的表现）；
- `/api/health/ready` 对真实 DB / IdP 的依赖检查（当前只校验本地配置）；
- 真实网络下的出站 Proxy、超时、重试与配额（`quota_per_minute` 等字段目前为空）；
- 幂等外部写（ADR-006）对真实渠道 API 的端到端验证；
- SSO 全链路（登录、Token 刷新、登出、时钟偏移）；
- 性能/容量基线、监控 Dashboard 与告警实际触发。

### 1.5 企业侧决策/签字类（非编码问题）

- 范围冻结决策表 Owner 签字（B-08）；
- 真实 Medical Reviewer 指定（B-09）——在此之前审批链只保留 Medical 角色占位，Agent 不得产出最终医疗批准。

---

## 2. 现在就能改的 Gap（不需要企业云端）

以下问题在 Phase 01 代码审查中已识别，均为**纯仓库内修复**，不依赖任何企业资源，建议在接入企业环境前完成：

| # | 问题 | 位置 | 优先级 |
|---|---|---|---|
| 1 | 审批令牌持久化消费未绑定 `tool_name`/`agent_type`（与 Fake verifier 语义分裂，影响 ADR-003） | `apps/api/src/dmt_api/persistence/repositories.py` | High |
| 2 | `list_approvals` 无 tenant/run/requester 作用域过滤 | `apps/api/src/dmt_api/routes/approvals.py` | High |
| 3 | Task 依赖可跨 run 引用，破坏 run 隔离 | `apps/api/src/dmt_api/persistence/repositories.py` | High |
| 4 | run-event 序号用 `max(sequence)+1`，并发下撞唯一约束 | 同上 | High |
| 5 | workbook 级 `canProceed` 用 `some(...)`，无效 sheet 数据可混入确定性指标（ADR-005） | `src/server/parsing/spreadsheet-parser.ts` + `src/analysis/snapshot-engine.ts` | High |
| 6 | 人口统计排名混用 count / percentage 单位 | `src/analysis/metrics-engine.ts` | High |
| 7 | 上传缺失 `Content-Length` 时先缓冲后校验，存在 DoS 面 | `src/app/api/parse/route.ts` | Medium |
| 8 | `/ready` 未检查 DB 等本地依赖（检查逻辑可先写好，真实验证见 §1.4） | `apps/api/src/dmt_api/routes/health.py` | Medium |
| 9 | OIDC `nbf` 畸形值抛裸异常变 500 | `apps/api/src/dmt_api/identity/oidc.py` | Medium |
| 10 | 模型输出文案可夹带未受支持的数值断言（ADR-005 治理） | `src/agents/action-plan-agent.ts` | Medium |
| 11 | 环比访客变化的粒度推断基于全部记录而非可比记录 | `src/analysis/metrics-engine.ts` | Medium |
| 12 | domain-contracts TS 类型未编码 schema 约束（pattern/min-max 等） | `packages/domain-contracts/src/types.ts` | Low |

此外还可以现在完成：真实适配层的**接口与配置骨架**（LLM/Queue/ObjectStore/Secret 的 live-mode 客户端骨架 + 配置校验 + 契约测试），使企业环境交付后只需填入 `secretref://` 与 endpoint 即可切换。

---

## 3. 切换路径概览（mock → 企业级）

1. **仓库内（现在）**：修复 §2 全部 High/Medium 项；补齐 live-mode 适配层骨架与负向测试。
2. **企业交付后（B-06 解除）**：填入 DEV 环境 endpoint/secretref → `deploy-dev.yml` 去掉 fail-closed 占位 → 在 DEV 跑 DB migration（空库升级→降级→再升级）与 44 个 PG 测试。
3. **IAM 交付后（B-02/B-07 解除）**：接入真实 OIDC，替换 FakeIdentityProvider，验证自批拒绝/Token 原子消费（P1-CP03 在真实 IdP 下复验）。
4. **供应商 Credential 注入后（B-03/B-04/B-05）**：受保护流水线内逐一将 `mode: mock` → `sandbox` → `live`，每步保留幂等写与审批门禁验证。
5. **签字项（B-08/B-09/B-10 系列）**：不阻塞编码，但阻塞真实晋级。

> 原则不变：阻断项解除前，仓库与普通 CI 一律保持 `mode: mock` / Fake，Secret 值只存在于企业侧。
