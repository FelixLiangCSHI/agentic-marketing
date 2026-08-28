# Coding Agent Prompt — Phase 06 / Subphase 05

## 给 Coding Agent 的指令
统一纪律：采用 TDD，先写失败测试再做 surgical 最小变更；禁止 broad catch、静默 fallback；保留无关用户变更。
演练 Token Rotation/Revoke、应急撤销、生产 Dashboard/Alert、值班和 Operations Runbook；保留只读能力和全部证据。执行模式：`remote-prd`。代码、测试、IaC、脚本、Runbook 和脱敏 fixture 在 GitHub 隔离 branch/worktree；PRD 执行需受保护 Pipeline/Environment Approval，Operations/Security 人类负责。

## 必须先读
- `../../phase_06_pilot_deployment_and_go_live.md`
- `../04_controlled_pilot/prompt.md`
- 父文档第 6.8、6.9、6.12、8.3–8.4、9、12、13、14 节。

## 执行位置与权限
检查/创建 `docs/runbooks/{channel-token-rotation,vendor-outage,queue-dlq,hypercare,security-incident}.md`、`infra/prd/observability`、`tests/recovery/prd` 和 Alert 定义。Coding Agent 只能准备/审查 Artifact；Operations/Security 人类拥有 PRD 执行和 Go/No-Go。禁止 Coding Agent 直接 SSH/RDP、手工 SQL、服务器热修、将真实 Secret 写入 GitHub、读取真实 Secret或删除证据。

## 前置条件
Pilot P6-CP02/03/04 PASS；人类 Security/Operations、Secret Manager、值班、Vendor 联系人、Kill Switch、Queue Pause、预算/Quota 和通知链已批准。缺失即 BLOCKED。

## 目标
在 10-23 前实际完成新旧 Token 轮换/撤销；验证旧调用失败、Kill Switch/Queue Pause/只读 Portal/Audit/Reconcile 可用；上线 Dashboard/Alert 覆盖健康、Queue/DLQ、Worker/DB、工具错误、费用、到期和 Audit。

## Scope
- 覆盖 Rotation、Emergency Revoke、Observability、On-call 和 Runbook 可执行性。
- 不扩大 Pilot 或自动修复生产对象。

## 实施任务
1. 通过 Secret Reference 创建新版本、滚动刷新 Connector/Worker、只读 Health、撤销旧版本并审计时间/Owner。
2. 演练 Secret/Token/DLP、未知外部写、重复对象、未批准 Claim、Audit 失败、Worker 无心跳、DLQ、DB/备份失败告警。
3. 为每个告警落实 Owner、严重度、去重键、通知渠道、升级时间、Runbook 和关闭条件；验证 80% 费用/Quota 告警及 100% 停止。
4. 应急撤销时关闭外部写、暂停对应 Queue、撤销凭据、保留只读能力、通知 Security/Business/Vendor。

## 验证命令与证据
```powershell
python -m pytest tests\recovery\prd -k "rotation or revoke or alert"
python -m pytest tests\smoke\prd -k "health or observability"
```
经 `remote-prd` 受保护流程演练；保存 Secret 版本 metadata（不含值）、旧调用失败、Audit、Alert firing/closure、On-call ack、Runbook 演练和通知记录。

## AI 质量 Checkpoint
执行 `P6-CP04`、`P6-CP05`，结果为 `PASS`/`FAIL`/`BLOCKED`。PASS：报告/建议硬门、Rotation/Revoke 可验证、硬门漂移 0、软评分下降 ≤0.2/4、费用/拒绝率在签字阈值内；Data Owner、QA、Medical、SRE、Security 人类批准，AI 不得签发，不请求 Chain-of-Thought。

## 失败与阻断处理
旧 Token 仍可用、告警无 Owner、Kill Switch 不可用、Secret 泄漏或监控缺失为 FAIL/BLOCKED；关闭 Provider/Feature、暂停 Queue、Incident/人工修复。禁止把撤销失败、告警缺失或未知状态包装成功。

## 完成响应格式
报告状态、变更文件、命令/结果、`P6-CP04`/`P6-CP05` 人类结果、Evidence 引用、风险/阻断和 Subphase 06 就绪性。
