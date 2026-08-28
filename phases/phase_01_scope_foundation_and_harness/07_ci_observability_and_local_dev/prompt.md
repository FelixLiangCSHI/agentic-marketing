# Coding Agent Prompt — Phase 01 / Subphase 07

## 给 Coding Agent 的指令

建立本地开发栈、CI 门禁和可观测性，使每次 AI/人工变更都可重复验证、追踪和安全审查。

## 必须先读

1. [Phase 01 总计划](../../phase_01_scope_foundation_and_harness.md)
2. [前序 Prompt](../06_queue_storage_secrets_and_config/prompt.md)。
3. 当前 package/Python 脚本、所有测试入口、Trace/Audit Contract。

## 执行位置与权限

- 模式：`repo`。
- GitHub 普通 PR CI 无真实 Secret、无远端写权限。
- 本地栈只使用合成数据、Fake Identity 和模拟 Credential。
- 受保护部署 Workflow 只能定义，不在普通 PR 中执行 DEV/SIT/UAT/PRD。

## 前置条件

- Subphase 06 Repo Contract 为 `PASS`。
- CI Runner、镜像仓库和扫描工具使用公司已批准方案。

## 目标

提供可复现本地栈、Web/Python/Contract/Migration/Security/Eval CI 和最小 Dashboard/Alert。

## Scope

包含 `infra/local/`、CI Workflow、OpenTelemetry 字段、Dashboard/Alert 定义和开发文档。

不包含真实远端部署、业务 Agent 或性能压测。

## 实施任务

1. 为 CI 配置先创建失败验证，确认每个 Job 实际执行而非空脚本。
2. 本地栈提供 PostgreSQL 16、Queue Emulator、Object Store Emulator、Telemetry Collector、Fake IAM。
3. 每个 Worktree 使用独立端口、Compose Project、DB、Queue 和 Bucket Prefix。
4. CI Jobs：
   - Web install/test/lint/typecheck/build。
   - Python test/lint/typecheck。
   - 双语言 Contract。
   - Migration 往返。
   - Secret/dependency/image scan。
   - 最小 Content/Campaign Eval。
5. 定义统一 Trace 字段、Run/Tool/Queue/Cost 指标。
6. 定义 L3/L4、DLQ、Audit、费用、Worker heartbeat 告警。
7. 可选 code-review-graph 仅做影响面辅助，不替代测试。
8. 受保护 Environment Workflow 使用 OIDC/短期身份和人工 Approval，Fork 不得取得权限。

## 验证命令与证据

- 从干净 checkout 启动本地栈。
- 运行全部 CI 等价命令和一条故意失败的门禁验证。
- 验证日志/Trace 无 Secret，Dashboard 查询能关联 Run/Tool/Approval。
- 验证普通 PR 无远端 Credential。
- Evidence：CI run、local stack health、Trace sample、alert test、scan/SBOM。

## AI 质量 Checkpoint

执行 `P1-CP04`、`P1-CP05`：

- Checkpoint 结果仅允许 `PASS / FAIL / BLOCKED`；AI 自评不能批准。
- CI 必需 Job 执行率 100%，绕过/空成功 0。
- Critical Trace 字段完整率 100%，Secret 泄漏 0。
- AI 生成 CI/IaC PR 的 Critical/High Review Finding 0、无关文件 0。
- 独立 Reviewer + Tech Lead/SRE 复核；结果为 `PASS / FAIL / BLOCKED`，不收集 Chain-of-Thought。

## 失败与阻断处理

- 缺批准扫描工具：使用已有门禁或标 `BLOCKED`，不私自上传源码到第三方。
- CI 只能在本机成功：`FAIL`，从干净 Runner 修复。
- 发现真实 Secret：立即撤销并按 Incident 处理，不提交脱敏前日志。

## 完成响应格式

```text
Status:
Changed files/workflows:
Local stack result:
CI jobs/results:
P1-CP04/P1-CP05:
Evidence:
Risks/blockers:
Ready for Subphase 08:
```
