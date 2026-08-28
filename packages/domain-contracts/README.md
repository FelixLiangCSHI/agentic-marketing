# domain-contracts — 跨语言 v1 Domain Contract

`schemas/` 为单一事实来源（JSON Schema draft-07）。Python（Pydantic，
`apps/api/src/dmt_api/contracts.py`）与 TypeScript（Ajv，`src/validate.ts`）
必须对 `fixtures/` 下同一套 Golden/Invalid fixtures 产生 100% 一致的验证结果。

## 契约清单（v1）

- `run.v1.schema.json`
- `run-event.v1.schema.json`
- `task.v1.schema.json`
- `approval.v1.schema.json`
- `tool-call.v1.schema.json`
- `approved-content-package.v1.schema.json`
- `activation-request.v1.schema.json`
- `connector-error.v1.schema.json`

## 契约规则

- `schema_version` 必填且为 `"1.0"`。
- 状态一律使用受限枚举；禁止自由文本状态。
- 未知字段一律拒绝（`additionalProperties: false` / `extra="forbid"`）。
- ID、时间戳、哈希、URI、货币等使用明确格式（正则双端一致）。
- 新增字段默认向后兼容；删除、改名或语义改变必须升级主版本（v2）。

## 验证入口

- TypeScript：`npm test`（`src/tests/domain-contracts.test.ts`）
- Python：`npm run api:test`（`apps/api/tests/test_contract_fixtures.py`）

现有 `src/domain/` 类型不迁移；新代码经由兼容 Adapter
`src/domain/contracts.ts` 消费本包。
