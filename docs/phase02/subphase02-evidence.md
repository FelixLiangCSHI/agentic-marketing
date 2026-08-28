# Phase 02 / Subphase 02 — 批准数据版本化 RAG 与引用 证据记录

> 记录日期：2026-08-28（UTC）
> 执行模式：`repo`；仅合成 fixtures 与确定性 Fake Embedding，无真实 Embedding API、Knowledge Base 或 Credential。
> 依据：git 历史中的 Phase 02 总控文档（blob `dd3c002…`）与 Subphase 02 Prompt（blob `f77681a…`）；`phases/` 目录按规则不恢复。

## 1. 交付物

| 交付物 | 位置 |
|---|---|
| 确定性分块（精确字符区间、句界切分、chunk hash） | `packages/product-rag/src/product_rag/chunking.py` |
| Citation 冻结模型（来源/版本/区间/有效期/双 hash，仅索引层可构造） | `packages/product-rag/src/product_rag/citations.py` |
| Embedding 边界（Protocol + 确定性 FakeEmbeddingProvider，向量绑定 provider/model/deployment/dimension） | `packages/product-rag/src/product_rag/embedding.py` |
| 版本化索引 + **预留 KnowledgeBaseIndex 接口**（本地 InMemory 实现；后续 MIDEA KB 实现同一 Protocol） | `packages/product-rag/src/product_rag/index.py` |
| **MIDEA Knowledge Base 预留适配器**（占位实现；未配置/未批准即抛类型化错误，禁止静默回退） | `packages/product-rag/src/product_rag/midea.py` |
| MIDEA KB 配置模板（`enabled: false` / `mode: mock`，仅 Secret Reference env 名） | `config/knowledge-base.yaml` |
| 摄取管道（批准/范围/hash 校验、拒绝记录、变更流撤销清除、审计报告） | `packages/product-rag/src/product_rag/ingestion.py` |
| 检索层（强制 tenant/product/market/locale/as_of 过滤；Citation 仅由索引条目构造） | `packages/product-rag/src/product_rag/retrieval.py` |
| 新增类型化错误（IngestionRejected/IndexVersionMismatch/MissingRetrievalFilter/KnowledgeBaseNotConfigured） | `packages/product-rag/src/product_rag/errors.py` |
| RAG 测试（24 项新增） | `packages/product-rag/tests/test_rag.py` |
| Golden Recall@k 评测（`rag-golden-queries-v1`，Recall@5 ≥ 0.95） | `packages/product-rag/tests/test_rag_eval.py` |

## 2. 版本记录

| 项 | 值 |
|---|---|
| Embedding 空间 | provider=`fake`, model=`feature-hash-bow-v1`, deployment=`local`, dimension=256 |
| 索引版本规则 | `make_index_version()` = `{provider}_{model}_{deployment}_d{dim}_g{generation}`；模型升级/重建产生新版本，禁止混用（`IndexVersionMismatchError`） |
| 默认索引版本 | `fake_feature-hash-bow-v1_local_d256_g1` |
| Golden 数据集 | `rag-golden-queries-v1`（6 条查询，绑定合成 fixtures；不允许为提升 Recall 修改答案） |
| Recall@5 | 1.00（阈值 0.95，PASS——仅验证管道机制，非真实 Embedding 质量验收） |

## 3. 命令与结果

| 命令 | 结果 |
|---|---|
| `cd packages/product-rag && python -m pytest` | PASS（55/55：31 Subphase 01 回归 + 24 新增） |
| `cd packages/product-rag && python -m mypy` | PASS（strict，src 与 tests 均通过） |
| `cd apps/api && python -m pytest && python -m mypy` | PASS（回归） |
| `cd packages/harness-core && python -m pytest` | PASS（45/45 回归） |
| `cd packages/infra-core && python -m pytest` | PASS（43/43 回归） |
| `python -m pytest evals` / `python -m pytest integration` | PASS（回归） |
| `npm test` / `npm run lint` / `npm run typecheck` / `npm run build` | PASS（回归） |
| `python scripts/check_no_secrets.py` | PASS（clean） |

