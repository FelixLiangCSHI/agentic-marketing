# Phase 02 / Subphase 01 — Content Contract & Product Adapter 证据记录

> 记录日期：2026-08-28（UTC）
> 执行模式：`repo`；仅合成/脱敏 fixtures，无真实 Product API、Credential 或业务数据。
> 依据：git 历史中的 Phase 02 总控文档（blob `dd3c002…`）与 Subphase 01 Prompt（blob `8c2545c…`）；`phases/` 目录按规则不恢复。

## 1. 交付物

| 交付物 | 位置 |
|---|---|
| `content-request.v1` Schema | `packages/domain-contracts/schemas/content-request.v1.schema.json` |
| `product-document.v1` Schema | `packages/domain-contracts/schemas/product-document.v1.schema.json` |
| `product-claim.v1` Schema | `packages/domain-contracts/schemas/product-claim.v1.schema.json` |
| `product-change.v1` Schema（Change Cursor 事件） | `packages/domain-contracts/schemas/product-change.v1.schema.json` |
| Golden/Invalid fixtures（双端共享） | `packages/domain-contracts/fixtures/{golden,invalid}/` |
| TS 注册与类型 | `packages/domain-contracts/src/{types,validate}.ts` |
| Python 镜像模型 | `apps/api/src/dmt_api/contracts.py` |
| 只读 Adapter 接口（get_product / list_approved_documents / get_claims / get_changes） | `packages/product-rag/src/product_rag/adapter.py` |
| Fake Product Adapter + 类型化错误模型 | `packages/product-rag/src/product_rag/{fake_adapter,errors}.py` |
| 合成 Product fixtures（正常/过期/撤销/跨市场/跨语言/跨 Tenant/Draft/注入文本） | `packages/product-rag/fixtures/` |
| Content API 输入校验（不静默返回空成功） | `apps/api/src/dmt_api/routes/content.py` |
| CI 门禁 | `.github/workflows/ci.yml`（新增 `product-rag` job）；`package.json`（`productrag:test`/`productrag:typecheck`） |

## 2. Schema Hash（冻结基线）

| 契约 | sha256 |
|---|---|
| content-request.v1 | `11cfeefb4e73c19957416d1ca4b3bddcb9b169f8fc727c2d4800ea5bded68d19` |
| product-document.v1 | `21aa6afb32ec2bad88a63ba6550ad638ef660424745b0d1445160d1e02f6c6e7` |
| product-claim.v1 | `37fcd9c0f711a98f3df19f9c9b518793dcf49cc94c3029fd53b05b7637b38179` |
| product-change.v1 | `a6da13bbd6669970e4ff8cdcb33bc5c7e8070e25fe8647ae129f69ed63915d4d` |

## 3. 命令与结果

| 命令 | 结果 |
|---|---|
| `npx tsx --test src/tests/domain-contracts.test.ts` | PASS（27/27，含 4 个新契约的 golden/invalid） |
| `cd apps/api && python -m pytest` | PASS（97 passed, 48 skipped=DB 集成需 Postgres） |
| `cd apps/api && python -m mypy` | PASS（strict） |
| `cd packages/product-rag && python -m pytest` | PASS（31/31） |
| `cd packages/product-rag && python -m mypy` | PASS（strict） |
| `cd packages/harness-core && python -m pytest` | PASS（45/45，回归） |
| `npm test` / `npm run lint` / `npm run typecheck` / `npm run build` | PASS（回归） |
| `python scripts/check_no_secrets.py` | PASS（clean） |

## 4. P2-CP01（Contract/Adapter 部分）硬门结果

| 硬门 | 结果 | 证据 |
|---|---|---|
| 不合格/过期/撤销来源返回数 = 0 | 满足 | `tests/test_fake_adapter.py::TestDefaultFilters`（DRAFT/expired/revoked 均被过滤，含 as_of 边界） |
| tenant/market/locale 跨域结果 = 0 | 满足 | `TestCrossBoundaryIsolation`（跨 tenant/市场/语言/变更流全部隔离） |
| 来源版本、有效期和 hash 完整率 = 100% | 满足 | 契约必填字段 + `test_every_result_has_version_validity_and_hash`；hash 冲突在装载时被 `ProductIntegrityError` 拒绝 |
| 自由文本按不可信数据处理 | 满足 | 注入文本原样作为数据返回（frozen model），Adapter 无写方法；API 侧 Prompt 注入文本仅形状校验 |
| Cursor replay 确定性 | 满足 | `TestChangeCursorReplay`（同 cursor 重放同页；未知 cursor 类型化报错） |
| 不静默返回空成功 | 满足 | 未知 Product/版本/cursor → 类型化错误；合法 ContentRequest → 版本化 `not_implemented`（501），非伪造成功 |

**P2-CP01 状态：`BLOCKED`（非 FAIL）**

- AI 自评不能签发 `PASS`；需 Product Data Owner 复核本记录与 fixtures。
- 真实 Product Schema/批准状态定义未确认（Phase 01 B-01 仍阻断），本子阶段按规则以 Fake Contract 完成，阶段状态标记 `BLOCKED` 直至业务确认。

## 5. 外部阻断项（沿用 docs/phase01/blocked.md）

- B-01：Product Data Owner/Schema/批准状态未确认 → 本契约冻结为 Fake 基线，真实 RAG 验收保持阻断。
- B-09：真实 Medical Reviewer 未指定（影响后续 Subphase，不影响本子阶段交付）。
- 真实 Credential 不进仓库/CI：所有能力保持 `mode: mock`。

## 6. Ready for Subphase 02

代码与测试就绪：Subphase 02（批准 RAG 与引用）可基于本契约启动；`ApprovedContentPackage` 相关阶段退出仍受 P2-CP01 人工复核与 B-01 解除约束。
