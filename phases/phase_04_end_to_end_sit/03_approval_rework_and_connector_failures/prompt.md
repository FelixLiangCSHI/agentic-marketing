# Coding Agent Prompt — Phase 04 / Subphase 03

## 给 Coding Agent 的指令
统一纪律：采用 TDD，先写失败测试再做 surgical 最小变更；禁止 broad catch、静默 fallback；保留无关用户变更。
以 TDD 验证审批拒绝、定点返工、Token/Package 失效和四类 Connector 故障；所有错误必须结构化、可重试性准确且不得假成功。执行模式：`remote-sit`。所有代码、测试、IaC、脚本、Runbook、脱敏 fixture 在 GitHub 隔离 branch/worktree；远端故障注入仅走受保护 Pipeline/Environment Approval/企业自托管 Runner。

## 必须先读
- `../../phase_04_end_to_end_sit.md`
- `../02_end_to_end_happy_path/prompt.md`
- 父文档第 6.5、6.6、7、8.1–8.3、12、13、14 节。

## 执行位置与权限
检查/创建 `tests/integration/sit/test_rejection_and_rework.py`、`tests/integration/sit/test_external_write_reconciliation.py`、`tests/workflow/sit`、`tests/fixtures/sit/{deepseek,jimeng,linkedin,google_ads}`、`docs/runbooks/connector-reconciliation.md`。禁止直接 SSH/RDP、手工 SQL、服务器热修、将真实 Secret 写入 GitHub、真实 Secret/生产访问。

## 前置条件
Subphase 02 的正常链路 Evidence PASS；故障 Stub/Fault Proxy、测试 Token、审批身份、外部测试账户及预算均获批准。缺远端故障环境或真实账户时 BLOCKED，不用 Mock 成功替代真实 Contract。

## 目标
证明 Compliance Critical 会阻断审批，Copy 可定点返工；内容/预算变化使旧审批失效；自批、过期/撤销/已用 Token/Package 100% 拒绝；DeepSeek、即梦、LinkedIn、Google Ads 对 429、408、5xx、400、401、DNS/TLS/Proxy 和格式变化遵守错误策略。

## Scope
- 覆盖 `SIT-E2E-002` 至 `008`、Connector 故障矩阵和外部写未知状态。
- 不覆盖 Queue/Worker 恢复、50 并发和 UAT。

## 实施任务
1. 为 Critical Claim、Requester 自批、Medical 执行 Campaign Approval、过期/撤销 Package、相同 Token 不同 hash 写失败测试并验证结构化 Audit。
2. 验证 Reviewer 指定 Copy 只重跑 Copy 及下游，已通过检索节点不重跑；新版本生成新 hash，旧 Approval 失效。
3. 注入 429/Retry-After、有界指数退避抖动、408/5xx 熔断、400/Schema 不重试、401 轮换任务、Proxy/TLS 拒绝和 malformed response；禁止静默默认。
4. 对外部写超时已创建、进程崩溃、100 次重复、同 key 异 hash、部分成功和供应商手工修改执行先对账；未知状态进人工队列/DLQ。
5. 修复只允许失败测试后 surgical diff；更新 Connector Contract、回归和脱敏 Evidence。

## 验证命令与证据
```powershell
python -m pytest tests\integration\sit\test_rejection_and_rework.py tests\integration\sit\test_external_write_reconciliation.py
python -m pytest tests\contract tests\workflow -k "approval or retry or connector"
python -m pytest tests\security\sit -k "approval or token"
```
在 `remote-sit` 运行批准故障矩阵；保存 fault input、错误分类、Retry-After、Circuit、Journal、Approval、Reconcile、Audit 和无副作用计数，所有日志脱敏。

## AI 质量 Checkpoint
执行 `P4-CP01`、`P4-CP02`，结果只能 `PASS`/`FAIL`/`BLOCKED`。PASS：Critical 错误分类 100%、错误成功化 0、重复副作用 0、恢复/版本状态一致 100%、Claim/hash 100%；QA、SRE、Medical 人类 Owner 判定，AI 自评不能批准，不收集 Chain-of-Thought。

## 失败与阻断处理
证据缺失或真实外部路径不可用为 BLOCKED；错误分类、旧审批仍有效、盲目重试、未审批写或泄漏为 FAIL。按 Checkpoint 返回 Error Mapping/Workflow/Retry/Mapper 节点，连续同类失败暂停自动返工；不得 broad catch、扩大权限、关闭审计或伪造成功。

## 完成响应格式
报告状态、变更文件、命令/结果、`P4-CP01`/`P4-CP02` 人类判定、Evidence 引用、剩余风险/阻断和 Subphase 04 就绪性。
