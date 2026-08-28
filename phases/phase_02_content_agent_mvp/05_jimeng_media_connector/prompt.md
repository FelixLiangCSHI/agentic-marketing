# Coding Agent Prompt — Phase 02 / Subphase 05

## 给 Coding Agent 的指令

按照父计划中的 `config/jimeng.yaml` 模板实现官方企业即梦 Connector、异步 Job、轮询、对象存储和确定性 Mock。禁止 Cookie、逆向接口或第三方代理。

## 必须先读

1. [Phase 02 总计划及即梦配置模板](../../phase_02_content_agent_mvp.md)
2. [前序 Prompt](../04_deepseek_connector/prompt.md)。
3. Connector SDK、Queue/Object Store、DLP/Malware Scan Hook。
4. 真实模式前核验采购批准的官方 Volcengine/BytePlus 租户文档。

## 执行位置与权限

- 模式：`hybrid-dev`。
- 所有代码、测试、配置和 fixture 变更必须在 GitHub 分支/Worktree 中完成并经 PR 审查。
- Repo/普通 CI：确定性异步 Mock，不访问外部 API。
- DEV：受保护 Pipeline + 企业自托管 Runner + Proxy/FQDN + Secret Reference。
- 不读取 AK/SK/Token，不上传未经批准的产品、员工或未发布素材。

## 前置条件

- Queue/Object Store/Secret Contract 可用。
- 官方供应商、区域、租户、认证、图片模型、数据保留/训练政策已确认；否则真实路径 `BLOCKED`。

## 目标

使 `GenerateMedia` 可靠创建、恢复、轮询、验证并保存媒体资产，同时控制安全、成本和重复任务。

## Scope

包含 `connectors/jimeng/`、配置、Mock、异步 Worker、对象存储导入、技术/安全校验。

不包含第二媒体供应商、视频能力假设或内容最终批准。

## 实施任务

1. 实现统一 Connector 接口和 vendor-specific auth Adapter。
2. 默认 `enabled:false/mode:mock`；中国区/国际区 endpoint、Credential、Quota 不混用。
3. 创建任务保存 provider job ID、request hash、idempotency key。
4. 使用持久 Queue 轮询；Worker 重启后恢复；不启用公网 webhook。
5. 创建超时先按 job/idempotency 对账，不重复创建。
6. 下载后验证 TLS、MIME、大小、hash、Malware Scan；转存 Object Store。
7. Generated/Approved 路径分离，任何修改创建新版本。
8. 限制并发、每 Run 资产数、每日费用；80% 告警、100% 停止。
9. Mock 覆盖完成、失败、取消、429、超时已创建、临时 URL 过期、非法 MIME 和 Malware。

## 验证命令与证据

- Config/Contract/Async Worker Unit Test。
- 100 次重复创建、restart/resume、URL expiry、object version Test。
- DLP/MIME/Malware/Cost Security Test。
- DEV 官方 API Smoke（获批时）。
- Evidence：job IDs、request/artifact hashes、poll trace、scan/cost report。

## AI 质量 Checkpoint

执行 `P2-CP03`：

- DLP/Malware/禁用视觉命中进入批准资产数 0。
- 技术规格通过率 100%，重复 Job 0。
- 相关性和品牌软评分 >= 3.4/4。
- Marketing + Security 复核；AI 自评不能 `PASS`。真实供应商未确认时为 `BLOCKED`，不保存 Chain-of-Thought。

## 失败与阻断处理

- Cookie/非官方 API：立即 `FAIL`，不得继续。
- 模型不支持图片：`BLOCKED` 并回报范围决策，不伪装能力。
- 未知 Job：停止创建，进入人工对账/DLQ。

## 完成响应格式

```text
Status:
Changed files:
Tenant/model/config:
Commands/results:
P2-CP03:
Job/artifact evidence:
Costs/risks/blockers:
Ready for Subphase 06:
```
