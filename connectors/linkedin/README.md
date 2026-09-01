# linkedin-connector — LinkedIn Advertising Connector（Phase 03 / Subphase 03）

基于共享 Connector SDK 的 LinkedIn Advertising Connector。**仓库内只有
Mock/Contract 实现**：真实 3-legged OAuth、测试广告账户写入和真实指标
读取只允许在受保护 DEV/SIT Job（企业自托管 Runner + Proxy/FQDN +
Secret Manager）中执行。真实路径当前状态：**BLOCKED**（Development
Access、测试账户、内部 Redirect/OAuth Broker、scope 与 API version
的官方核验记录尚未完成）。

## 不变量

- **默认 `enabled: false` / `mode: mock`**：`config/linkedin.yaml` 由
  `load_linkedin_config` 严格加载；API version 只能来自
  `env://LINKEDIN_API_VERSION` 引用，代码不硬编码瞬态版本。
- **最小 scope**：`rw_ads`、`r_ads`、`r_ads_reporting`；超出批准集合的
  scope 在类型层被拒绝，不得自行扩大。
- **OAuth 只走 Authorization Code（成员 3-legged）**：state 绑定且
  单次使用（CSRF）；Token 只以 `SecretValue`（masked）与 Secret
  Manager 引用出现，绝不回写仓库、日志或异常消息；Redirect 只允许
  内部 HTTPS。
- **Mapper 只输出官方已核验字段**：未核验的 objective 映射抛
  `verification_required`（fail closed），不猜测供应商字段或 ID 格式；
  request/response 均保存 sha256 摘要供审计绑定。
- **写入前置校验**：`approval_token_ref` + `input_hash` + 
  `idempotency_key` 缺一不可；同 key 重复投递返回 `ALREADY_EXISTS`
  （同一对象）；同 key 不同 hash 拒绝。
- **超时/断开先对账**：外部创建后超时 → `outcome=UNKNOWN`，
  `reconcile` 通过 idempotency key 找回对象，绝不创建第二对象。
- **部分层级成功**：停止后续写入，`PartialHierarchyError` 记录已创建
  external IDs 并进入 `connector-error.v1` 的 `details`。
- **Metrics 原样保留**：raw provider 字段/类型/缺失值原样保存（缺失
  不等于 0），带 retrieval time、分页游标和 source_response_hash。

## Mock 故障注入

`fixtures/mock_faults.yaml` 与 `config/linkedin.yaml` 场景保持一致：
`HTTP_429`（含 Retry-After）、`AUTH_EXPIRED`、
`TIMEOUT_AFTER_EXTERNAL_CREATE`、`DUPLICATE_DELIVERY`、
`PARTIAL_HIERARCHY_SUCCESS`。

## 运行

```bash
python3 -m pip install -e "packages/infra-core" -e "packages/content-package" \
  -e "packages/campaign-draft" -e "packages/connector-sdk" -e "connectors/linkedin[dev]"
npm run linkedin:test        # pytest
npm run linkedin:typecheck   # mypy strict（src 与 tests）
```

## P3-CP03 检查点

渠道规格违规拦截率 100%、无效审批写调用 0、重复消息重复对象 0、
未知结果先对账 100%。真实权限未批准 → 真实路径 `BLOCKED`，Mock 不能
替代；检查点必须由 API Owner + QA + Security 人工复核，AI 不能自评通过。
