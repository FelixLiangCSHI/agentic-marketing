# Phase 01 BLOCKED 清单

> 版本：2026-08-28。原则：不替业务方做高风险假设；阻断项解除前相关能力保持 `mode: mock` / Fake。

| ID | 阻断项 | 负责人 | 最晚日期 | 未解除时的影响与默认处置 |
|---|---|---|---|---|
| B-01 | Product Data (MDM/PIM/DAM) Owner、Schema、版本与批准状态未确认 | Product Data Owner | 2026-08-28 | 阻断批准 RAG；RAG 仅 Fake Contract |
| B-02 | 企业 SSO DEV App 未建立；OIDC 或 SAML 形式未确认 | IAM | 2026-08-28 | 仅 FakeIdentityProvider；若只有 SAML 需 Gateway/Broker 转换或单独 ADR |
| B-03 | DeepSeek/企业 LLM 与 Embedding 服务的企业审批未完成 | Architecture / Security | 2026-08-28 | 保持 `mode: mock`；禁止真实模型请求 |
| B-04 | LinkedIn Marketing API 与 Google Ads Developer Token 未获批 | Product Owner | 2026-08-28（申请启动） | Fake Connector + Contract Test；Phase 03 真实接入阻断 |
| B-05 | 即梦正式企业 API 区域、租户、认证方式与数据处理条款未确认 | Marketing / Procurement | 2026-09-04 | 媒体生成保持 `mode: mock` |
| B-06 | 对象存储、Queue/DLQ、Secret/KMS、监控、出站 Proxy 与四环境 VM/DB/域名工单未提交 | Operations / Network / DBA / Security | 2026-09-04 | 仅本地 Fake Infra；企业集成门禁无法验收（Phase 01 定义为 Repo-first Hybrid，代码可先行） |
| B-07 | OAuth 回调形式（内部 HTTPS Redirect / OAuth Broker / 受控管理员授权）未定 | IAM / Network | 2026-09-04 | 阻断渠道真实授权；仅保留扩展点 |
| B-08 | 范围冻结决策表（首发渠道、LinkedIn 有机发布、邮件发送等）待 Owner 签字 | Product Owner / Marketing / Legal | 2026-08-28 | 采用总控文档默认值推进；默认值变化时更新 ADR 与追踪矩阵 |
| B-09 | 真实 Medical Reviewer 未指定 | Medical / Compliance | 2026-08-28 | Agent 不得生成最终医疗批准；审批链保留 Medical 角色占位 |
| B-10 | P1-CP01 人工复核（Product Owner + Architect）未签字 | Product Owner + Architect | Subphase 02 开始前 | AI 自评不能签发 PASS；本子阶段结论为 BLOCKED 直至签字 |

## 更新记录

### 2026-08-28：Subphase 01 人工审批通过，Subphase 02 启动

- B-10 解除：Subphase 01 人工审批已通过（用户确认），Subphase 02 开始执行。
- B-03 / B-04 / B-05 部分解除：LLM API、即梦 API、LinkedIn API 的申请均已获批（用户确认）。
  但出于数据泄露风险控制，真实 Credential **不提供给 Coding Agent / 仓库 / CI**；
  Secret 值仅保留在企业侧。因此仓库内所有相关能力继续保持 `mode: mock` / Fake Connector，
  真实接入按计划在受保护流水线与远端环境验证（Phase 02/03 门禁不变）。
- Google Ads Developer Token 状态未在本次确认中提及，B-04 中对应部分维持原状。
