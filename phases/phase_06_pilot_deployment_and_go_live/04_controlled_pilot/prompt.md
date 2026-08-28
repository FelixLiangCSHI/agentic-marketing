# Coding Agent Prompt — Phase 06 / Subphase 04

## 给 Coding Agent 的指令
统一纪律：采用 TDD，先写失败测试再做 surgical 最小变更；禁止 broad catch、静默 fallback；保留无关用户变更。
在严格边界内执行小范围真实 Pilot：每个 Content Package/Campaign 都必须人工审批、对账并受预算约束。执行模式：`remote-prd`。代码、测试、IaC、脚本、Runbook 和脱敏 fixture 只能在 GitHub 隔离 branch/worktree；真实生产动作由受保护 Pipeline/Environment Approval 和人类 Operations/Business/Security 执行，Coding Agent 不得生产访问。

## 必须先读
- `../../phase_06_pilot_deployment_and_go_live.md`
- `../03_credentials_and_smoke_tests/prompt.md`
- 父文档第 6.7、8.2、9、10、12、13、14 节。

## 执行位置与权限
检查/创建 `tests/pilot`、`scripts/release/reconcile_pilot.py`、`docs/runbooks/campaign-kill-switch.md`、Pilot manifest 和 Evidence 模板。Coding Agent 只能准备/审查 Artifact；Operations/Business/Security 人类拥有 PRD 执行和 Go/No-Go。禁止直接 SSH/RDP、手工 SQL、服务器热修、真实 Secret 入 GitHub、自动优化/互动/邮件或 L4 自动执行。

## 前置条件
Subphase 03 P6-CP01/03 PASS；指定内部用户、批准产品/市场/语言/渠道、Campaign/预算/受众/时间硬上限、Provider 日费上限、值班和 Kill Switch 均有书面批准。缺任一项 BLOCKED。

## 目标
在 2026-10-19 至 10-23 边界内完成批准 Content→Medical/Marketing→Draft/Dry-run→Campaign Approval→LinkedIn/Google 写入→Reconcile→Metrics/Report，并证明安全、幂等、费用和告警门禁。

## Scope
- 仅指定内部用户和受控真实 LinkedIn/Google Pilot。
- 保持逐次人工审批；不自动增预算、改竞价/受众、暂停/删除或邮件发送。

## 实施任务
1. 每日先检查 Credential、Quota、Queue/DLQ、Policy/Skill/Package 过期，再提交批准任务。
2. 对每个 Package 执行 Claim/Medical/品牌/媒体安全/有效期检查并保存 Approval、Hash；拒绝或漂移阻断 Campaign。
3. 对每个 Campaign 记录 Request/Token/input hash/idempotency/External ID/Reconcile/Audit，发布后立即对账并清理。
4. 采集 Raw Metrics、新鲜度、Report/Strategy（仅草稿）、费用、告警、缺陷和风险；验证未审批写 0、重复 0、Critical Claim 逃逸 0、Secret 泄漏 0、证据完整 100%。

## 验证命令与证据
```powershell
python -m pytest tests\pilot
python scripts\release\reconcile_pilot.py --environment prd --read-only
```
受保护 `remote-prd` Job 执行每日 Pilot；保存审批表、Package/Checkpoint、External ID、Reconcile、费用/Quota、Queue/DLQ、Metrics、Audit、清理和人类复核证据。

## AI 质量 Checkpoint
执行 `P6-CP02`、`P6-CP03`、`P6-CP04`，每项只能 `PASS`/`FAIL`/`BLOCKED`。阈值分别为 Claim 引用 100%/Critical 逃逸 0/软评分 ≥3.4、未审批写/重复/违规参数 0 且 Reconcile/Audit 100%、报告数值一致 100%/虚构结论 0/直接写建议 0/软评分 ≥ UAT 基线−0.2；Medical、Marketing、Approver、Operations、Data Owner 人类判定，AI 不得批准，不请求 Chain-of-Thought。

## 失败与阻断处理
任何硬门失败立即 Kill Switch/暂停 Connector Queue 并人工对账；缺账户、审批、预算、监控或证据为 BLOCKED。不得自动豁免、重试未知外部写、删除 Run/Audit/External ID 或用 Mock 代替真实 Pilot。

## 完成响应格式
报告状态、变更文件、命令/结果、三项 Checkpoint 人类结果、Evidence 引用、风险/阻断和 Subphase 05 就绪性。
