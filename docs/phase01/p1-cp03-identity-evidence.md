# P1-CP03 证据（Identity/Approval/Audit）：Phase 01 / Subphase 05

结果：**BLOCKED（待 Security + IAM Owner 复核；DEV SSO App 未交付）**

按 Subphase 05 提示词规则：AI 自评不能签发 PASS；企业 DEV SSO App/组映射工单未交付时，真实 OIDC 验证保持 BLOCKED，不得以 Fake 成功替代。

## 变更范围

- `apps/api/src/dmt_api/identity/`
  - `roles.py`：8 个角色（Requester、Content Creator、Medical Reviewer、Marketing Reviewer、Campaign Operator、Campaign Approver、Admin、Auditor）；组→角色映射仅服务端受控；职责分离冲突对（Medical Reviewer 与 Campaign Approver 互斥）。
  - `provider.py`：`FakeIdentityProvider`（不透明会话令牌、过期/撤销、角色只来自组映射，客户端自报角色无效）。
  - `oidc.py`：OIDC 优先 `EnterpriseIdentityProvider` —— 服务端验证 issuer、audience、signature（注入式 Verifier）、exp/nbf、单次 state、nonce；未配置企业元数据时抛 `ProviderNotConfiguredError`（BLOCKED，不伪造成功）；Token 内 `roles` Claim 一律忽略。
  - `auth.py`：FastAPI 认证/RBAC 守卫（401/403 类型化信封，凭据永不回显）。
- `apps/api/src/dmt_api/approval_service.py`：Approval 绑定（artifact hash + Policy/Prompt/Skill/Workflow 版本 + 范围 + 账户/预算/时间窗）canonical SHA-256；角色路由（content_publication→Medical Reviewer；campaign_activation/budget_change→Campaign Approver；Admin 无旁路）；自批禁止（仓储层强制）；Token 原子消费；输入变化使旧 Token 立即失效（burn + 审计，fail closed 持久化）。
- 持久化：Migration `0002_approval_binding`（可逆：requests.binding/binding_hash、tokens.revoked_at/revoked_reason）；`consume_token_bound`（仅 APPROVED 且绑定匹配可消费）；`revoke_request`；`list_recent`；`UnitOfWork.commit()`（安全事件显式持久化）。
- 路由：`GET /api/v1/me`；`/api/v1/approvals` 创建/列表/决定/撤销（守卫先于持久化执行；无 DB 时返回类型化 503，不伪造成功）。
- Portal：`/approvals` 只读审批收件箱（服务端取数；未登录显示 BLOCKED 状态，不伪造成功）。

## Repo 测试与结果

| 命令 | 结果 |
|---|---|
| `apps/api: python -m pytest`（含本地 Postgres 16） | 110 passed |
| `apps/api: python -m mypy`（strict） | 25 files，0 issues |
| 根 `npm test` / `npm run typecheck` / `npm run build` | 97 pass / clean / build 成功 |
| `packages/harness-core: python -m pytest` | 45 passed |

## 门禁指标（负向测试证据）

| 指标 | 结果 |
|---|---|
| 未登录 / 伪造会话 / 过期 / 撤销会话拒绝率 | 100%（401） |
| 伪造角色 Claim 生效次数 | 0（角色仅来自服务端组映射） |
| 错误 issuer / audience / 签名 / 过期 / nbf / nonce / state 重用拒绝率 | 100% |
| 自批成功次数 | 0（HTTP 403 `separation_of_duties`；服务与仓储双层强制） |
| 越权角色决定审批成功次数 | 0（Medical↔Campaign 互不可批；Admin 无旁路） |
| Medical Reviewer 与 Campaign Approver 同一身份并存 | 0（组映射解析即抛 RoleConflictError） |
| 未决定 / 被拒 / 过期 / 撤销 Token 消费成功次数 | 0 |
| 并发（8 线程）Token 消费赢家 | 恰好 1 |
| 输入变化后旧 Token 可用次数 | 0（绑定不匹配即 burn，原输入亦不可重放） |
| 审计写入失败时高风险调用成功次数 | 0（决定回滚，状态保持 PENDING） |
| 日志/响应中的 Token 或凭据 | 0（列表/错误信息不含明文 Token） |

## DEV 受保护流水线

未执行 —— 企业 DEV SSO App、组映射与 OIDC 元数据/证书未交付。真实登录、Redirect/Logout 与组映射契约测试保持 **BLOCKED**，只能在受保护 Pipeline + 企业自托管 Runner 中进行。

## 阻断与后续

- BLOCKED 项：DEV SSO App 工单交付后补 OIDC Contract/Integration 测试（不输出 Token）。
- Security + IAM Owner 需复核：角色矩阵、职责分离冲突表、Token 生命周期与审计 fail-closed 行为。
- Subphase 06（Queue/Storage/Secrets/Config）可在本层之上继续。
