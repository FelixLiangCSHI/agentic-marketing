# campaign-metrics

Phase 03 / Subphase 06: Raw Metrics 摄取、独立 Normalization、Performance Report
与只读 Strategy Recommendation。精确数值全部由确定性代码计算，模型只解释证据。

## 职责

- **Raw Metrics（不可变）**：按主计划 §11.1 保存 provider
  field/value/type/currency/timezone/attribution window/window/version/
  retrieved/source hash；以
  `(channel, object, field, period, source_response_hash)` 去重，
  只追加——供应商修订是新行，禁止 UPDATE（DDL 层有 append-only trigger）。
  缺失、不可用与真实 `0` 绝不互相转换。
- **Normalized Metrics（可重算）**：独立层，Decimal 数值、显式
  `formula_version`（当前 `fv1`）与 source raw metric IDs；
  币种/时区/归因窗口不一致或无法可靠转换 → `not_available`，不插补。
  统一维度：impressions / clicks / spend / conversions / ctr / cpc / cpm /
  conversion_rate（公式与 `src/analysis` 确定性引擎兼容：
  CTR = clicks ÷ impressions，分母为 0 → not_available）。
- **Ingest（watermark/cursor）**：每页写入后持久化 checkpoint，
  Worker 重启后从 cursor 恢复；重复拉取 0 新行；分页中断不丢数据。
  两渠道适配器复用 `linkedin_connector.fetch_metrics_page` 与
  `google_ads_connector.fetch_gaql_page`（结构化注入，本包不 import 供应商 SDK）。
- **PerformanceReport**：`performance-report.v1` 契约；每个数字引用
  raw IDs、公式版本与新鲜度；没有数据就是 `not_available` + 原因，
  预算差异只对照已批准上限。
- **StrategyRecommendation**：`strategy-recommendation.v1` 契约；恒为
  `DRAFT`，每条建议绑定报告内 `ok` 状态的证据（虚构证据直接拒绝）、
  风险与置信度；`executed` 恒为 `false`——任何执行都生成新的
  ActivationRequest 或人工任务，本包无任何渠道写 Tool。

## 边界

仓库内只有确定性 fixture 与 Fake 存储；真实 DEV/SIT 双渠道 metrics pull
仅在受保护流水线执行。持久化 DDL 见
`apps/api/migrations/versions/0005_raw_normalized_metrics.py`
（`campaign.raw_channel_metrics` / `campaign.normalized_metrics`）。

## 运行

```bash
pip install -e "packages/campaign-metrics[dev]"
npm run campaignmetrics:test
npm run campaignmetrics:typecheck
```
