# Coding Agent Prompt — Phase 03 / Subphase 02

## 给 Coding Agent 的指令

实现统一 Connector SDK、错误模型、HTTP/Proxy 抽象和无副作用 Channel Dry-run。所有测试使用 Fake Connector。

## 必须先读

1. [Phase 03 总计划](../../phase_03_campaign_agent_and_integrations.md)
2. [前序 Prompt](../01_campaign_contract_and_draft/prompt.md)。
3. Connector Error、Secret Resolver、Proxy Policy、Approval 和 Tool Registry。

## 执行位置与权限

- 模式：`repo`。
- 所有代码、测试、配置和 fixture 变更必须在 GitHub 分支/Worktree 中完成并经 PR 审查。
- 普通 CI 不访问 LinkedIn/Google，不使用 OAuth/Developer Token。
- 不产生外部 Campaign、媒体或费用。

## 前置条件

- P3-CP01 Contract/Draft 为 `PASS`。
- Connector SDK 接口和错误类别已冻结。

## 目标

让两个渠道共享配置校验、Dry-run、执行/状态/对账接口和统一错误语义。

## Scope

包含 Connector Protocol、Config、HttpClient/Proxy/Clock、Fake Connector、Dry-run Policy 和 Contract fixtures。

不包含真实 LinkedIn/Google Adapter。

## 实施任务

1. 先写缺 endpoint/auth/version/quota/proxy、429、超时、4xx、5xx 和 Secret 泄漏测试。
2. 实现 `validate_config/health_check/dry_run/execute/get_status/reconcile/collect_metrics/normalize_error/cancel`。
3. `DryRunResult` 返回 normalized request、warnings/errors 和 fingerprint。
4. Dry-run 检查账户、objective、预算、币种、时区、日期、市场、受众、素材和 Policy。
5. Dry-run 必须无副作用；Fake 记录外部调用次数为 0。
6. 统一 `ConnectorError`：retryable、reconcile_required、provider code、sanitized message。
7. 429 尊重 `Retry-After`；未知外部写状态要求 reconcile-before-retry。
8. Connector 只依赖 SecretResolver/Clock/HttpClient/ProxyPolicy，不接收模型传入 Secret。

## 验证命令与证据

- SDK/Config/Error Unit/Contract Test。
- Dry-run invalid matrix，违规拦截率 100%。
- 断言 Dry-run 外部写调用 0。
- Secret/log/Trace scan。
- Evidence：Contract fixtures、fingerprints、error mapping、call counter。

## AI 质量 Checkpoint

执行 `P3-CP02`：

- Checkpoint 结果仅允许 `PASS / FAIL / BLOCKED`；AI 自评不能批准。
- 预算/账户/地区/受众/排期/素材违规拦截率 100%。
- Dry-run 外部副作用 0。
- Critical 错误分类 100%，修复建议正确率 >= 95%。
- Connector Owner + QA 复核；AI 自评不能批准，不收集 Chain-of-Thought。

## 失败与阻断处理

- 未核验字段：返回 `verification_required`，不猜测。
- Provider 错误正文含敏感内容：脱敏后再进入日志/Agent。
- Dry-run 产生副作用：Critical `FAIL`，停止后续渠道实现。

## 完成响应格式

```text
Status:
Changed files:
Connector/Dry-run summary:
Commands/results:
P3-CP02:
Evidence:
Risks/blockers:
Ready for Subphase 03:
```
