# Coding Agent Prompt — Phase 02 / Subphase 02

## 给 Coding Agent 的指令

实现只摄取批准资料的版本化 RAG 和可验证引用。Repo 中完成确定性逻辑和 Fake Embedding；真实 Product/Embedding 只在受保护 DEV 环境验证。

## 必须先读

1. [Phase 02 总计划](../../phase_02_content_agent_mvp.md)
2. [前序 Prompt](../01_content_contract_and_product_adapter/prompt.md) 及 P2-CP01 Evidence。
3. Product Contract、Object Store、Secret/Config 和企业 Embedding 资料。

## 执行位置与权限

- 模式：`hybrid-dev`。
- Repo/普通 CI：Fake Product、Fake Embedding、合成 Golden Set。
- DEV：受保护 Pipeline + 自托管 Runner 连接脱敏 Product API、批准 Embedding 和索引服务。
- 不直接连接远端服务器，不把 Product 原文或 Credential 写入 GitHub。

## 前置条件

- Subphase 01 Repo 部分为 `PASS`。
- Embedding/pgvector 方案有 ADR；未批准时真实路径 `BLOCKED`。

## 目标

建立 ingestion、chunk、embedding、index、retrieval 和 citation，保证每个返回事实可定位到批准源版本。

## Scope

包含 `packages/product-rag/`、Fake/真实 Embedding Adapter、索引版本和 Retrieval Eval。

不包含内容生成、Compliance 或媒体。

## 实施任务

1. 先写过期/撤销/跨市场召回、索引混版、无来源结果和 Prompt Injection 测试。
2. 摄取前验证批准状态、tenant、市场、语言、有效期和 hash。
3. Chunk 保存 source/version、页/字符范围、市场、语言和有效期。
4. Embedding 保存 provider/model/deployment/dimension/index version。
5. Retrieval 强制 tenant/product/market/locale/approval/validity filter。
6. 返回片段、source/version/location/expiry/hash；不得让模型生成引用。
7. 撤销/过期事件使关联条目不可召回；模型升级创建新索引。
8. 建立 Golden queries 和 Recall@k 测量。
9. DEV 受保护 Job 验证真实接口、索引和 Trace；只回传脱敏统计/hash。

## 验证命令与证据

- Ingestion/Chunk/Filter/Citation Unit Test。
- Retrieval Golden/Adversarial Eval。
- Index rebuild/version/撤销 Integration Test。
- DEV Product/Embedding Contract Test。
- Evidence：dataset/index/model version、Recall@k、source hashes、隔离/撤销报告。

## AI 质量 Checkpoint

执行 `P2-CP01`：

- 不合格/过期/撤销来源 0。
- Citation location/hash 完整率 100%。
- Golden Source Recall@k >= 95%。
- 跨 Tenant/市场/语言结果 0。
- Product Data Owner 复核；AI 自评不可批准。无远端服务时为 `BLOCKED`，不以 Fake 替代，不保存 Chain-of-Thought。

## 失败与阻断处理

- Recall 不达标：只调整 chunk/retrieval/index，并记录对比，不修改 Golden 答案迎合输出。
- 真实 Embedding 未批准：保持 Fake，远端门禁 `BLOCKED`。
- 撤销资料仍可召回：Critical `FAIL`，停止下游生成。

## 完成响应格式

```text
Status:
Changed files:
Index/model/dataset versions:
Commands/eval results:
P2-CP01:
DEV evidence:
Risks/blockers:
Ready for Subphase 03:
```
