# Coding Agent Prompt — Phase 05 / Subphase 01

## 给 Coding Agent 的指令
统一纪律：采用 TDD，先写失败测试再做 surgical 最小变更；禁止 broad catch、静默 fallback；保留无关用户变更。
冻结通过 SIT 的 UAT RC，在独立 UAT 环境执行十个核心业务场景和真实角色审批。执行模式：`remote-uat`。代码、测试、IaC、脚本、Runbook 和脱敏 fixture 只能在 GitHub 隔离 branch/worktree 修改；远端只经受保护 Pipeline/Environment Approval/企业自托管 Runner。

## 必须先读
- `../../phase_05_uat_security_performance_and_stabilization.md`
- `../../phase_04_end_to_end_sit.md`
- 父文档第 2、3、4、5.1、5.2、6、8.1、9、10、13、14、15 节。

## 执行位置与权限
检查/创建 `tests/uat/{scenarios,fixtures,evidence}`、`evals/{content,compliance,campaign}/uat`、`docs/runbooks/uat-execution.md`、`docs/release/release-candidate.md`。业务审批在受控 UAT 远端由具名 Marketing/Medical/Campaign Owner 执行；Coding Agent 禁止直接 SSH/RDP、手工 SQL、服务器热修、真实 Secret 入 GitHub、生产访问或真实 Secret。

## 前置条件
SIT 退出全部 PASS；UAT 域名、独立 App/角色、脱敏 Product、专用账户、预算、Observability 和签字人已确认。缺 Reviewer、真实账户、远端环境或恢复证据则 BLOCKED，不以 Mock 晋级。

## 目标
冻结不可变 UAT RC，执行 UAT-BIZ-01..10：正常链路、Medical Reject/定点返工、预算重审批、过期/撤销、外部状态差异、指标报告和 Strategy 草稿。

## Scope
- 覆盖 Marketing、Medical、Operator/Approver、Auditor 角色与 Content/Campaign 业务场景。
- 不覆盖 Red Team、100/300 并发、PITR 或 Pilot。

## 实施任务
1. 记录 SHA、digest、Migration、Prompt/Model/Policy/Skill/Workflow/Connector/API 版本及 `mock/sandbox/live-disabled-in-uat` flags；禁止指向 PRD。
2. 为十场景创建脱敏 fixtures 和表单；验证 Request→有来源内容→分离审批→双渠道草稿→批准发布→对账→Raw/Normalized/Report→Strategy draft。
3. Medical Reject 必须保留规则/Claim/Source/Severity，定点重跑 Copy；预算改变 input_hash、旧 Token 失效并在重新批准前无外部写。
4. 过期/撤销 Product、Skill、Policy、Package、OAuth Token 停在正确状态并告警；外部后台差异只报告不覆盖。
5. 逐项收集人工决策、Reviewer 反馈、引用/hash、Trace/Audit 和缺陷链接。

## 验证命令与证据
```powershell
python -m pytest tests\contract tests\workflow
python -m pytest tests\uat tests\security\uat -k "biz or approval or report"
$env:DMT_ENV = "uat"; $env:DMT_BASE_URL = "https://digital-marketing-uat.carstream-int.com"; python -m pytest tests\uat -m uat
```
保存 UAT 表单、Artifacts、Checkpoint Results、审批/拒绝/返工 Journal、External ID/Reconcile 和脱敏签字 Evidence。

## AI 质量 Checkpoint
执行 `P5-CP01`，结果只能 `PASS`/`FAIL`/`BLOCKED`。PASS：核心场景 100%、Critical 逃逸 0、拒绝项闭环、软评分平均 ≥3.4/4 且单项 ≥3；Marketing 与 Medical 具名人类审核。AI 自评不能签字，不请求/存储 Chain-of-Thought。

## 失败与阻断处理
业务角色、账户、审批或环境缺失为 BLOCKED；事实/引用/Medical/审批/副作用失败为 FAIL。返回指定业务节点重新审批；先失败测试后最小修复，新 RC 全量回归，不扩大权限、不吞错、不用 Mock 替代 live evidence。

## 完成响应格式
报告状态、变更文件、命令/结果、`P5-CP01` 人类结果、Evidence 引用、剩余风险/阻断和 Subphase 02 就绪性。
