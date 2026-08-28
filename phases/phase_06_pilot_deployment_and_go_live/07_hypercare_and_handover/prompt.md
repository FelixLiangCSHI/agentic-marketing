# Coding Agent Prompt — Phase 06 / Subphase 07

## 给 Coding Agent 的指令
统一纪律：采用 TDD，先写失败测试再做 surgical 最小变更；禁止 broad catch、静默 fallback；保留无关用户变更。
执行上线后 Hypercare、每日漂移/质量/费用复核和 Operations 正式移交；所有决定由人类 Owner 批准。执行模式：`remote-prd`。代码、测试、IaC、脚本、Runbook 和脱敏 fixture 只在 GitHub 隔离 branch/worktree 修改；生产执行经受保护 Pipeline/Environment Approval/企业自托管 Runner，Coding Agent 不得生产访问。

## 必须先读
- `../../phase_06_pilot_deployment_and_go_live.md`
- `../06_rollback_and_go_live/prompt.md`
- 父文档第 6.11–6.12、8、9、10、12、13、14 节。

## 执行位置与权限
检查/创建 `docs/runbooks/hypercare.md`、`docs/release/production-signoff.md`、Dashboard/Alert、On-call、Vendor Contact、Access Review 和 P1 Backlog；证据进入受控企业系统，GitHub 只保存状态/hash/脱敏引用。Coding Agent 只能准备/审查 Artifact；Operations/Security 人类拥有 PRD 执行和 Go/No-Go。禁止直接 SSH/RDP、手工 SQL、服务器热修、将真实 Secret 写入 GitHub、真实 Secret、自动豁免。

## 前置条件
Subphase 06 人类 Go、最终 Smoke、回退和 P6-CP05/06 PASS；分批开放计划、值班、业务/Medical/Security/Architecture/Operations/QA Owner、SLA 99.5%、RPO ≤15 分钟、RTO ≤2 小时和清理计划已批准。缺项 BLOCKED。

## 目标
每日 09:00 健康/备份/Credential/Quota/Queue 检查，业务时段监控 Critical Alert，外部写抽样核对，17:00 风险复盘；完成 10-30 签字、Dashboard/Runbook/Access/Vendor 移交、已知限制和 P1 Backlog。

## Scope
- 覆盖 Hypercare 日报、生产漂移、投诉/Reject/版本变化回溯、SEV 响应和 Operations handover。
- 不新增功能或扩大未批准渠道/权限。

## 实施任务
1. 每日收集 Availability、Run 成功/失败/取消、Latency、Queue/DLQ、Worker/DB/Backup、Tool 错误、费用、到期和 Audit；每个异常关联 Owner/Runbook/Incident。
2. 对每个生产外部写抽样核对 Approval/Hash/Idempotency/Reconcile/External ID；Pilot、Medical Claim、异常结果 100% 人工复核，低风险开放后每日不少于 10% 且不少于 30 条。
3. 运行 P6-CP05 漂移：与 UAT Golden 比较事实/合规/品牌/拒绝率/软评分；硬门失败立即关闭 Feature/Provider，连续两天下降 >0.2 或单日 >0.5 回滚。
4. 处理 SEV-1 Kill Switch/Incident/回退、SEV-2 暂停 Queue/渠道、SEV-3 当日计划、SEV-4 Backlog；保留所有证据。
5. 完成正式移交：签字、Dashboard、Runbook、值班、Access Review、Vendor 联系人、已知限制、P1 Backlog 和定期审查计划。

## 验证命令与证据
```powershell
python -m pytest tests\smoke\prd tests\pilot tests\recovery\prd
python scripts\release\reconcile_pilot.py --environment prd --read-only
```
通过 `remote-prd` 受保护流程采集 Hypercare 日报和移交报告；保存 Daily Eval、Drift Dashboard、Alert/Incident、抽样 Reconcile、SLA/备份/PITR、签字和交接确认。

## AI 质量 Checkpoint
执行 `P6-CP05`、`P6-CP06`，结果只能 `PASS`/`FAIL`/`BLOCKED`。PASS：硬门失败 0、软评分下降 ≤0.2/4、异常拒绝率/成本在阈值内、Evidence 引用 100%、错误/遗漏门禁 0、Go/移交签字均为人类 Owner；AI 自评不能批准，不请求 Chain-of-Thought。

## 失败与阻断处理
监控/值班/Runbook/签字/证据缺失为 BLOCKED；任何硬门失败立即关闭受影响 Feature/Provider，必要时 Kill Switch、Incident 和回滚。不得删除生产 Evidence、隐藏投诉、自动豁免或把未完成移交称为成功。

## 完成响应格式
报告状态、变更文件、命令/结果、`P6-CP05`/`P6-CP06` 人类结果、Evidence 引用、剩余风险/阻断和正式 Operations handover readiness。
