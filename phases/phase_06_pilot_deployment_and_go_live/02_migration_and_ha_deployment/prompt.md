# Coding Agent Prompt — Phase 06 / Subphase 02

## 给 Coding Agent 的指令
统一纪律：采用 TDD，先写失败测试再做 surgical 最小变更；禁止 broad catch、静默 fallback；保留无关用户变更。
准备并由人类 Operations/DBA 监督执行 PRD 向后兼容 Migration 与 HA 滚动部署；保留 Kill Switch 和消费暂停。执行模式：`remote-prd`。代码、测试、IaC、脚本、Runbook 和脱敏 fixture 只在 GitHub 隔离 branch/worktree 修改；远端只能通过受保护 Pipeline/Environment Approval/企业自托管 Runner，Coding Agent 不拥有生产执行权限。

## 必须先读
- `../../phase_06_pilot_deployment_and_go_live.md`
- `../01_release_freeze_and_prd_preflight/prompt.md`
- 父文档第 4、6.4–6.5、7、8.1、8.4、12、13 节。

## 执行位置与权限
检查/创建 `infra/prd/deployment`、`infra/prd/backup`、Migration 文件、`docs/runbooks/prd-deployment.md`、`docs/runbooks/rollback.md` 和 `scripts/release/verify_rollback.py`。Coding Agent 只能准备/审查 Artifact；Operations/DBA/Security 人类拥有 PRD 执行和 Go/No-Go。禁止直接 SSH/RDP、手工 SQL、服务器热修、将真实 Secret 写入 GitHub、破坏性 Migration、真实 Secret 暴露或生产访问。

## 前置条件
Subphase 01 P6-CP01 PASS；PRD preflight、备份/恢复点、锁影响、expand→migrate→contract 方案、旧新 API/Worker 兼容窗口和人类 DBA/Operations 批准齐全。否则 BLOCKED。

## 目标
按配置/Secret preflight→Migration→Observability→API 节点 1/2→Worker（消费暂停）→Web 节点 1/2→Gateway Health→只读 Smoke 的顺序完成可回退部署，且不丢 Queue watermark。

## Scope
- 覆盖向后兼容 Migration、HA 滚动发布、Health、Queue pause/resume 和失败停止。
- 不执行外部写 Pilot 或 Go-Live。

## 实施任务
1. 对空库/预置 Schema dry-run，生成 Schema diff/锁报告和备份验证；不可逆变化不得同窗删除旧列。
2. 通过 Pipeline 暂停冲突后台任务、记录 Queue watermark、运行 Migration、验证 Schema/Role/Audit，再滚动部署 API/Worker/Web。
3. 每步失败自动停止后续步骤，保留状态/证据；恢复 Queue 前确认 Health、兼容性和 Kill Switch 仍关闭。
4. 编写/验证非破坏性回滚：关闭 Feature、回退应用 digest、保留兼容 Schema，禁止覆盖 Tag 或删除新数据。

## 验证命令与证据
```powershell
python scripts\release\preflight.py --environment prd --read-only
python scripts\release\verify_rollback.py --environment prd --dry-run
python -m pytest tests\recovery\prd -k "migration or ha or rollback"
```
由 `remote-prd` Pipeline/人类 Operations 执行并保存 Migration dry-run、lock/schema diff、watermark、节点健康、滚动日志、备份/恢复点和回滚演练 Evidence。

## AI 质量 Checkpoint
执行 `P6-CP01`，结果为 `PASS`/`FAIL`/`BLOCKED`。PASS：版本/Contract/Golden 100%、测试/PRD 数据串用 0、Migration 可复现且 HA/health 证据齐全；人类 Tech Lead/Security/QA/DBA 判定，AI 不得批准，不请求 Chain-of-Thought。

## 失败与阻断处理
Migration 锁、兼容性、备份、节点 Health 或 Pipeline 权限失败为 BLOCKED/FAIL；停止后续步骤，回到可验证的兼容应用版本。禁止手工 SQL、关闭审计/TLS、删除证据或把部署失败包装成功。

## 完成响应格式
报告状态、变更文件、命令/结果、`P6-CP01` 人类结果、Evidence 引用、风险/阻断和 Subphase 03 就绪性。
