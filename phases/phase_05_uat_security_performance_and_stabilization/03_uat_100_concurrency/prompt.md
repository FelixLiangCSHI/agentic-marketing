# Coding Agent Prompt — Phase 05 / Subphase 03

## 给 Coding Agent 的指令
统一纪律：采用 TDD，先写失败测试再做 surgical 最小变更；禁止 broad catch、静默 fallback；保留无关用户变更。
冻结单用户质量基线并在 UAT 执行 100 并发混合负载，比较质量、正确性、副作用和资源，不以换模型或降低控制面掩盖退化。执行模式：`remote-performance`。代码、测试、IaC、脚本、Runbook 和脱敏 fixture 在 GitHub 隔离 branch/worktree；负载只能由受保护性能 Pipeline/Environment Approval/企业自托管 Runner 运行。

## 必须先读
- `../../phase_05_uat_security_performance_and_stabilization.md`
- `../02_security_red_team/prompt.md`
- 父文档第 5.8、8.3、9、10、13、14 节。

## 执行位置与权限
检查/创建 `tests/performance/uat`、`tests/uat/fixtures`、`docs/runbooks/performance-test.md` 和 pairwise 报告工具。禁止直接 SSH/RDP、手工 SQL、服务器热修、真实 Secret 入 GitHub、生产访问或临时改服务器。

## 前置条件
P5-CP01/02 PASS；Product/SRE 在测试前签署持续时间、ramp-up、SLO、预算、账户和清理方案；UAT 拓扑/Observability 可采集 Web/API、Queue、Worker、DB、Object、Vendor、费用数据。缺项 BLOCKED。

## 目标
使用 40% 查询、20% Content、10% 媒体、15% Campaign Draft/Dry-run、5% 受控写、10% Metrics/Report 完成 100 并发，保持同版本输出质量与安全基线。

## Scope
- 只覆盖 UAT 100 并发、质量 pairwise、资源和队列回落。
- 不执行 PRD 300 容量或生产写入。

## 实施任务
1. 冻结同一输入的单用户 Golden/Adversarial 质量基线；固定 Prompt/Model/Policy/Skill/Connector/RC 版本。
2. 编写可停止、限预算、可清理的负载脚本；记录 p50/p95/p99、错误率、Queue/DLQ、Worker CPU/Memory/heartbeat/task time、DB CPU/连接/锁/IOPS/慢查询、Object、Vendor 429/5xx、Token/费用。
3. 对并发输出逐项比对事实、引用、截断、重复、跨用户错配、审批、外部对象和 Trace/Audit。
4. 验证内部成功率 ≥99.5%（注入故障单独统计）、跨用户错配 0、未审批写 0、重复对象 0、审计缺失 0，队列在签字窗口内回落。

## 验证命令与证据
```powershell
python -m pytest tests\performance\uat -m "uat and concurrency100"
python -m pytest tests\uat tests\security\uat -k "isolation or idempot"
```
通过 `remote-performance` Runbook 运行负载；保存 Baseline/Load pairwise report、Trace、资源时序、SLO 签字、预算/清理、队列回落和错误明细。

## AI 质量 Checkpoint
执行 `P5-CP03`，结果只能 `PASS`/`FAIL`/`BLOCKED`。PASS：硬指标与单用户基线一致 100%、跨用户错配 0、软评分下降 ≤0.2/4、重复副作用 0、成功率 ≥99.5%；QA/SRE 人类判定，AI 不得批准，不请求 Chain-of-Thought。

## 失败与阻断处理
负载窗口、SLO、预算、采集或真实 UAT 证据缺失为 BLOCKED；退化/积压/错配/重复为 FAIL。调整 Queue/并发/超时后按同一基线重测，不关闭审批、TLS、DLP、审计或降低 Rubric。

## 完成响应格式
报告状态、变更文件、命令/结果、`P5-CP03` 人类结果、Evidence 引用、风险/阻断和 Subphase 04 就绪性。
