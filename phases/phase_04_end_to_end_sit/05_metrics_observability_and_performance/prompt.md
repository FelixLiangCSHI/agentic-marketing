# Coding Agent Prompt — Phase 04 / Subphase 05

## 给 Coding Agent 的指令
统一纪律：采用 TDD，先写失败测试再做 surgical 最小变更；禁止 broad catch、静默 fallback；保留无关用户变更。
核验 Raw/Normalized Metrics、报告追溯、Trace/Audit/Alert，并建立 50 并发 SIT 基线；不擅自承诺未签字 SLO。执行模式：`remote-sit`。代码、测试、IaC、脚本、Runbook、脱敏 fixture 只在 GitHub 隔离 branch/worktree；负载和远端指标只能通过受保护 Pipeline/Environment Approval/企业自托管 Runner。

## 必须先读
- `../../phase_04_end_to_end_sit.md`
- `../04_queue_recovery_and_security/prompt.md`
- 父文档第 6.8、6.10、6.11、7、8.4、9、10、14 节。

## 执行位置与权限
检查/创建 `tests/integration/sit/test_metrics_and_reports.py`、`tests/performance/sit`、`evals/content/sit`、`docs/runbooks/connector-reconciliation.md` 及 Dashboard/Alert 定义。Coding Agent 不得直接 SSH/RDP、手工 SQL、服务器热修、真实 Secret 入 GitHub、生产访问或接触真实 Secret。

## 前置条件
Subphase 04 安全/恢复 PASS；已批准 Raw fixtures、公式版本、Trace backend、Alert index、费用/Quota 阈值和 50 并发窗口。缺少远端指标或资源采集证据为 BLOCKED，不用 Mock 代替。

## 目标
证明指标数值/公式/来源/新鲜度和缺失语义正确，Critical Run 可按 trace_id 查询全字段，告警可行动；混合 50 并发下无数据错乱、审批绕过、重复副作用且队列回落。

## Scope
- 覆盖 `SIT-METRIC-01`、`SIT-OPS-01`、`SIT-PERF-01`。
- 负载包含 Portal 查询、Content、媒体、Campaign Dry-run、测试发布和 Metrics Poll。

## 实施任务
1. 验证 Raw 只追加、Normalized 带公式版本、缺失/权限/不可用/真实 0 不互转、分页/cursor/watermark 可恢复去重；报告追溯 Raw Metric ID/response hash。
2. 让 `run_id, task_id, agent_type, workflow_version, tool_call_id, approval_id, content_package_id, campaign_id, external_object_id, model, prompt_version, policy_version` 均可由 trace_id 查询。
3. 定义并测试无审批 L3/L4、未知外部写、DLQ、未批准 Claim、费用/Quota 80%、RAG 过期、Worker 无心跳和 Audit 失败告警；每个有 Owner、严重度、去重键、通知、Runbook、关闭条件。
4. 通过受控负载采集 API p50/p95/p99、Queue Depth/Oldest Age、Worker 利用率/心跳、DB 连接/CPU/IOPS、外部 429/5xx、Token/媒体/费用；确认窗口后队列回落。
5. 生成资源报告，为 Phase 05 100/300 并发设计提供数据；不得用性能优化关闭审批、审计、TLS、DLP 或预算。

## 验证命令与证据
```powershell
python -m pytest tests\integration\sit\test_metrics_and_reports.py
python -m pytest tests\performance\sit
python -m pytest tests\security\sit -k "audit or alert"
```
经 `remote-sit` 运行 50 并发混合负载；保存 Raw/Normalized/Formula/Report、Trace/Audit completeness、告警触发/关闭、资源时序、错误率、队列回落和费用报告。

## AI 质量 Checkpoint
执行 `P4-CP03`、`P4-CP04`，结果为 `PASS`/`FAIL`/`BLOCKED`。PASS：数值/公式一致 100%、Raw 追溯 100%、虚构/自动执行建议 0、Critical 场景和 Trace/Audit 100%、软评分至少 3.4/4；Data Owner、Marketing、QA/SRE 人类判定，AI 自评不可批准，不请求 Chain-of-Thought。

## 失败与阻断处理
指标错配、缺失转 0、不可追溯、告警无 Owner、跨用户响应、队列不回落或资源证据缺失分别 FAIL/BLOCKED。按 Metric/Report/Observability/Queue 节点最小返工；不吞错、不编造 SLO、不以 Mock/人工文本替代执行证据。

## 完成响应格式
报告状态、变更文件、命令/结果、`P4-CP03`/`P4-CP04` 人类结果、Evidence 引用、风险/阻断和 Subphase 06 就绪性。
