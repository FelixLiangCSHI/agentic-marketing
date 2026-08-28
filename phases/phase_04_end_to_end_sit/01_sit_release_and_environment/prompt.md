# Coding Agent Prompt — Phase 04 / Subphase 01

## 给 Coding Agent 的指令
统一纪律：采用 TDD，先写失败测试再做 surgical 最小变更；禁止 broad catch、静默 fallback；保留无关用户变更。
以最小、可审查的变更准备 SIT Release Candidate、部署定义和环境门禁；严格继承父文档，不修改父文档或其他无关用户变更。执行模式：`remote-sit`。代码、测试、IaC、脚本、Runbook 和脱敏 fixture 只能在 GitHub 的隔离 branch/worktree 修改；远端执行只能通过受保护 Pipeline、Environment Approval 和企业自托管 Runner。

## 必须先读
- `../../phase_04_end_to_end_sit.md`
- Phase 01–03 中已存在的 Harness、Approval、Audit、Queue、Contract、Migration、CI 和 RC 约定。
- 先读完本阶段父文档的第 2、3、4、5、6.1–6.3、8.5、9、10、13、14 节。

## 执行位置与权限
Repo 中检查/创建 `infra/sit/{deployment,config,network,observability}`、`tests/fixtures/sit`、`docs/runbooks/sit-deployment.md`、`docs/runbooks/sit-test-plan.md` 及必要 CI 定义；真实 SIT DNS、TLS、SSO、DB、Queue、Bucket、Secret、Proxy 和账户仅由批准的 Pipeline/Environment 执行。禁止 Coding Agent 直接 SSH/RDP、服务器热修、手工 SQL、真实 Secret 入 GitHub 或任何生产访问。

## 前置条件
- Phase 01–03 Critical CI、Migration 正向/回退/再正向和不可变 SHA/digest 已有证据。
- SIT DNS/TLS、独立 SSO、PostgreSQL、三类 Queue/DLQ、Object Store、Secret Namespace、Proxy/NAT、Observability、LinkedIn/Google 测试账户均有 Owner 和批准记录。
- 缺任一远端访问、凭据或环境证据，立即输出 `BLOCKED`；不得用 Mock 冒充真实门禁。

## 目标
冻结可复现 RC，声明 SIT 拓扑和配置隔离，按 Database→Queue/Storage/Secret→Observability→API→Worker→Web→Gateway 顺序部署，并证明 live/ready 健康检查不产生外部副作用。

## Scope
- 只覆盖 SIT RC、配置 Schema、部署/IaC、健康检查、环境隔离和启动 Runbook。
- 不启用 PRD Credential、真实业务预算、公网入口或新渠道。

## 实施任务
1. 建立 RC manifest，记录 commit SHA、镜像 digest、Migration、Prompt/Model/Policy/Skill/Workflow、Connector/API version 和非敏感 config hash。
2. 定义 Web 8080、API/Worker 8000、PostgreSQL 16 私网端点、内部 HTTPS 443、无公网入站和批准 FQDN Allowlist；声明四环境资源不得共享。
3. 为 `/api/health/live` 和 `/api/health/ready` 编写测试，ready 必须检查 DB、Queue、Object Store 和关键配置且不调用模型/创建外部对象。
4. 加入配置校验：缺少 Approval、Secret、Proxy、FQDN、Quota 或官方核验时 Connector 启动失败；Web 只能经 `/api/*`。
5. 编写部署和回滚 Runbook、证据模板及脱敏日志规则；对每个资源记录 Owner、版本、分类和清理日期。

## 验证命令与证据
在 Repo 运行最小相关测试：
```powershell
npm ci
python -m pytest tests\contract tests\integration\sit -k "health or environment"
python -m pytest tests\security\sit -k "secret or isolation"
```
通过受保护 `remote-sit` Pipeline 运行 readiness、资源隔离和配置负向检查。保存 RC manifest/hash、部署日志、health 响应、网络/身份/资源隔离报告和清理计划；真实凭据只引用 Secret Reference。

## AI 质量 Checkpoint
执行并记录 `P4-CP05`，结果只能为 `PASS`、`FAIL` 或 `BLOCKED`。PASS 需要硬指标无回归、软评分下降不超过 0.2/4、Critical/High 为 0、真实渠道门禁全通过；Tech Lead、QA Lead、Security 人类签字。AI 自评不能批准；失败按证据定位到 RC、配置或环境节点返工并生成新 RC，不收集或请求 Chain-of-Thought。

## 失败与阻断处理
任何门禁缺失、远端不可达、Secret/账户未批准、测试失败或健康检查副作用都标 `BLOCKED`/`FAIL` 并附日志链接、时间、commit 和责任人。不得扩大权限、关闭 TLS/审批/审计、静默 fallback 或将 Mock 标成真实成功；保留用户改动，修复先加失败测试再做 surgical diff。

## 完成响应格式
用中文报告：`状态: PASS|FAIL|BLOCKED`；变更文件；命令及结果；`P4-CP05` 结果与人类 Owner；Evidence 引用；剩余风险/阻断；以及是否满足 Subphase 02 前置条件。无证据不得声称完成。
