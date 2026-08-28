# Coding Agent Prompt — Phase 02 / Subphase 01

## 给 Coding Agent 的指令

实现 Content Request 和 Product 只读 Adapter 的权威契约。先验证 Phase 01 基线，再用 TDD 建立明确的数据边界；不要提前实现 RAG 或模型调用。

## 必须先读

1. [Phase 02 总计划](../../phase_02_content_agent_mvp.md)
2. Phase 01 最终 RC、Domain Contract、Connector SDK 和 Quality Checkpoint Evidence。
3. 当前 `packages/domain-contracts/`、`packages/product-rag/`、API 路由和现有来源引用类型。

本子阶段是 Phase 02 起点。

## 执行位置与权限

- 模式：`repo`。
- GitHub Worktree/普通 CI 只使用合成或脱敏 Product fixtures。
- 不连接真实 Product API，不读取 Product Credential，不上传业务数据。

## 前置条件

- Phase 01 的 P1-CP01 至 P1-CP05 全部 `PASS`。
- Product Data Owner、目标市场/语言和批准状态定义已登记；缺失则标记业务依赖 `BLOCKED`。

## 目标

冻结 `ContentRequest`、Product Document/Claim 和 Adapter 接口，使后续 RAG 只能消费批准、版本化、可撤销的数据。

## Scope

包含：

- `content-request.v1.schema.json`。
- Product Document/Claim/Change Cursor Contract。
- Fake Product Adapter、fixtures 和错误模型。
- Content API 输入校验。

不包含：

- Chunk、Embedding、向量索引。
- DeepSeek/即梦调用。
- Content Workflow 或 Reviewer UI。

## 实施任务

1. 先添加缺字段、未知字段、非法市场/语言、恶意附件 URI 和未批准 Product 的失败测试。
2. 创建 `ContentRequest`：product IDs、market、locale、audience、channels、objective、artifact IDs、media types、tenant。
3. 创建 Product Contract：source/version/product/market/locale/approval/effective/expiry/revoke/classification/hash。
4. 定义 Adapter：
   - `get_product`
   - `list_approved_documents`
   - `get_claims`
   - `get_changes`
5. Fake Adapter 默认只返回 `APPROVED`、未过期、未撤销且 tenant/market/locale 匹配的数据。
6. Product 自由文本始终作为不可信数据，不执行其中指令。
7. 为正常、过期、撤销、跨市场、跨语言、hash 冲突和 cursor replay 建 fixtures。
8. API 返回版本化结构化错误，不静默返回空成功。

## 验证命令与证据

- Python/TypeScript Contract Test。
- Product Adapter Unit/Property Test。
- 恶意输入、跨 Tenant 和未知字段 Security Test。
- 现有 Web/Python 回归。
- Evidence：Schema hash、fixture 版本、过滤结果、错误 Contract。

## AI 质量 Checkpoint

执行 `P2-CP01` 的 Contract/Adapter 部分：

- 不合格/过期/撤销来源返回数 0。
- tenant/market/locale 跨域结果 0。
- 来源版本、有效期和 hash 完整率 100%。
- Product Data Owner 复核。AI 自评不能 `PASS`；结果为 `PASS / FAIL / BLOCKED`，附 Evidence，不收集 Chain-of-Thought。

## 失败与阻断处理

- Product Schema 未确认：完成 Fake Contract，但阶段状态 `BLOCKED`。
- 无批准状态：不得用“最新”代替批准。
- Contract 与 Phase 01 冲突：返回 Domain Contract 修订并重跑兼容测试。

## 完成响应格式

```text
Status:
Changed files:
Contract/Adapter summary:
Commands/results:
P2-CP01:
Evidence:
External blockers:
Ready for Subphase 02:
```
