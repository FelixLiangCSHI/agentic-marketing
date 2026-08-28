# Coding Agent Prompt — Phase 04 / Subphase 02

## 给 Coding Agent 的指令
统一纪律：采用 TDD，先写失败测试再做 surgical 最小变更；禁止 broad catch、静默 fallback；保留无关用户变更。
在 SIT 中实现并验证 `SIT-E2E-001` Critical Happy Path，逐节点核对 Schema、状态、Journal、Policy、Approval、Trace、Audit、Object URI/hash 和外部 ID。执行模式：`remote-sit`。代码、测试、IaC、脚本、Runbook 和脱敏 fixture 只能在 GitHub 隔离 branch/worktree 修改；远端只经受保护 Pipeline/Environment Approval/企业自托管 Runner。

## 必须先读
- `../../phase_04_end_to_end_sit.md`
- `../01_sit_release_and_environment/prompt.md`
- 父文档第 6.4、7、8.1、8.3–8.5、9、10、13、14 节。

## 执行位置与权限
检查/创建 `tests/integration/sit/test_content_to_campaign.py`、`tests/fixtures/sit/{product,linkedin,google_ads}`、`evals/{content,compliance,campaign}/sit` 和对应 Runbook/Evidence 模板。真实双渠道测试只由受保护 SIT Job 执行；Coding Agent 不得 SSH/RDP、手工 SQL、服务器热修、将真实 Secret 写入 GitHub、接触真实 Secret 或生产。

## 前置条件
Subphase 01 的 RC、SIT health/isolation 证据 PASS；脱敏批准 Product、合成媒体、测试身份、硬预算及 LinkedIn/Google 测试账户已获批准。若真实账户、SSO 或远端环境缺失，输出 `BLOCKED`，不能以 Mock 替换。

## 目标
完成 Internal SSO→Content Request→批准 Product Facts→Copy/Media→Compliance→Medical/Marketing Approval→ApprovedContentPackage→双渠道 Draft/Dry-run→Campaign Approval→single-use Token→测试账户 Publish→Reconcile→Raw/Normalized Metrics→Report→Strategy Draft 全链路。

## Scope
- 只覆盖正常路径、双渠道 Contract、引用/hash 和报告边界。
- 不做拒绝返工、故障恢复、50 并发或生产写入。

## 实施任务
1. 固定 `SIT-CONT-01`、`SIT-CAMP-01/02` 脱敏 fixture，校验 tenant/product/market/locale/validity、Claim 来源 100% 和不可变媒体 hash。
2. 编写端到端测试及 pairwise 质量 fixture；断言每一步 Run/Task 状态合法、Approval 分离、审计字段完整。
3. 验证 LinkedIn 与 Google 产生不同合规草稿，Dry-run 后只消费哈希匹配 ApprovedContentPackage；写入带 idempotency key、external ID 和 Reconcile。
4. 验证 Raw Metrics 追加、Normalized Metrics 公式版本、分页/watermark 去重、报告追溯 Raw ID/response hash；Strategy 仅草稿。
5. 生成逐场景 Evidence Pack；失败先加可复现测试，再做最小修复并重新生成 RC。

## 验证命令与证据
```powershell
python -m pytest tests\integration\sit\test_content_to_campaign.py -m sit
python -m pytest tests\contract tests\workflow -k "content or campaign or metrics"
```
通过 `remote-sit` Pipeline 使用批准测试账户运行一次双渠道真实 E2E；保存脱敏 Run/Trace/Audit、Claim/Source/Approval/Hash、External ID、Reconcile、Raw/Report 和清理记录。真实路径缺失则证据为 `BLOCKED_EXTERNAL_DEPENDENCY`。

## AI 质量 Checkpoint
执行并记录 `P4-CP01`、`P4-CP04`，仅允许 `PASS`/`FAIL`/`BLOCKED`。PASS 阈值：Claim/引用/hash 100%、未批准内容进入 Campaign 0、Critical 场景 100%、Trace/Audit 100%、软解释评分至少 3.4/4；Medical、QA 和业务 Reviewer 人类确认。AI 自评不能批准，不请求/保存 Chain-of-Thought。

## 失败与阻断处理
遇到供应商权限、Quota、账户、SSO 或证据缺失即 BLOCKED；遇到漂移、未审批写、重复对象、引用缺失、Strategy 写入或错误成功即 FAIL。按 Checkpoint 返回 Mapper/Contract/指定节点，禁止盲目重跑、放宽审批、静默 fallback、热修或保留敏感响应。

## 完成响应格式
报告状态、变更文件、命令/结果、`P4-CP01`/`P4-CP04` 结果及人类签字、Evidence 引用、风险/阻断和 Subphase 03 就绪性。
