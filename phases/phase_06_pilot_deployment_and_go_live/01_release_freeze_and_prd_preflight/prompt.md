# Coding Agent Prompt — Phase 06 / Subphase 01

## 给 Coding Agent 的指令
统一纪律：采用 TDD，先写失败测试再做 surgical 最小变更；禁止 broad catch、静默 fallback；保留无关用户变更。
冻结 UAT 签字 RC，审查 PRD Release Manifest 并运行只读 Preflight；不得执行生产写。执行模式：`remote-prd`。代码、测试、IaC、脚本、Runbook 和脱敏 fixture 只在 GitHub 隔离 branch/worktree 修改；PRD 远端只经受保护 Pipeline/Environment Approval/企业自托管 Runner，Operations/Security 人类拥有执行和 Go/No-Go。

## 必须先读
- `../../phase_06_pilot_deployment_and_go_live.md`
- `../../phase_05_uat_security_performance_and_stabilization.md`
- 父文档第 3、4、5、6.1–6.2、7、8、9、12–14 节。

## 执行位置与权限
检查/创建 `infra/prd/{deployment,config,network,observability,backup}`、`scripts/release/{verify_config,preflight}.py`、`docs/release/go-no-go.md`。Coding Agent 可准备/审查 Artifact，但不得直接 SSH/RDP、手工 SQL、服务器热修、真实 Secret 入 GitHub、读取 Secret、生产写或生产访问；部署由人类 Operations/Security 执行。

## 前置条件
P5-CP01..06 全部 PASS；六类人类签字、SHA/digest/SBOM/Migration、PRD Credential/Quota/FQDN/Legal/Security 审批、HA/PITR/Runbook 均有证据。缺一项输出 BLOCKED。

## 目标
验证 PRD Web/API/Worker x2、PostgreSQL HA、网络/隔离/Secret/Queue/Object/Observability/SSO 配置与 UAT 基线一致，生成不可变 Release Manifest 和只读 Preflight 证据。

## Scope
- 只读配置、版本、拓扑、网络、身份、数据保护和 Golden Contract Smoke。
- 不 Migration、不注入 Credential、不 Pilot、不生产写。

## 实施任务
1. 固定签名 Tag、镜像 digest、SBOM、Migration、Domain Contract、Prompt/Model/Policy/Skill/Workflow/Connector 版本、非敏感 config hash、Feature/Kill Switch 默认值。
2. 用 `verify_config.py` 检查 PRD namespace/SSO/DB/Queue/DLQ/Bucket/KMS/Secret/Proxy/FQDN/HA/Observability/Alert 与非生产完全隔离。
3. 让 `preflight.py` 只读检查 DNS/TLS/Gateway、双节点、DB HA/TLS/备份/PITR/Role、Worker Identity、Object 生命周期/Malware、Secret Policy、SSO URI 和告警。
4. 所有失败非零退出且不修改任何资源；保留配置 hash、版本、审批和状态证据。

## 验证命令与证据
```powershell
python scripts\release\verify_config.py --environment prd
python scripts\release\preflight.py --environment prd --read-only
```
通过 `remote-prd` 受保护 Job 运行；保存 Manifest、Config hash、Preflight 输出、拓扑/隔离/审批 Evidence。没有真实 PRD 证据不得标 PASS。

## AI 质量 Checkpoint
执行 `P6-CP01`，结果只能 `PASS`/`FAIL`/`BLOCKED`。PASS：未批准版本 0、Contract/Golden Smoke 100%、测试/PRD 数据串用 0；Tech Lead、Security、QA 人类批准。AI 自评不能签发 PASS/Go-Live，不请求 Chain-of-Thought。

## 失败与阻断处理
Preflight 任一失败、凭据/审批/监控缺失即 BLOCKED；版本漂移或隔离失败为 FAIL，阻断部署或关闭 Provider。不得用 UAT Credential、默认值、Mock、手工修改或扩大权限补齐。

## 完成响应格式
报告状态、变更文件、命令/结果、`P6-CP01` 人类结果、Evidence 引用、风险/阻断和 Subphase 02 就绪性。
