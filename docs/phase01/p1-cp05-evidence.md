# P1-CP05 证据（CI / Observability / Local Dev）：Phase 01 / Subphase 07

- 日期：2026-08-28
- 结论：**BLOCKED**（AI 自评不得给出 PASS；需独立 Reviewer + Tech Lead/SRE 复核）

## 变更范围

- 新增 `infra/local/`：docker-compose 本地栈（postgres:16、rabbitmq:4 Queue Emulator、
  MinIO Object Store Emulator、OTel Collector、Fake IAM）+ `.env.example` per-worktree
  隔离（项目名/端口/DB/bucket 前缀）+ README。
- 新增 `evals/`：最小 Content/Campaign Eval（golden + adversarial，5 个用例）。
- 新增 `scripts/check_no_secrets.py`：Secret 扫描门禁（普通 PR CI 使用）。
- CI 新增 Jobs：`contract`（双语言契约）、`migration`（往返）、`security`
  （secret + npm audit + pip-audit）、`eval`。
- 新增受保护部署 Workflow 定义 `.github/workflows/deploy-dev.yml`
  （workflow_dispatch + Environment `dev` 人工 Approval + OIDC `id-token: write` +
  Fork/仓库来源守卫；部署步骤 fail-closed 占位，DEV 基础设施未交付）。
- 新增 `docs/observability.md`：统一 Trace 字段、指标与 L3/L4/DLQ/Audit/费用/heartbeat 告警定义。
- 修复 `package.json` overrides：brace-expansion/js-yaml/nanoid 升至无漏洞版本
  （原 overrides 钉住了含 DoS 漏洞的 brace-expansion 1.1.16/5.0.8）；
  `npm audit --audit-level=high` 从 17 high → 0。
- 根 scripts 新增：`contract:test`、`eval:test`、`scan:secrets`。

## 本地栈结果（干净 checkout）

```
docker compose up -d   # infra/local
postgres / queue / objectstore / fake-iam：healthy；otel-collector：up
GET fake-iam /healthz → {"status":"ok"}
POST /token subject=content-author → 合成 token fake-local-content-author
```

## CI 门禁与本地等价命令结果

| Job | 命令 | 结果 | 故意失败验证（非空脚本证明） |
| --- | --- | --- | --- |
| web | lint/typecheck/test/build | 通过（97 tests） | 既有门禁（Subphase 02 已验证） |
| api | pytest + mypy | 110 passed | 既有门禁 |
| harness / infra | pytest + mypy | 45 / 43 passed | 既有门禁 |
| contract | tsx 契约测试 + api fixture 测试 | 19 pass + 25 passed | fixture 由 invalid 目录负例覆盖 |
| migration | `pytest tests/db` | 44 passed（head→base 逐版本往返） | 测试含 downgrade 残留表断言 |
| security | `check_no_secrets.py` + `npm audit --audit-level=high` + `pip-audit` | clean / 0 vulnerabilities / 无漏洞 | 注入 AKIA 假 key → 扫描退出码 1 |
| eval | `pytest evals` | 5 passed | 注入故意失败测试 → 1 failed，Job 会失败 |

## 门禁指标

| 指标 | 要求 | 结果 |
| --- | --- | --- |
| CI 必需 Job 执行率 | 100%，绕过/空成功 0 | 每个新 Job 有实际断言并完成故意失败验证 |
| Critical Trace 字段完整率 | 100% | 字段契约已定义（docs/observability.md）；运行时校验随 Phase 02 工作流接入 |
| Secret 泄漏 | 0 | 秘密扫描 clean；日志/Trace 契约禁止凭据值 |
| 普通 PR 远端 Credential | 0 | ci.yml 无任何 Secret 引用；deploy-dev 仅 OIDC + 人工 Approval |
| Fork 权限 | 0 | deploy-dev 有仓库来源守卫；pull_request 事件无 Secret 可用 |

## 阻断与后续

- **镜像扫描 / SBOM：BLOCKED** — 企业批准的镜像仓库与扫描工具未指定；未私自引入第三方
  扫描服务（遵循「不上传源码到第三方」）。交付后补充 image scan + SBOM Job。
- **Dashboard/Alert 落地：BLOCKED** — 企业监控栈未交付，本阶段交付字段/指标/告警契约定义。
- **deploy-dev 实际执行：BLOCKED** — DEV SSO/PostgreSQL/Queue/Object Store/Secret
  Manager/Gateway 未交付；Workflow 已定义且 fail-closed。
- P1-CP04 / P1-CP05 需独立 Reviewer + Tech Lead/SRE 复核后方可置 PASS；当前 BLOCKED。
