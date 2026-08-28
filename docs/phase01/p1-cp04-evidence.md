# P1-CP04 证据（Queue/Storage/Secrets/Config）：Phase 01 / Subphase 06

- 日期：2026-08-28
- 结论：**BLOCKED**（AI 自评不得给出 PASS；需 QA + SRE 会签；DEV 远端验证部分因服务未交付而阻断）

## 变更范围

- 新增 `packages/infra-core/`：`clock.py`、`queue.py`、`objectstore.py`、
  `secrets.py`、`config.py`、`__init__.py`、43 个测试、README、pyproject。
- 新增仓库根 `config/base.yaml` 与 `config/environments/{dev,sit,uat,prd}.yaml`
  示例分层配置（全部 `mode: mock`，仅允许 secretref 引用）。
- CI 新增 `infra` 作业；根 `package.json` 新增 `infra:test` / `infra:typecheck`。
- 未改动既有 `apps/api`、`packages/harness-core`、`src/` 代码。

## Repo 测试与结果

| 套件 | 命令 | 结果 |
| --- | --- | --- |
| infra-core | `python -m pytest`（packages/infra-core） | 43 passed |
| infra-core 类型 | `python -m mypy`（strict） | 0 错误 |
| harness-core 回归 | `python -m pytest`（packages/harness-core） | 45 passed |
| api 回归 | `python -m pytest`（apps/api，本地 PostgreSQL） | 110 passed |
| web 回归 | `npm test` | 97 passed |
| web 类型 | `npm run typecheck` | 0 错误 |

## 门禁指标（负向测试证据）

| 指标 | 要求 | 证据（测试） | 结果 |
| --- | --- | --- | --- |
| 重复投递去重 | 100 次重复投递 → 0 次重复副作用 | `test_queue.py::TestIdempotentEnqueue`、`TestAtLeastOnceSideEffects`（100 次 enqueue → 1 条消息；崩溃 worker + 消费端幂等 → 每个 key 恰好处理 1 次） | 通过（Fake） |
| Worker 崩溃恢复 | 恢复后状态/哈希一致率 100% | `TestLeaseAndCrashRecovery`（租约过期重投递 attempt+1；僵尸 ack/heartbeat 抛 `LeaseExpiredError`） | 通过（Fake） |
| 毒消息 | 最大重试后进入 DLQ 且可回放 | `TestRetryAndDlq`（max_attempts 后入 DLQ 含 last_error；`replay_dlq` 重新入队） | 通过（Fake） |
| 密钥零泄漏 | 异常/日志/repr 不含密钥值 | `test_secrets.py`（`SecretValue` 掩码；缺失密钥启动失败；异常消息不含值） | 通过（Fake） |
| 环境前缀零跨用 | 对象禁止跨环境读写 | `test_objectstore.py`（env 不匹配写入被拒；键前缀强校验） | 通过（Fake） |
| 禁止覆盖 | 版本化、无 delete、显式版本不可覆盖 | `test_objectstore.py`（同键写入版本递增；显式覆盖抛 `OverwriteError`；无 `delete` 属性） | 通过（Fake） |
| 未知配置字段 | 启动即失败 | `test_config.py`（顶层与嵌套未知字段均抛 `ConfigError`） | 通过（Fake） |
| live 模式声明 | endpoint/quota/proxy/secretref 缺一不可 | `test_config.py`（缺失声明失败；原始密钥值代替引用被拒） | 通过（Fake） |
| PRD .env 禁令 | PRD 拒绝 .env 携带密钥 | `test_config.py`（prd + 含密钥 .env → `ConfigError`；非 prd 容忍） | 通过（Fake） |

## DEV 受保护流水线

- **BLOCKED**：真实队列 / 对象存储 / 密钥管理 DEV 服务尚未交付（LLM API、
  即梦 API、LinkedIn API 凭据由用户持有，不进入仓库或本环境）。
- 远端恢复演练、真实 DLQ 回放与密钥解析验证需在服务交付后经受保护流水线执行。

## 阻断与后续

- P1-CP04 需 QA + SRE 会签后方可置为 PASS；当前为 BLOCKED。
- 后续（Subphase 07 起）在本抽象层之上接入 LangGraph 工作流与真实绑定。
