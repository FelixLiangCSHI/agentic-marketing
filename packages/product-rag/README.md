# product-rag

Phase 02 / Subphase 01：批准 Product 数据只读契约与 Adapter。

- 权威跨语言契约在 `packages/domain-contracts/schemas/`（`product-document.v1`、`product-claim.v1`、`product-change.v1`、`content-request.v1`）。
- 本包提供 Python 运行时模型、`ProductAdapter` 只读接口、类型化错误模型与 `FakeProductAdapter`。
- **不包含** Chunk / Embedding / 向量索引 / 模型调用（Subphase 02+）。
- 不连接真实 Product API，不读取 Product Credential；只使用 `fixtures/` 下的合成脱敏数据。
- 所有 Product 自由文本（`content`、`claim_text`）是不可信数据：只能作为数据传递，不得被解释为指令。

默认过滤规则（P2-CP01 硬门）：只返回 `APPROVED`、未过期、未撤销且 tenant/market/locale 完全匹配的记录。

```bash
python -m pip install -e ".[dev]"
python -m pytest
python -m mypy
```
