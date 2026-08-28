# Coding Agent Prompt — Phase 01 / Subphase 05

## 给 Coding Agent 的指令

实现 SSO/IAM 适配层、RBAC、职责分离、Approval Service 和不可变 Audit。先用 Fake Identity 完成 Repo 测试，再通过受保护 DEV Pipeline 验证企业集成。

## 必须先读

1. [Phase 01 总计划](../../phase_01_scope_foundation_and_harness.md)
2. [前序 Prompt](../04_harness_loop_tools_and_hooks/prompt.md) 及 Permission/Hook Evidence。
3. Approval、Audit、Run Contract 和企业 IAM 接入资料。

## 执行位置与权限

- 模式：`hybrid-dev`。
- 所有代码、测试、配置、IaC 和 Runbook 变更必须在 GitHub 分支/Worktree 中完成并经 PR 审查。
- Repo：实现 Provider、Policy、API、UI 和测试。
- DEV：只通过受保护 Pipeline、Environment Approval 和企业自托管 Runner 连接 SSO/Secret。
- Coding Agent 不直接 SSH/RDP，不读取真实 Token；普通 PR 只运行 Fake Identity。

## 前置条件

- Subphase 04 为 `PASS`。
- DEV SSO App/组映射工单存在；未交付时真实验证为 `BLOCKED`。

## 目标

实现服务端可信身份、角色映射、内容/活动审批、单次 Token、职责分离和全链路 Audit。

## Scope

包含 Fake/Enterprise Identity Provider、`/api/v1/me`、Approval API/UI、角色 Policy、Token 生命周期和 Audit。

不包含供应商 OAuth、PRD 身份或真实 Campaign 写入。

## 实施任务

1. 先写未登录、伪造角色、自批、越权角色、过期/撤销/重用 Token 和 Audit 故障测试。
2. 实现 `FakeIdentityProvider` 和 OIDC 优先的 `EnterpriseIdentityProvider`。
3. 服务端验证 issuer、audience、signature、expiry、state/nonce；角色只来自受控组映射。
4. 实现 Requester、Content Creator、Medical Reviewer、Marketing Reviewer、Campaign Operator/Approver、Admin、Auditor。
5. Approval 绑定 artifact hash、Policy/Prompt/Skill/Workflow 版本、范围、账户/预算/时间和过期。
6. 发起人不能批准自身高风险动作；Medical 与 Campaign Approver 分离。
7. Token 原子消费；输入变化使旧 Token 失效。
8. DEV Pipeline 只验证登录、组映射、Redirect/Logout 和 Audit，不扩大生产权限。

## 验证命令与证据

- Fake IAM Unit/Security/Approval Test。
- 并发 Token 消费和自批负向测试。
- DEV OIDC Contract/Integration Test；不得输出 Token。
- Audit 完整性和 fail-closed 测试。
- Evidence：角色矩阵、Denied Trace、Token 状态、脱敏 DEV 登录报告。

## AI 质量 Checkpoint

执行 `P1-CP03`：

- 未授权角色、自批、过期/撤销/重用 Token 拒绝率 100%。
- Audit 缺失下高风险调用成功数 0。
- Security + IAM Owner 复核；AI 自评不能签发 `PASS`。
- 无 DEV App 时返回 `BLOCKED`，不得以 Fake 成功替代；不收集 Chain-of-Thought。

## 失败与阻断处理

- 企业 IAM 元数据/证书缺失：保留 Fake 测试并报告 `BLOCKED`。
- Token/身份出现在日志：立即 `FAIL`，清理证据并修复脱敏。
- 远端配置错误：修改 Repo 中声明式配置并重部署，禁止热修。

## 完成响应格式

```text
Status:
Changed files:
Repo tests:
DEV protected-job result:
P1-CP03:
Evidence references:
Security blockers:
Ready for Subphase 06:
```
