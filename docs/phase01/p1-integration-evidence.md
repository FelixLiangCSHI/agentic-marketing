# Phase 01 集成质量门 Evidence Pack（Subphase 08）

- 日期：2026-08-28
- 阶段结论：**BLOCKED**（Repo 内全部硬门通过；DEV 受保护验证与具名人工签字未完成，AI 自评不得批准）

## 1. Release Candidate（不可变基线）

| 项 | 值 |
| --- | --- |
| 基线 SHA（验证时 HEAD） | `d5308fa43d7a4114dac4c7eef7797c9cef5edab5`（Subphase 08 提交在其上叠加，仅新增集成测试/CI Job/本文档） |
| 依赖锁 | `package-lock.json` sha256 前缀 `7af9839e81b5ac0f`；Python 依赖钉版本于各 `pyproject.toml` |
| Migration head | `0002_approval_binding`（往返 downgrade 验证通过） |
| 配置 hash（`AppConfig.config_hash()` 前 16 位） | dev `5d363c6e16be6d0c` / sit `dcb51965a1a3ac12` / uat `af5ba68d7f1f6223` / prd `b246890c7026d7fc` |
| 镜像 digest / SBOM | **BLOCKED** — 企业镜像仓库与扫描/SBOM 工具未指定 |

## 2. Fake 双 Agent Demo 与恢复测试（`integration/test_phase01_gate.py`，12 passed）

| 场景 | 证据 | 结果 |
| --- | --- | --- |
| 创建→执行→等待审批 | 无 token 的 L3 `content.publish` 被 approval 层拒绝，副作用未执行，任务 nack 等待 | 通过 |
| 拒绝 | 无效 token 重试仍被拒绝，`published` 证据不存在 | 通过 |
| 批准→恢复 | 授予一次性 token 后重投递（attempt 递增）完成目标；token 恰好消费一次 | 通过 |
| 取消 | `cancel` 后任务永不投递 | 通过 |
| Campaign 生命周期 | plan(L1)+activate(L3 带 token) SUCCEEDED | 通过 |
| Tool Namespace 隔离 | 跨 Agent 调用在 policy 层拒绝（双向） | 通过 |
| Memory Namespace 隔离 | content/campaign 命名空间互不可读；非白名单键拒写 | 通过 |
| Credential Namespace 隔离 | content 密钥引用在 campaign resolver 中 `SecretNotFoundError` | 通过 |

## 3. 故障注入

| 注入 | 证据 | 结果 |
| --- | --- | --- |
| 非法状态（未 freeze 的 Registry） | 启动 Run 即抛错 | 通过 |
| 无审批 L3 / L4 | 依次在 approval/deny 层拒绝，副作用 0 | 通过 |
| 恶意/未注册 Tool | deny 层拒绝，永不执行 | 通过 |
| Audit 故障 | fail-closed，Run FAILED（`audit_unavailable`），证据 0 | 通过 |
| 重复消息 ×100 | 1 条消息、1 次处理、完成后仍去重 | 通过 |
| Worker restart | 租约过期后 attempt+1 重投递，同一 idempotency_key | 通过 |
| Poison Message | max_attempts 后入 DLQ（含 last_error），replay 可恢复 | 通过 |

## 4. 全量门禁结果（本地 CI 等价命令）

| 门禁 | 结果 |
| --- | --- |
| Web lint/typecheck/test/build | 0 错误 / 0 错误 / 97 passed / build 成功 |
| API pytest + mypy（含 contract 25、migration 44） | 110 passed / 0 错误 |
| harness-core pytest + mypy | 45 passed / 0 错误 |
| infra-core pytest + mypy | 43 passed / 0 错误 |
| Eval | 5 passed |
| Integration（本子阶段新增 CI Job） | 12 passed |
| Secret 扫描 | clean（225 文件） |
| npm audit（high）/ pip-audit | 0 / 0 漏洞 |
| CodeQL | 0 告警 |

## 5. ADR / 文档复核

ADR-001..006 与本阶段实现一致（共享 Harness、仅 LangGraph 待 Phase 02 接入、
副作用前审批、无公网 Webhook、受控事实 Memory、幂等外部写）；无架构变化，无 ADR 更新需要。
可观测性契约见 `docs/observability.md`；Runbook/Owner/API 工单状态见 `docs/phase01/blocked.md`。

## 6. AI 质量 Checkpoint 汇总

| Checkpoint | Repo 证据 | 结论 |
| --- | --- | --- |
| P1-CP01（基线/范围） | `docs/phase01/baseline.md`、traceability-matrix | **BLOCKED**（待具名签字） |
| P1-CP02（契约/Migration） | contract 双语言 100%、migration 往返 | **BLOCKED**（待具名签字） |
| P1-CP03（Harness/Identity/Approval/Audit） | 无审批 L3/L4 成功 0、跨 Agent 访问 0、审计 fail-closed | **BLOCKED**（待具名签字） |
| P1-CP04（Queue/Storage/Secrets/Config） | 重复副作用 0、恢复一致、密钥泄漏 0、`p1-cp04-evidence.md` | **BLOCKED**（待 QA+SRE） |
| P1-CP05（CI/Observability/Local Dev） | 必需 Job 执行率 100%、空成功 0、`p1-cp05-evidence.md` | **BLOCKED**（待 Reviewer+TL/SRE） |

阶段签字要求 Product Owner、Architect、Security、QA、SRE 具名复核；AI 自评不能批准。

## 7. 阻断项与后续

- **DEV 受保护验证：BLOCKED** — DEV SSO、PostgreSQL、Queue、Object Store、Secret
  Manager、Gateway/Proxy 均未交付；`deploy-dev.yml` 已定义且 fail-closed。
  不以 Fake 结果宣称阶段完成。
- **镜像扫描/SBOM：BLOCKED** — 企业批准工具未指定。
- **五个 Checkpoint 具名签字：待人工** — 本 Evidence Pack 为签字输入。
- Phase 02/03 输入已就绪：domain-contracts、harness-core、infra-core、审批链、
  CI 门禁与本地栈可直接复用。
