# connector-sdk — 统一渠道 Connector SDK（Phase 03 / Subphase 02）

所有渠道 Connector 的统一契约：Connector 协议、共享配置校验、
HTTP/Proxy/Clock/Secret 抽象、归一化错误模型（reconcile-before-retry
语义）、零副作用的渠道 Dry-run，以及仓库内唯一实现——确定性的
`FakeConnector`。**仓库内不存在任何真实 LinkedIn/Google 适配器或
真实网络传输**；真实传输只能由受保护流水线注入。

## 不变量

- **Dry-run 零外部调用**：`run_dry_run` 是纯确定性代码；`FakeConnector`
  记录调用计数供测试断言（`external_write_calls == 0`、
  `http_client.calls == []`）。
- **配置只接受引用**：凭据、API 版本、配额只能是 `secretref://` /
  `env://` / `config://` 引用；原始值在类型层被拒绝。
  `proxy.required=True`、`allow_inbound=False`、
  `reconcile_before_retry=True`、`honor_retry_after=True`
  以 `Literal` 强制，不可关闭。
- **sandbox/live 门禁**：`require_ready_for_mode()` 要求
  `endpoint.verification=="verified"` 且 `enabled=True`；mock 恒通过。
- **幂等外部写**：`execute` 必须携带 `approval_token_ref`、
  `input_hash`、`idempotency_key`；同 key 重复投递返回
  `ALREADY_EXISTS`（同一对象，绝不第二次创建）；同 key 不同
  `input_hash` 直接拒绝。
- **UNKNOWN 先对账**：超时/5xx 后写入结果未知 → `outcome=UNKNOWN`，
  必须 `reconcile` 确认后才允许重试；`RetryPolicy.should_retry`
  在 `reconcile_required` 且未对账时返回 False。429 始终尊重
  `Retry-After`。
- **错误消息脱敏**：`sanitize_message` 剥离 token/secret 形态内容；
  `normalize_error` 输出冻结的 `connector-error.v1` 文档，
  `reconcile_required` 位于 `details`。

## 跨语言契约

Dry-run 报告契约为
`packages/domain-contracts/schemas/campaign-dry-run.v1.schema.json`，
TypeScript（Ajv）与 Python（pydantic `CampaignDryRunV1`）对同一批
golden/invalid fixture 结论一致。

## 运行

```bash
python3 -m pip install -e "packages/infra-core" -e "packages/content-package" \
  -e "packages/campaign-draft" -e "packages/connector-sdk[dev]"
npm run connectorsdk:test        # pytest
npm run connectorsdk:typecheck   # mypy strict（src 与 tests）
```

## P3-CP02 检查点

拦截率 100%（所有策略违规均以结构化错误报告）、外部副作用 0、
错误分类与重试语义可测试。检查点必须由人工审核 PASS，AI 不能自评通过。
