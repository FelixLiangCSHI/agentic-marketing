# ADR-004：轮询获取外部状态，不使用公网 Webhook

- 状态：Accepted
- 日期：2026-08-28
- 决策者：Architecture / Network / Security（待签字复核）

## 背景

部署环境为企业内网：无公网入站、无 CDN、外部服务只允许经批准 Proxy/NAT 的 `443/TCP` 出站。供应商 Webhook（LinkedIn、Google Ads、Buffer、媒体生成等）需要公网可达回调端点，与网络约束冲突。

## 决策

- 所有外部对象状态（Campaign 状态、媒体任务、发布结果、指标）通过**出站轮询**获取。
- 轮询由 Worker 执行，使用指数退避 + 抖动、可配置间隔与配额保护，尊重供应商 Rate Limit。
- 不注册、不暴露任何公网入站 Webhook 端点。
- OAuth 回调采用内部 HTTPS Redirect、OAuth Broker 或受控管理员授权（最终形式待 IAM/Network 确认，见 BLOCKED 清单）。

## 后果

- 状态更新有轮询延迟；对账逻辑（ADR-006）必须容忍最终一致。
- 若未来企业提供受控入站通道，需新 ADR 评估。

## 关联

ADR-006。
