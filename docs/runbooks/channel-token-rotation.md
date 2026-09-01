# Runbook — Channel Token Rotation（LinkedIn / Google Ads 凭据轮换）

`config/linkedin.yaml` 与 `config/google_ads.yaml` 的 `rotation_runbook`
指向本文件。所有凭据只以 Secret Reference（`secret://` / `secretref://`）
存在；真实值只进入远端 Secret Manager，禁止出现在 Git、fixture、日志、
Trace、错误响应或模型上下文。

## 1. 凭据清单（引用名，不含值）

| 渠道 | 引用 | 类型 | 轮换方式 |
|---|---|---|---|
| LinkedIn | `secret://dmt/${DMT_ENV}/linkedin/client-id` / `client-secret` | OAuth App | 供应商后台重置后写入 Secret Manager |
| LinkedIn | `secret://dmt/${DMT_ENV}/linkedin/refresh-token` | 3-legged OAuth Refresh Token | 受控管理员重新授权（内部 Redirect/OAuth Broker） |
| Google Ads | `secret://dmt/${DMT_ENV}/google_ads/developer-token` | Developer Token | Google Ads 后台重置；独立审计 |
| Google Ads | `secret://dmt/${DMT_ENV}/google_ads/oauth-client-id` / `oauth-client-secret` / `refresh-token` | OAuth | 重新 Consent 后替换 |
| 共用 | `secret://dmt/${DMT_ENV}/egress/proxy-url` / `ca-bundle` | Egress Proxy | 基础设施 Owner 轮换 |

## 2. 定期轮换步骤

1. 提交工单，记录环境（DEV/SIT/UAT/PRD）、引用名与轮换原因。
2. 在受控管理员工作站/OAuth Broker 完成新授权；LinkedIn 必须使用成员
   3-legged Authorization Code（禁止 Client Credentials），Google 默认
   OAuth（Service Account 仅限有企业所有权审批记录的账户）。
3. 新值写入 Secret Manager 的同一引用名（版本化）；不修改任何仓库文件。
4. 在受保护流水线运行 connector `health_check` + 只读冒烟（mock 之外的
   验证仅限 DEV/SIT 测试账户）。
5. 确认新版本生效后吊销旧 Token/Key；记录吊销时间与执行人。

## 3. 泄漏 / 离职 应急

1. 立即吊销供应商侧 Token（LinkedIn App 后台 / Google Cloud Console），
   再吊销 Secret Manager 版本 —— 顺序不可颠倒。
2. 触发日志/Trace 扫描（`scripts/check_no_secrets` + 远端日志检索），
   确认无明文落盘；命中即提交安全事件。
3. 冻结相应渠道 Feature Flag（`config://features/*-real-api`），连接器
   回落 `mode: mock`，队列消息停住而非失败。
4. 重新授权（见第 2 节），双人复核后恢复 Flag。

## 4. 验证与证据

- 仓内门禁：`connectors/*/tests/test_auth.py`、`test_config.py`（拒绝
  明文凭据、拒绝未核验配置）、`scripts/check_no_secrets`。
- 每次轮换在工单中归档：引用名、Secret 版本号、健康检查结果、吊销记录。

Owner：Security（审批/应急）、IAM（授权方案）、Connector Owner（验证）。
