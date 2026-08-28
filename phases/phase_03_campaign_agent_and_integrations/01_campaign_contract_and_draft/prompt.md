# Coding Agent Prompt — Phase 03 / Subphase 01

## 给 Coding Agent 的指令

实现 Campaign Proposal、Activation Request 和 Draft 的权威契约。只消费已批准、未过期、hash 匹配的 Content Package；不要提前调用渠道 API。

## 必须先读

1. [Phase 03 总计划](../../phase_03_campaign_agent_and_integrations.md)
2. Phase 02 最终 `ApprovedContentPackage` Contract、RC 和 P2 Checkpoint Evidence。
3. Phase 01 Approval/Tool/Run/Connector Error Contract。

本子阶段是 Phase 03 起点。

## 执行位置与权限

- 模式：`repo`。
- GitHub Worktree/普通 CI 使用批准 Package fixture 和 Fake Clock。
- 无 OAuth、渠道 Credential、远端 API 或外部副作用。

## 前置条件

- Phase 02 P2-CP01 至 P2-CP06 为 `PASS`。
- Campaign 目标、预算、市场、币种和渠道范围已冻结。

## 目标

创建可审查、确定性、版本化的 `CampaignProposal`/`ActivationRequest` 和 canonical hash。

## Scope

包含 Campaign Contract、Draft Builder、版本/失效和 API 占位。

不包含 Connector、Dry-run、发布、指标或 Strategy。

## 实施任务

1. 先写过期/撤销 Package、hash 不匹配、缺渠道变体、负预算、非法币种/时区/市场和未知字段测试。
2. 创建/完善：
   - `campaign-proposal.v1.schema.json`
   - `activation-request.v1.schema.json`
   - Draft Domain Model。
3. 规范化账户内部 ID、objective、预算、排期、受众、素材 hash、Policy/Workflow 版本。
4. 使用 Decimal/最小货币单位，禁止浮点误差、NaN 和负数。
5. 相同输入+版本+Fake Clock 产生稳定 proposal/request hash；字段变化创建新版本。
6. Campaign Agent 只接收 `APPROVED` 且有效 Package，不读取 Content 私有 Context/Credential。
7. Draft 状态固定为 `DRAFT`，不创建外部对象。
8. 为 Python/TypeScript 建立共享 Golden/Invalid fixtures。

## 验证命令与证据

- 双语言 Contract Test。
- Draft deterministic/hash/version Unit Test。
- Package validity、预算/时间/受众 Security Test。
- Phase 02 Contract compatibility Test。
- Evidence：Schema/hash、Package-Proposal diff、fixture 版本。

## AI 质量 Checkpoint

执行 `P3-CP01`：

- Content hash 匹配 100%，批准 Claim 漂移 0。
- 必填字段和渠道变体完整率 100%。
- Draft 事实/预算/受众软评分 >= 3.4/4。
- Marketing + Campaign Operator 复核。AI 自评不能 `PASS`；输出 `PASS / FAIL / BLOCKED` 和 Evidence，不收集 Chain-of-Thought。

## 失败与阻断处理

- Package 未批准/过期：阻断，不回到模型猜测替代内容。
- Contract 冲突：返回 Phase 02/Domain Contract Owner 协调，不使用类型断言绕过。
- 业务参数未冻结：`BLOCKED`。

## 完成响应格式

```text
Status:
Changed files:
Contract/hash summary:
Commands/results:
P3-CP01:
Evidence:
Blockers:
Ready for Subphase 02:
```
