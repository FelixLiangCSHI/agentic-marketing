# Coding Agent Prompt — Phase 05 / Subphase 04

## 给 Coding Agent 的指令
统一纪律：采用 TDD，先写失败测试再做 surgical 最小变更；禁止 broad catch、静默 fallback；保留无关用户变更。
在 PRD 等价隔离性能环境完成 300 并发容量与单节点失效测试，输出可执行 Sizing，不接触生产数据或无上限预算。执行模式：`remote-performance`。代码、测试、IaC、脚本、Runbook 和脱敏 fixture 在 GitHub 隔离 branch/worktree；远端仅经受保护 Pipeline/Environment Approval/企业自托管 Runner。

## 必须先读
- `../../phase_05_uat_security_performance_and_stabilization.md`
- `../03_uat_100_concurrency/prompt.md`
- 父文档第 5.9、8.3、9、10、12、13、14 节。

## 执行位置与权限
检查/创建 `tests/performance/prd_capacity`、`infra/prd/sizing`、`docs/runbooks/performance-test.md` 和容量报告。性能环境需 Web x2、API/Worker x2、PostgreSQL HA 等价规格、分 Queue/连接池/Proxy/Observability；禁止直接 SSH/RDP、手工 SQL、服务器热修、真实 Secret 入 GitHub、PRD 访问或真实 Secret。

## 前置条件
100 并发报告和 P5-CP03 PASS；SRE/Product 签署负载、SLO、预算、Stub/受控账户、故障窗口和清理；若等价拓扑或资源采集缺失，BLOCKED，不以纸面推演替代。

## 目标
完成普通 API、长任务积压、供应商限流和单节点退出/重分配，确定 Worker 并发、Queue 分区、连接池、CPU/Memory/IOPS 与扩容阈值。

## Scope
- 仅内部容量、故障恢复和 PRD Sizing；外部写使用 Stub 或受控测试账户。
- 不执行生产业务、真实无上限预算或新功能。

## 实施任务
1. 复用冻结单用户 Golden/Load baseline，设计 300 并发混合负载并分别采集普通 API、长任务、429/5xx。
2. 注入 Web/API/Worker 单节点退出，验证 HA 可用、lease/checkpoint 恢复、无数据损坏/跨 Tenant/审批绕过/重复副作用。
3. 记录成功率、延迟、Queue 回落、DB/Worker/Object/Vendor 资源和费用；若队列不回落，调整 Sizing 后完整重测。
4. 生成带假设、观测、推荐值、上限、扩容阈值和风险的 `prd_capacity` 报告，供 Architecture/Operations 人类批准。

## 验证命令与证据
```powershell
python -m pytest tests\performance\prd_capacity -m "concurrency300"
python -m pytest tests\recovery\uat -k "node or lease or checkpoint"
```
通过 `remote-performance` 运行并保存 Baseline/Load pairwise、资源时序、单节点事件、Queue 回落、错误/副作用计数、Sizing 报告和预算清理证据。

## AI 质量 Checkpoint
执行 `P5-CP03`，结果仅 `PASS`/`FAIL`/`BLOCKED`。PASS：300 场景完成、硬指标基线一致 100%、跨用户错配 0、软评分下降 ≤0.2/4、重复副作用 0、成功率 ≥99.5%、单节点后可用且队列回落；QA/SRE 人类签字，AI 不得批准，不请求 Chain-of-Thought。

## 失败与阻断处理
拓扑不等价、预算/账户/证据缺失为 BLOCKED；损坏、积压、跨域、绕过或退化为 FAIL。调整 Queue/Worker/连接池/超时后重测，不关闭控制面、不降低 Rubric、不把 Stub 成功称作真实外部验收。

## 完成响应格式
报告状态、变更文件、命令/结果、`P5-CP03` 人类结果、Evidence 引用、风险/阻断和 Subphase 05 就绪性。
