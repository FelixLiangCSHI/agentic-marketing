# Coding Agent Prompt — Phase 05 / Subphase 05

## 给 Coding Agent 的指令
统一纪律：采用 TDD，先写失败测试再做 surgical 最小变更；禁止 broad catch、静默 fallback；保留无关用户变更。
执行真实 PITR、Worker/Queue/Object/节点恢复、Token Rotation 和供应商故障演练，按时间和一致性证明 RPO/RTO。执行模式：`remote-uat`。代码、测试、IaC、脚本、Runbook 和脱敏 fixture 在 GitHub 隔离 branch/worktree；恢复执行只能通过受保护 Pipeline/Environment Approval/企业自托管 Runner。

## 必须先读
- `../../phase_05_uat_security_performance_and_stabilization.md`
- `../04_prd_300_capacity/prompt.md`
- 父文档第 5.10、5.11、8.3、9、10、12、13、14 节。

## 执行位置与权限
检查/创建 `tests/recovery/uat`、`docs/runbooks/{backup-restore,vendor-outage,token-rotation}.md` 和 timed drill 模板。Coding Agent 不得直接 SSH/RDP、手工 SQL、服务器热修、将真实 Secret 写入 GitHub、生产访问或读取真实 Secret；DBA/SRE/QA 人类拥有恢复执行。

## 前置条件
100/300 并发和安全 PASS；UAT 备份/PITR、Queue/Object version、Token、节点故障、供应商 Fault、审批账户、监控和恢复窗口均已批准。缺真实恢复环境或人类 Owner 为 BLOCKED，不能纸面或 Mock 通过。

## 目标
演练误删 PITR、Worker 中断、Queue 重复、Object 版本恢复、Secret Rotation/旧凭据撤销、单 Web/App/Worker 不可用；达到 RPO ≤15 分钟、RTO ≤2 小时且无重复外部写。

## Scope
- 覆盖故障开始/检测/响应/恢复/验证、最后可恢复点、丢失事件及 Run/Task/Approval/Audit/External 一致性。
- 不新增功能或改变门槛。

## 实施任务
1. 固定演练输入、时间戳和 hash；执行 DB 误删/PITR、Worker/Queue/Object/节点故障及供应商 429/5xx/不可用。
2. 记录 watermark、lease、最后可恢复时间、丢失业务事件、重放 key、外部 ID 和恢复后 hash diff。
3. 执行 Token 新旧版本轮换/撤销，验证旧调用失败、只读能力保留、Audit 完整。
4. 核对恢复不重复外部写、审批不失效、状态不非法回退；失败演练建立根因、最小修复、重新演练任务。

## 验证命令与证据
```powershell
python -m pytest tests\recovery\uat
python -m pytest tests\security\uat -k "token or credential"
```
由 `remote-uat` Runbook 执行 timed drill；保存故障时间线、PITR/backup、hash diff、Audit、Queue/Object/Token、RPO/RTO 和签字报告，敏感数据脱敏。

## AI 质量 Checkpoint
执行 `P5-CP04`，结果只能 `PASS`/`FAIL`/`BLOCKED`。PASS：数据/状态不一致 0、重复外部写 0、恢复说明与证据一致率 100%、RPO ≤15 分钟、RTO ≤2 小时；DBA/SRE/QA 人类判定，AI 自评不能批准，不收集 Chain-of-Thought。

## 失败与阻断处理
恢复证据、计时、备份、权限或 Owner 缺失为 BLOCKED；超时、丢事件、不一致、旧 Token 可用或重复写为 FAIL。修复 Recovery/Idempotency/Runbook 后重新演练；不手工 SQL、不删除证据、不假报成功。

## 完成响应格式
报告状态、变更文件、命令/结果、`P5-CP04` 人类结果、Evidence 引用、风险/阻断和 Subphase 06 就绪性。
