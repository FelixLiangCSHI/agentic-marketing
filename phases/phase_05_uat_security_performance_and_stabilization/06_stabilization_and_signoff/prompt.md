# Coding Agent Prompt — Phase 05 / Subphase 06

## 给 Coding Agent 的指令
统一纪律：采用 TDD，先写失败测试再做 surgical 最小变更；禁止 broad catch、静默 fallback；保留无关用户变更。
进入 Feature Freeze，完成 Critical/High 修复回归、RC 稳定化、Evidence 汇总和人类签字；不新增功能。执行模式：`remote-uat`。代码、测试、IaC、脚本、Runbook 和脱敏 fixture 只能在 GitHub 隔离 branch/worktree 修改；远端验证仅经受保护 Pipeline/Environment Approval/企业自托管 Runner。

## 必须先读
- `../../phase_05_uat_security_performance_and_stabilization.md`
- `../05_recovery_pitr_and_rto/prompt.md`
- 父文档第 5.12、7、8、9、10、13、14、15 节。

## 执行位置与权限
检查 `tests/uat`、`tests/security/uat`、`tests/performance/{uat,prd_capacity}`、`tests/recovery/uat`、`evals/*/uat`、`docs/release/{uat-signoff,risk-register,release-candidate}.md`。只在 Repo 修复并从干净 checkout 构建；禁止直接 SSH/RDP、手工 SQL、服务器热修、将真实 Secret 写入 GitHub、真实 Secret、生产访问。

## 前置条件
业务、安全、100/300 性能、恢复演练分别完成；Feature Freeze 已生效，Product/Marketing、Medical、Security、Architecture、Operations/SRE、QA/Eval 具名 Owner 可签字。任何 Critical/High、外部门禁、证据或签字缺失为 BLOCKED。

## 目标
新 RC 满足所有 UAT 硬门和质量基线，Critical/High=0，RPO/RTO、Sizing、Credential/Quota/FQDN 和 Runbook 完整，生成可进入 Phase 06 Pilot 的不可变 Evidence Pack。

## Scope
- 仅缺陷修复、测试/文档/Runbook/告警/配置修正、全量回归、签字和风险登记。
- 不接受新渠道、模型、UI 流程或未经评审的大改。

## 实施任务
1. 每个缺陷先复现并添加失败测试，做最小 diff，运行受影响和 Critical 全量回归，生成新 SHA/digest/Migration/SBOM RC。
2. 重跑 Golden/Adversarial、十核心 UAT、外部写、Security、100/300、PITR/RPO/RTO、Token/供应商故障和单节点恢复。
3. 对照签字基线检查软评分下降 ≤0.2/4、单项 ≥3、硬门全通过；连续三次同类失败暂停自动返工并根因分析。
4. 汇总版本、场景、Reviewer、Security、性能/Sizing、恢复、API Access/Quota/FQDN/Credential、缺陷、Risk Acceptance、Runbook 和所有签字。
5. 只输出人类可审查的 Phase 06 readiness；AI 不代签、不得自动豁免。

## 验证命令与证据
```powershell
npm ci
npm test
npm run lint
npm run typecheck
npm run build
python -m pytest tests\contract tests\workflow tests\uat tests\security\uat tests\recovery\uat tests\performance\uat tests\performance\prd_capacity
```
通过 `remote-uat` 重新运行关键远端证据；保存最终 RC、Baseline/Load、Timed Drill、扫描、缺陷关闭和全体签字 Evidence Pack。

## AI 质量 Checkpoint
执行 `P5-CP05`、`P5-CP06`，结果只能 `PASS`/`FAIL`/`BLOCKED`。PASS：硬门无回归、软评分相对基线下降 ≤0.2/4、Critical/High=0、Evidence 引用 100%、虚假完成/遗漏阻断项 0，且签字全为具名人类 Owner；AI 自评不能批准，不请求 Chain-of-Thought。

## 失败与阻断处理
冻结期新增功能、门禁下降、回归失败、证据不一致、签字缺失或未确定性披露不足即 FAIL/BLOCKED；拒绝 RC，仅最小修复并生成新 RC，按 Checkpoint 返回节点，不关闭测试/审批/审计/TLS/DLP。

## 完成响应格式
报告状态、变更文件、命令/结果、`P5-CP05`/`P5-CP06` 人类结果、Evidence 引用、剩余风险/阻断和 Phase 06 Subphase 01 就绪性。
