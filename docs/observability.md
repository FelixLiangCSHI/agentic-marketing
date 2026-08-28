# 可观测性契约：Trace 字段、指标与告警（Phase 01 / Subphase 07）

本文档定义统一的 OpenTelemetry Trace 字段、Run/Tool/Queue/Cost 指标和告警规则。
本地开发使用 `infra/local/` 的 OTel Collector（debug exporter）；企业监控栈交付后
仅替换 exporter，字段与指标名不变。日志与 Trace **禁止包含 Secret 值**；凭据只允许
以 `secretref://` 引用形态出现。

## 1. 统一 Trace 字段（Critical 字段完整率要求 100%）

所有 Span 必须携带（`dmt.` 前缀为本项目命名空间）：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `dmt.environment` | string | 是 | `local/dev/sit/uat/prd`，与配置层一致 |
| `dmt.tenant_id` | string | 是 | 租户；对象存储前缀同源 |
| `dmt.agent_type` | string | 是 | `content` 或 `campaign`，两 Agent 命名空间隔离 |
| `dmt.run_id` | string | 是 | Run 主键；关联 Run Journal 与 Audit |
| `dmt.task_id` | string | 否 | Task DAG 节点 |
| `dmt.workflow_id` | string | 否 | LangGraph Workflow 实例 |
| `dmt.tool_name` | string | 工具 Span 必填 | Tool Registry 中的名称 |
| `dmt.tool_level` | string | 工具 Span 必填 | `L1/L2/L3/L4` |
| `dmt.approval_id` | string | L3 必填 | 审批令牌关联的 Approval 记录 |
| `dmt.queue.topic` / `dmt.queue.delivery_id` / `dmt.queue.attempt` | string/int | 队列 Span 必填 | 与 infra-core 队列语义一致 |
| `dmt.config_hash` | string | 是 | `AppConfig.config_hash()`，保证配置可追溯 |
| `dmt.idempotency_key` | string | 外部写必填 | 幂等外部写（ADR-006） |

关联规则：Portal/API 的请求 Trace → Run Span → Tool Span → Queue/DB Span 通过
`trace_id` + `dmt.run_id` 双向可查；Audit Record 存 `trace_id` 引用而非日志原文。

## 2. 指标

| 指标 | 类型 | 标签 | 说明 |
| --- | --- | --- | --- |
| `dmt_run_total` | counter | environment, agent_type, status | Run 结果计数 |
| `dmt_run_duration_seconds` | histogram | agent_type | Run 时长 |
| `dmt_tool_call_total` | counter | tool_name, tool_level, decision | 工具调用与 allow/deny |
| `dmt_tool_error_total` | counter | tool_name, error_kind | 工具失败 |
| `dmt_approval_pending` | gauge | agent_type | 待审批数量 |
| `dmt_queue_depth` | gauge | topic | 队列积压 |
| `dmt_queue_retry_total` | counter | topic | 重试次数 |
| `dmt_dlq_depth` | gauge | topic | DLQ 深度 |
| `dmt_worker_heartbeat_timestamp` | gauge | worker_id | Worker 最近心跳 |
| `dmt_llm_cost_usd_total` | counter | agent_type, model, mode | 模型调用成本（mock 模式为 0） |
| `dmt_audit_write_failure_total` | counter | — | 审计写失败（必须为 0，失败即停止 Run） |

## 3. 告警定义

| 告警 | 条件 | 级别 | 响应 |
| --- | --- | --- | --- |
| L3 未审批执行尝试 | `dmt_tool_call_total{tool_level="L3",decision="deny_missing_approval"}` 增长 | P2 | 审查调用方与 Prompt；重复出现升级 Security |
| L4 调用尝试 | `dmt_tool_call_total{tool_level="L4"}` > 0（任何 decision） | P1 | 立即 Incident；L4 永不允许 |
| DLQ 积压 | `dmt_dlq_depth` > 0 持续 10 分钟 | P2 | 按 Runbook 分析毒消息并决定 replay |
| 审计写失败 | `dmt_audit_write_failure_total` > 0 | P1 | Run 已 fail-closed；恢复审计存储后复盘 |
| 费用异常 | `dmt_llm_cost_usd_total` 1 小时增量超预算阈值 | P2 | 检查配额与 quota_per_minute 配置 |
| Worker 心跳丢失 | `now - dmt_worker_heartbeat_timestamp` > 3×心跳间隔 | P2 | 队列租约会自动回收；确认 Worker 状态 |
| Secret 泄漏嫌疑 | 日志/Trace 扫描命中凭据模式 | P1 | 立即撤销凭据并按 Incident 处理 |

## 4. Dashboard 最小查询

- 按 `dmt.run_id` 汇总一次 Run 的全部 Span、工具决策与审批引用。
- 按 `dmt.approval_id` 反查触发的 Run 与工具调用。
- 队列健康：`dmt_queue_depth`、`dmt_queue_retry_total`、`dmt_dlq_depth` 按 topic。
- 成本：`dmt_llm_cost_usd_total` 按 agent_type/model 分解。

## 5. 边界

- 普通 PR CI 不上报遥测；本地栈 Collector 仅 debug 输出。
- 企业 Dashboard/Alert 平台交付后，把本文件的定义落成平台配置并回传脱敏 Evidence。
