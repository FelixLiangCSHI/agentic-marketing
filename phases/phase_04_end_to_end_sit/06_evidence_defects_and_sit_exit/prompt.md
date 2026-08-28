# Coding Agent Prompt — Phase 04 / Subphase 06

## 给 Coding Agent 的指令
统一纪律：采用 TDD，先写失败测试再做 surgical 最小变更；禁止 broad catch、静默 fallback；保留无关用户变更。
汇总 SIT Evidence、分级缺陷、执行最小修复和 Critical 回归，形成可审计的 SIT→UAT 晋级建议。执行模式：`remote-sit`。代码、测试、IaC、脚本、Runbook、脱敏 fixture 仅在 GitHub 隔离 branch/worktree；远端验证经受保护 Pipeline/Environment Approval/企业自托管 Runner。

## 必须先读
- `../../phase_04_end_to_end_sit.md`
- `../05_metrics_observability_and_performance/prompt.md`
- 父文档第 7、8、9、10、12、13、14、15 节。

## 执行位置与权限
检查所有 `tests/{integration,workflow,security,recovery,performance}/sit`、`evals/*/sit`、`docs/runbooks/*sit*`、`infra/sit` 和 CI Artifact；新增缺陷失败测试、Evidence 模板或修复只能入 Repo。禁止直接 SSH/RDP、手工 SQL、服务器热修、将真实 Secret 写入 GitHub、真实 Secret 或生产访问。

## 前置条件
Subphase 05 通过；每个 Critical Run、双渠道真实账户、恢复/重复/DLQ/安全/50 并发和 Trace/Audit 报告已有受控链接。任一 SIT DNS/SSO/DB/Queue/账户证据缺失即 BLOCKED。

## 目标
验证 Critical/High 缺陷为 0，所有退出条件和 P4 Checkpoint 完整 PASS，Evidence Pack 含 SHA/digest/config/migration、测试、Contract、外部 ID、清理、回归、风险与签字，并只提出可追溯晋级决定。

## Scope
- 汇总 `SIT-CONT/CAMP/FAIL/METRIC/SEC/OPS/PERF` 证据、缺陷回归和签字。
- 不新增功能、渠道、P1 或无关 UI 重构。

## 实施任务
1. 建立 Evidence 索引，逐项引用 Run、Artifact、Approval、External ID、Raw Metric、Audit、hash 和人类 Owner；删除/脱敏真实响应、Token、身份和敏感 Product。
2. 按 Critical/High/Medium/Low 分级；每个修复必须有失败测试、最小 diff、受影响回归、新 RC、部署证据。
3. 重跑所有 Critical Workflow、真实 LinkedIn/Google 路径、100 次重复消息、超时对账、Worker/DLQ、Token、Security、Metrics 和 50 并发。
4. 核对退出硬门：未审批写/重复 Campaign/Secret 泄漏/跨域均 0，Claim/Package/Approval/External/Raw/Report Trace/Audit 100%，环境完全隔离。
5. 由 QA、Tech Lead、Security、Marketing、Medical 人类签字；仅输出 UAT readiness，不代签。

## 验证命令与证据
```powershell
npm test
npm run lint
npm run typecheck
npm run build
python -m pytest tests\contract tests\workflow tests\integration\sit tests\security\sit tests\recovery\sit tests\performance\sit
```
通过 `remote-sit` 复验真实外部路径和 Artifact；保存最终 RC manifest、缺陷台账、全量结果、Checkpoint Results、签字和受控 Evidence Pack。

## AI 质量 Checkpoint
执行 `P4-CP01`、`P4-CP02`、`P4-CP03`、`P4-CP04`、`P4-CP05`，每项只写 `PASS`/`FAIL`/`BLOCKED`。PASS 必须满足各自 100%/0/≥3.4 阈值、Critical/High=0、真实渠道门禁全通过；人类 Owner 逐项批准。AI 自评不得批准，不请求或保存 Chain-of-Thought。

## 失败与阻断处理
任一未裁决分歧、Critical/High、外部依赖、签字或 Evidence 缺失即 BLOCKED/FAIL，不得晋级。按对应 Checkpoint 返回节点，连续三次同类失败暂停自动返工并做根因分析；不降门槛、不删除证据、不用 Mock 替代 live proof。

## 完成响应格式
报告状态、变更文件、命令/结果、五项 Checkpoint 的人类结果、Evidence 引用、剩余风险/阻断和 Subphase 07（Phase 05）启动就绪性。
