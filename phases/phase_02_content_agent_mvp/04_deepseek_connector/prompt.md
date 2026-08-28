# Coding Agent Prompt — Phase 02 / Subphase 04

## 给 Coding Agent 的指令

按照父计划中的 `config/deepseek.yaml` 模板实现 DeepSeek Connector、确定性 Mock、错误标准化、限流和费用门禁。真实调用仅在审批完成的 DEV 远端作业中执行。

## 必须先读

1. [Phase 02 总计划及 DeepSeek 配置模板](../../phase_02_content_agent_mvp.md)
2. [前序 Prompt](../03_skills_and_content_workflow/prompt.md)。
3. Connector SDK、Secret Resolver、Proxy Policy、Content 节点 Contract。
4. 启用真实模式前重新核验 DeepSeek 官方文档。

## 执行位置与权限

- 模式：`hybrid-dev`。
- 所有代码、测试、配置和 fixture 变更必须在 GitHub 分支/Worktree 中完成并经 PR 审查。
- Repo/普通 CI：确定性 Mock 和 fault injection，不发外部 HTTP。
- DEV：受保护 Pipeline、自托管 Runner、Proxy/FQDN 和 Secret Reference。
- Coding Agent 不读取 API Key，不直连生产或绕过 Proxy。

## 前置条件

- Content Workflow Fake 基线为 `PASS`。
- 企业 LLM 审批、数据处理/区域/保留政策、DEV Quota 有记录；缺失时真实路径 `BLOCKED`。

## 目标

实现统一 Connector 接口并使 `BuildBrief/GenerateCopy` 可安全切换 Mock 与批准的 DeepSeek DEV 模式。

## Scope

包含 `connectors/llm/deepseek/`、配置 Schema、Mock fixtures、fault injection、Contract Test 和 DEV Smoke。

不包含 Embedding、媒体、生产 Credential 或 Prompt 质量调优以外的业务逻辑。

## 实施任务

1. 实现 `validate_config/dry_run/execute/get_status/reconcile/cancel/normalize_error`；不支持动作返回 `NOT_SUPPORTED`。
2. 使用父模板创建非敏感配置；默认 `enabled:false`、`mode:mock`。
3. API Key 仅经 Secret Resolver，endpoint/model/quota/proxy 来自配置。
4. 实现连接/请求/总超时、本地队列、预算和最大并发。
5. 对 408/429/5xx 有界指数退避+抖动并尊重 `Retry-After`；4xx Schema/Auth 不盲目重试。
6. 记录 request hash、model/prompt/config version、token/费用，不记录 body/Secret。
7. fixtures 覆盖正常、拒绝、非法 JSON、429、超时、5xx、Token 超限和无来源 Claim。
8. DEV Smoke 只使用批准脱敏数据；缺审批时不运行。

## 验证命令与证据

- Config Schema/unknown field/secret absence Test。
- Mock Contract/Fault/Retry/Budget Test。
- Content Workflow with DeepSeek Mock。
- 受保护 DEV Smoke、Trace 和费用报告。
- Evidence：官方核验、config hash、request/response schema hash、retry trace。

## AI 质量 Checkpoint

执行 `P2-CP02`：

- Checkpoint 结果仅允许 `PASS / FAIL / BLOCKED`；AI 自评不能批准。
- DeepSeek 输出 Claim 来源覆盖 100%，事实错误/虚构数字 0。
- 结构化输出和渠道硬规则 100% 通过；软评分 >= 3.4。
- Mock 无外部 HTTP；Secret 泄漏 0。
- Marketing + QA 复核，AI 自评不能批准；无 DEV 审批则 `BLOCKED`，不保存 Chain-of-Thought。

## 失败与阻断处理

- 官方 endpoint/model/quota 未核验：真实模式 `BLOCKED`。
- Provider 超时/错误：返回类型化状态，不静默退回 Mock。
- 输出质量失败：返回 Prompt/Copy 节点，不扩大 Token/重试掩盖问题。

## 完成响应格式

```text
Status:
Changed files:
Provider/config versions:
Mock and DEV commands/results:
P2-CP02:
Evidence:
Costs/risks/blockers:
Ready for Subphase 05:
```
