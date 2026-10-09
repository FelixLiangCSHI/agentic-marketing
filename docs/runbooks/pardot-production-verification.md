# Runbook — Pardot 生产只读连接验证

## 范围与成功条件

流水线 [deploy-dev.yml](../../.github/workflows/deploy-dev.yml) 保留原文件名，
但显示名称已改为 `verify-pardot-production`，不再部署 DEV 或应用。
仅执行 Salesforce Client Credentials OAuth 和
`GET https://pi.pardot.com/api/v5/objects/campaigns`。两个请求都必须返回
HTTP 200，响应还必须通过现有连接器的格式校验。空 Campaign 列表也是有效结果。

验证不读取 Prospect，不发送邮件，不测试发送权限，不跟随重定向、不自动重试，
也不回退到 Mock。生产 API 的首屏最多读取 100 条 Campaign；
报告中的 `campaignSampleCount` 不是全量 Campaign 数量。

发布包只包含验证脚本、Pardot 连接器、独立连接器类型和共享受保护凭据读取器，
不依赖 YouTube 页面或 Campaign Delivery UI，也不发布开发目录中的内部数据、
本地凭据或其他未上线功能。既有应用的类型与 YouTube 凭据读取器仍保留兼容导出。

## 执行前的人工门禁

以下项目必须由 Tech Lead 和 IAM/SRE 或对应 Owner 双人复核，不能由 Agent
自行补写为“已批准”。修改本地 YAML 不会自动建立 GitHub 的环境保护规则。

1. 通过正常评审将本次代码发布到仓库 `FelixLiangCSHI/agentic-marketing` 的
   `main`，启用 main 分支保护及所需的双人代码审查。
2. 创建 GitHub Environment `production`：
   - 配置 Required reviewers，并启用 Prevent self-review；
   - 禁止管理员绕过审批；
   - Deployment branches 选择 Protected branches only；
   - 只允许本仓库的受控生产验证 Runner 使用该环境。
   运行时会读取实际环境配置；缺少 Reviewer、防自审或受保护分支限制时，
   在读取 Salesforce 凭据前失败。若 GitHub API 返回管理员绕过为启用，也会失败。
   GitHub Environment 的多个 Reviewer 候选不等于双人审批；双人代码审查和
   生产工单签字必须另外落实。
3. 在 `production` 的 Variables 中配置非 Secret 的审批与凭据引用：

   | Variable | 内容 |
   | --- | --- |
   | `PARDOT_APPROVED_COMMIT_SHA` | 双人审查通过的 main 完整 40 位 commit SHA |
   | `PARDOT_APPROVAL_REFERENCE` | 本次生产只读验证的已签字工单引用 |
   | `PARDOT_CREDENTIALS_SECRET_REF` | 企业 Secret Manager 的 `secretref://` 引用，路径须包含 `prd` 或 `production` 分段 |

   不接受裸凭据、任意输入的源分支或未经批准的 SHA。Owner 更新审批引用或 SHA
   即撤销旧执行参数；审批应按企业流程到期后清除。
4. 配置短生命周期 self-hosted Linux x64 Runner，标签为
   `pardot-production-verification`。不要复用普通 PR Runner 或开发工作站。
   Runner 必须具备获批的企业出站网络、TLS 信任及 Node.js 工具链安装条件。
5. IAM/SRE 使用企业 Secret Manager 和绑定本仓库 `production` Environment 的
   OIDC 短期身份，在获批 Runner 上解析上述 Secret Reference，按既有渠道凭据
   格式供给仓库外的 `~/.agentic-marketing/channel-credentials.json`。
   这是基础设施供给步骤，仓库不实现或假定某个未确认的 Vault/云厂商。
   凭据文件的 `pardot.environment` 必须为 `production`，
   `loginDomain` 与 Business Unit 来自管理员，目录权限 `0700`、文件 `0600`。
   引用与挂载内容对应关系由 Secret Manager Agent/平台审计证明；
   本脚本仅校验引用格式及已有受保护文件，不声称已实现 Secret Manager 解析。
   **不得复制开发机凭据至仓库、GitHub Variables、Artifacts 或聊天，也不得把
   Client Secret 保存成 GitHub 长期 Secret。** Runner 生命周期结束时由平台
   清理凭据挂载及工作目录。

未满足任何前提时保持 BLOCKED，不从普通开发机调用生产 API，也不把本地测试
或 `configured: true` 作为真实连接证据。

## 触发与查看结果

在 GitHub Actions 选择 **verify-pardot-production → Run workflow**：

- 分支仅选择 `main`，其 SHA 必须等于批准的 SHA；
- `approval_reference` 填写与 Environment Variable 一致的工单引用；
- 勾选 `confirm_production_read_only`；
- 由非发起者的生产环境 Reviewer 批准后才进入受控 Runner。

获批的 Runner 执行 `npm run pardot:verify:production`。
该命令在普通本地执行会在任何凭据读取或 HTTP 请求之前返回
`APPROVAL_REQUIRED`；不要伪造 `GITHUB_*` 变量绕过执行边界。

成功时日志与 Job Summary 只记录 HTTP 状态、首屏数量、零业务写入、
检查时间、批准 SHA、工单和 Run ID。不记录 token、Secret、Business Unit ID、
客户、Campaign ID/名称或原始响应。以该 Run URL 和脱敏回执作为验证证据，
成功结论仅为“Pardot 生产只读连接成功”，不包含邮件发送能力。

失败时进程返回非零状态，输出脱敏的 `code`、`stage`、`reason` 和已知的
上游 `httpStatus`。`stage: approval` 先修复审批或环境配置；
`credentials` 检查 Secret Manager 供给、文件权限及生产环境；
`oauth` 由管理员检查 Client Credentials Flow、Run As 与 OAuth scope；
`campaign-query` 检查生产 Business Unit 和 Campaign View 权限。
原始服务端错误、token 和业务记录不得贴入工单或模型上下文。
