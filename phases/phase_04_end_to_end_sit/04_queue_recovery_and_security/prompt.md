# Coding Agent Prompt — Phase 04 / Subphase 04

## 给 Coding Agent 的指令
统一纪律：采用 TDD，先写失败测试再做 surgical 最小变更；禁止 broad catch、静默 fallback；保留无关用户变更。
验证 Queue/DLQ/Worker 恢复、取消、重复投递及安全集成边界，保持幂等、fail closed 和完整审计。执行模式：`remote-sit`。代码、测试、IaC、脚本、Runbook、脱敏 fixture 只在 GitHub 隔离 branch/worktree 修改；故障和安全演练只能经受保护 Pipeline/Environment Approval/企业自托管 Runner。

## 必须先读
- `../../phase_04_end_to_end_sit.md`
- `../03_approval_rework_and_connector_failures/prompt.md`
- 父文档第 6.7、6.9、8.2、8.3、10、13、14 节。

## 执行位置与权限
检查/创建 `tests/workflow/sit`、`tests/recovery/sit`、`tests/security/sit`、`tests/fixtures/sit`、`docs/runbooks/sit-recovery.md`。不得 Coding Agent 直接 SSH/RDP、手工 SQL、服务器热修、真实 Secret 入 GitHub、访问生产或读取真实 Secret；不修改父 Markdown。

## 前置条件
Subphase 03 故障映射 PASS；SIT 三类 Queue、DLQ、Worker 控制节点、恶意输入 fixture、角色身份和隔离证据已批准。缺失远端恢复/安全环境时 BLOCKED，不以 Mock 代替 live evidence。

## 目标
证明重复消息、Tool 前后/Checkpoint 前后崩溃、lease 过期、Poison Message、DLQ Replay、各阶段取消和 Metrics watermark 恢复均不产生重复副作用；Prompt Injection、SSRF、越权、DLP、Secret 泄漏和 Audit 故障均受控。

## Scope
- 覆盖 Content/Campaign/Connector Queue、DLQ、Worker、租约、取消、恢复和安全信任边界。
- 不覆盖指标深度报告、50 并发和 UAT Red Team。

## 实施任务
1. 注入三类消息重复投递、Worker 在 Tool/Checkpoint 前后退出、lease 过期重领、最大重试入 DLQ、相同 key Replay，并断言合法状态单调性。
2. 在队列等待、执行、审批等待和 Metrics 轮询取消；保存原 Run/Trace/原因，取消后不得启动新副作用。
3. 注入用户 Prompt、附件、Product 文本、Tool Result 中的指令；验证数据/指令隔离、Schema/PreToolUse 重验和模型不可改变 Role/Approval/Policy/Hash/Tool Level。
4. 验证恶意 URL、SSRF、路径遍历、伪造 MIME、跨 Agent/Tenant/环境、前端伪造角色、无审批 L3/L4、任意 URL/Shell/SQL 和 Audit 不可用均拒绝；Audit 失败时高风险 Tool fail closed。
5. 扫描 Log、Trace、错误、Object Metadata/UI 的 Secret/DLP 泄漏，保存 Denied Trace 与脱敏报告。

## 验证命令与证据
```powershell
python -m pytest tests\workflow\sit tests\recovery\sit
python -m pytest tests\security\sit
python -m pytest tests\integration\sit -k "cancel or idempot"
```
经 `remote-sit` 执行受控崩溃/攻击演练；证据含状态 Journal、lease、DLQ/Replay、side-effect count、Denied Trace、Audit、DLP/Secret scan 和 Runbook 链接。

## AI 质量 Checkpoint
执行 `P4-CP02`、`P4-CP04`，结果只能 `PASS`/`FAIL`/`BLOCKED`。PASS：错误分类 100%、重复副作用 0、恢复状态一致 100%、Critical 场景与 Trace/Audit 完整率 100%、软评分至少 3.4/4；QA、SRE、Security、业务 Reviewer 人类确认。AI 不得自签，禁止请求 Chain-of-Thought。

## 失败与阻断处理
真实故障注入、身份、日志或远端权限缺失为 BLOCKED；任何跨域成功、Secret 泄漏、重放副作用、非法状态回退或 Audit fail-open 为 FAIL。按证据返回 Queue/Worker/Policy/Authorization 节点；不得删除证据、扩大权限、静默 fallback 或整段盲重跑。

## 完成响应格式
报告状态、变更文件、命令/结果、`P4-CP02`/`P4-CP04` 人类结果、Evidence 引用、风险/阻断和 Subphase 05 就绪性。
