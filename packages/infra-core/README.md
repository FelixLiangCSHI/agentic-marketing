# infra-core — 队列 / 对象存储 / 密钥解析 / 分层配置（Phase 01 / Subphase 06）

平台基础设施抽象与本地 Fake 实现。仓库内不包含任何真实远端绑定；真实
DEV/SIT/UAT/PRD 服务通过受保护流水线在后续子阶段接入。

## 模块

- `infra_core.clock` — `Clock` 协议、`SystemClock` 与可控推进时间的 `FakeClock`。
- `infra_core.queue` — `QueueClient` 协议与 `FakeQueueClient`：at-least-once
  投递、幂等键去重（完成后仍持久去重）、租约 + 心跳、最大重试 + 指数退避
  （确定性抖动）、DLQ 与 `replay_dlq`、任务取消。
- `infra_core.objectstore` — `ObjectStore` 协议与 `FakeObjectStore`：
  `environment/tenant/agent/run_id/name` 键前缀校验、环境绑定、sha256、
  自动版本递增（禁止就地覆盖，无 delete）、大小 / MIME 限制、恶意内容扫描钩子。
- `infra_core.secrets` — `SecretRef`（`secretref://provider/path`）、掩码的
  `SecretValue`、`SecretResolver` 协议与 `FakeSecretResolver`；异常信息不含密钥值。
- `infra_core.config` — 分层配置 `base -> environment -> agent -> workflow ->
  tenant/market`，未知字段一律拒绝；`mode: mock|sandbox|live` 默认 mock，
  非 mock 必须声明 endpoint、quota、proxy 与 `secretref://` 引用；PRD 拒绝
  `.env` 携带密钥；`config_hash()` 输出稳定哈希用于审计。

## 安全不变量（负向测试验证）

- 100 次重复投递 → 恰好 1 条消息、消费者侧 0 次重复副作用。
- 毒消息在 `max_attempts` 后进入 DLQ 并记录 `last_error`，可 `replay_dlq`。
- Worker 崩溃（租约过期）后消息以 `attempt+1` 重新投递；僵尸 ack/heartbeat 被拒绝。
- 缺失密钥启动即失败；任何异常与 repr 均不包含密钥明文。
- 对象禁止跨环境写入、禁止覆盖既有版本、恶意内容被扫描钩子拦截。
- 未知配置字段（顶层或嵌套）导致启动失败。

## 开发命令

```bash
cd packages/infra-core
pip install -e ".[dev]"
python -m pytest      # 43 个测试
python -m mypy        # strict
```

仓库根：`npm run infra:test` / `npm run infra:typecheck`。

## 边界

- 仅本地 Fake；`mode: mock` 是默认且唯一在仓库内允许运行的模式。
- 不发起网络调用，不读取真实凭据；密钥只能以 `secretref://` 引用出现。
- 示例配置见仓库根 `config/base.yaml` 与 `config/environments/*.yaml`。
