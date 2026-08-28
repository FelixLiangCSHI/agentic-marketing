# Coding Agent Prompt — Phase 06 / Subphase 03

## 给 Coding Agent 的指令
统一纪律：采用 TDD，先写失败测试再做 surgical 最小变更；禁止 broad catch、静默 fallback；保留无关用户变更。
准备 PRD Secret Reference 和只读 Credential/Health Smoke；获批准的最小写 Smoke 只能由人类 Operations 在受保护流程执行。执行模式：`remote-prd`。代码、测试、IaC、脚本、Runbook 和脱敏 fixture 在 GitHub 隔离 branch/worktree；禁止 Coding Agent 直接 SSH/RDP、手工 SQL、生产访问或读取真实 Secret。

## 必须先读
- `../../phase_06_pilot_deployment_and_go_live.md`
- `../02_migration_and_ha_deployment/prompt.md`
- 父文档第 3.2、5、6.3、6.6、7、8.2–8.3、13、14 节。

## 执行位置与权限
检查/创建 `scripts/release/smoke_test.py`、`tests/smoke/prd`、`docs/runbooks/prd-smoke-test.md` 和 Secret/Workload Identity 配置。Coding Agent 只能准备/审查 Artifact；Operations/Security 人类拥有 Secret Manager、Credential 注入、PRD 执行和 Go/No-Go，Coding Agent 只审查脱敏结果。禁止直接 SSH/RDP、手工 SQL、服务器热修、真实 Secret 入 GitHub 或生产访问。

## 前置条件
Subphase 02 Migration/HA PASS；每个 Provider 的 Production Access、Quota、FQDN、Security/Legal/Procurement、Rotation/Revoke、SLA/联系人已批准。未批准 Provider 必须保持关闭并 BLOCKED。

## 目标
按 Secret Reference→Service Identity→Connector 最小权限→只读 Credential Health 顺序验证 SSO、Health、Run/Approval 查询、DB/Queue/Object/Trace、Product 检索和四 Provider，不创建外部对象；为获批最小写 Smoke 准备 manifest。

## Scope
- 覆盖 Secret 不泄露、最小权限、读 Smoke、双节点健康和批准写 Smoke 前置。
- 不执行未经批准的 Pilot 或扩大预算。

## 实施任务
1. 仅配置 Secret Reference、版本/到期/Owner metadata；禁止流水线参数、Prompt、UI、Log、Trace、DB 明文包含值。
2. 检查 LinkedIn 3-legged OAuth、Google Developer Token/批准身份、DeepSeek/即梦数据处理/区域/训练/保留/Quota 审批。
3. 编写只读 Smoke：SSO/角色、live/ready、Run/Task/Approval、DB/Queue/Object/Secret Reference/Trace、Product、Credential Health、Web/API 双节点轮询。
4. 设计最小写 manifest，绑定批准 Package、预算、账户、Approval Token、input hash、idempotency key、截止时间；写前二次验证。

## 验证命令与证据
```powershell
python scripts\release\verify_config.py --environment prd
python scripts\release\smoke_test.py --environment prd --read-only
python -m pytest tests\smoke\prd
```
由 `remote-prd` 运行只读 Smoke；获批准写 Smoke 另由人类使用 manifest 执行并立即对账。保存 Secret metadata、Health、角色、版本、无外部对象读证据或批准写的 External ID/Reconcile/Audit。

## AI 质量 Checkpoint
执行 `P6-CP01`、`P6-CP03`，结果只能 `PASS`/`FAIL`/`BLOCKED`。只读 PASS 要求 Contract/Golden 100%、未批准版本/串数 0；写 Smoke PASS 要求未审批写 0、重复对象 0、违规参数 0、Reconcile/Audit 100%；Security/QA/Operations 人类批准，AI 不得签发，不请求 Chain-of-Thought。

## 失败与阻断处理
Secret/Access/Quota/FQDN/审批缺失、Smoke 非零或日志泄漏为 BLOCKED/FAIL；关闭对应 Provider 或 Kill Switch，禁止用 UAT Credential、默认值、Mock 成功或人工改配置替代。

## 完成响应格式
报告状态、变更文件、命令/结果、`P6-CP01`/`P6-CP03` 人类结果、Evidence 引用、风险/阻断和 Subphase 04 就绪性。