## 4. P2-CP01（RAG 部分）硬门结果

| 硬门 | 结果 | 证据 |
|---|---|---|
| 不合格/过期/撤销来源可召回数 = 0 | 满足 | Adapter 过滤 + 摄取二次校验（`test_only_valid_sources_are_ingested…`）；检索按 `as_of` 复核有效期（`test_expired_entries_not_recallable_at_later_as_of`） |
| Content hash 不匹配 → 记录性拒绝，非静默 | 满足 | `doc-alpha-injection` 伪 hash 被拒并记入 `IngestionReport`（reason=`content_hash_mismatch`） |
| 撤销后立即不可召回（Critical） | 满足 | `TestRevocationPurge`：`delete_by_source` 后召回 0；变更流 `chg-0003`/`chg-0004` REVOKED 事件驱动清除 |
| 引用位置/hash 完整率 = 100% | 满足 | Citation 必填字段 + `test_all_citations_are_complete_and_verifiable`（char 区间重建原文、chunk hash 复验） |
| tenant/market/locale 跨域检索 = 0 | 满足 | `RetrievalFilters` 全字段强制 + `test_cross_scope_results_are_zero`；查询文本不可扩权（`test_query_text_cannot_widen_scope`） |
| 索引不得混用 Embedding 空间/版本 | 满足 | `TestIndexVersioning`（空间/版本/维度不匹配均抛 `IndexVersionMismatchError`；Retriever 侧同样校验） |
| 模型不生成引用 | 满足 | Citation 仅在 `retrieval.py` 由 IndexEntry 构造；`RetrievedPassage` frozen |
| 注入文本仅作数据 | 满足 | `test_injected_source_text_is_returned_as_data_with_citation`（原样返回+引用，不改变过滤） |
| Golden Source Recall@k ≥ 95% | 满足（Fake Embedding 机制验证） | `test_rag_eval.py`：Recall@5 = 1.00，数据集 `rag-golden-queries-v1` |

**P2-CP01 状态：`BLOCKED`（非 FAIL）**

- AI 自评不能签发 `PASS`；需 Product Data Owner 复核本记录、fixtures 与 golden 数据集。
- 真实 Embedding 质量验收保持阻断（B-03/B-05：Credential 不进仓库/CI；无 DEV 远程环境证据）。
- 真实 Product Schema 未确认（B-01），召回/引用验收基于 Fake 契约基线。

## 5. MIDEA Knowledge Base 预留接口说明

- 集成点 = `KnowledgeBaseIndex` Protocol（`index.py`）：Agent/Workflow 仅依赖该协议，不依赖具体后端。
- `MideaKnowledgeBaseIndex`（`midea.py`）为占位实现：`enabled: false`/`mode: mock` 或配置不完整时抛 `KnowledgeBaseNotConfiguredError`，任何路径不静默回退到假成功；配置齐备也保持类型化阻断，直到官方 API 获批并在受保护流水线实现。
- `config/knowledge-base.yaml` 仅含 Secret Reference env 名（`MIDEA_KB_ENDPOINT` / `MIDEA_KB_API_KEY_SECRET_REF` / `MIDEA_KB_COLLECTION` / `MIDEA_KB_ALLOWED_FQDNS`），无任何真实值。

## 6. 外部阻断项（沿用 docs/phase01/blocked.md）

- B-01：Product Data Owner/Schema 未确认 → RAG 验收停留在 Fake 基线。
- B-03/B-05：真实 Embedding/外部 KB Credential 不进仓库/CI → 真实召回质量验收阻断。
- MIDEA KB 官方 API（endpoint/auth/数据驻留）未获批 → 仅保留接口与配置模板。

## 7. Ready for Subphase 03

RAG 摄取/索引/检索/引用与撤销清除机制就绪，Content 生成（Subphase 03）可基于 `Retriever` + `Citation` 启动；阶段退出仍受 P2-CP01 人工复核与 B-01/B-03 解除约束。
