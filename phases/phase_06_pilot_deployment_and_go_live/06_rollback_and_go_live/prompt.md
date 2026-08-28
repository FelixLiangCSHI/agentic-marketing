# Coding Agent Prompt — Phase 06 / Subphase 06

## 给 Coding Agent 的指令
统一纪律：采用 TDD，先写失败测试再做 surgical 最小变更；禁止 broad catch、静默 fallback；保留无关用户变更。
执行上线前回退演练并准备 10-23 Go/No-Go、10-26 最终 Smoke 和 10-27–30 分批开放计划；Go/No-Go 只能由人类签发。执行模式：`remote-prd`。代码、测试、IaC、脚本、Runbook 和脱敏 fixture 在 GitHub 隔离 branch/worktree；PRD 通过受保护 Pipeline/Environment Approval/企业自托管 Runner，Coding Agent 不执行生产动作。

## 必须先读
- `../../phase_06_pilot_deployment_and_go_live.md`
- `../05_rotation_monitoring_and_operations/prompt.md`
- 父文档第 3.3、6.10–6.11、7–9、12–14 节。

## 执行位置与权限
检查/创建 `scripts/release/verify_rollback.py`、`docs/runbooks/rollback.md`、`docs/release/go-no-go.md`、`tests/recovery/prd` 和生产 Evidence 索引。Coding Agent 只能准备/审查 Artifact；Operations/Security 人类拥有 PRD 执行和 Go/No-Go。禁止直接 SSH/RDP、手工 SQL、服务器热修、将真实 Secret 写入 GitHub、覆盖镜像 Tag、真实 Secret 暴露或自动改生产 Campaign。

## 前置条件
Subphase 05 Rotation/Monitoring PASS；Pilot、Release Manifest、HA、PITR、预算、Security/Legal、值班、Vendor 和人类 Go/No-Go Owner 证据齐全。缺任一项 `BLOCKED`，不得口头豁免为 Go。

## 目标
验证 Web/API/Worker 回退 digest、Feature Flag、Kill Switch、Queue Pause/Replay、兼容 Schema、Object/PITR、Token 撤销替换，并形成可审计 Go/No-Go 与最终 Smoke 决定。

## Scope
- 覆盖回退触发条件、证据保留、人工外部对账、Incident、最终只读/最小写 Smoke 和分批开放门禁。
- 不引入非阻断功能或视觉改版。

## 实施任务
1. 演练未审批写、重复 Campaign、Critical Claim、Secret/跨域、数据损坏/Audit 丢失、无法对账、Availability/Queue/DB 超阈值触发回退。
2. 回退到上一 digest，关闭新 Workflow，暂停 Queue 并安全 Replay，保留兼容 Schema，恢复 Object/PITR，撤销/替换 Token。
3. 回退后保留 Run/Approval/Audit/External ID，人工对账并创建 Incident/复盘；不得删除证据。
4. 10-23 逐门检查 Release/Security/Business/Medical/API/Reliability/Operations/Data；10-26 核对 Manifest/Credential/Quota/FQDN/预算和值班，执行 Smoke，记录人类 Go/No-Go。
5. 为 10-27–30 每批定义 Queue/DLQ/费用/Token/Alert 检查、逐次审批和对账停机条件。

## 验证命令与证据
```powershell
python scripts\release\verify_rollback.py --environment prd --dry-run
python scripts\release\preflight.py --environment prd --read-only
python scripts\release\smoke_test.py --environment prd --read-only
```
由 `remote-prd` 受保护 Job/人类 Runbook 执行；保存回退时间线、hash/digest、PITR/Queue/Object/Token、Incident、Smoke、Go/No-Go 会议决定和签字 Evidence。

## AI 质量 Checkpoint
执行 `P6-CP05`、`P6-CP06`，结果只能 `PASS`/`FAIL`/`BLOCKED`。PASS：硬门漂移 0、软评分下降 ≤0.2/4、回退可执行、Evidence 引用 100%、错误/遗漏门禁 0；人类 Operations/Security/PM/全体签字人判定。AI 不得批准 Go-Live/Risk Acceptance，不请求 Chain-of-Thought。

## 失败与阻断处理
任何回退失败、不可对账、门禁缺失或证据不一致为 `NO-GO`/BLOCKED；执行 Kill Switch/暂停 Queue/Incident，修复后重演。禁止口头豁免、静默 fallback、删除证据或用测试 Credential 代替 PRD。

## 完成响应格式
报告状态、变更文件、命令/结果、`P6-CP05`/`P6-CP06` 人类结果、Evidence 引用、风险/阻断和 Subphase 07 就绪性。
