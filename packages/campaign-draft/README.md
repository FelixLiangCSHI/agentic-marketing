# campaign-draft — Campaign Proposal Draft（Phase 03 / Subphase 01）

确定性的 `CampaignProposal` Draft 构建器。只消费 **APPROVED、未过期、
hash 匹配且包含目标渠道变体** 的 `ApprovedContentPackage`（经由
`content_package.consumable` 消费门）；不调用任何渠道 API，不产生任何
外部副作用。

## 不变量

- 金额使用 `Decimal` → 整数最小货币单位；拒绝 float、NaN、负数、超精度
  和不支持的币种（见 `SUPPORTED_CURRENCIES`）。
- 相同输入 + 版本 + Fake Clock 产生相同 `input_hash` 与 `proposal_id`；
  任何绑定字段变化产生新 hash、新 id 和 `version + 1`。
- Draft 状态恒为 `DRAFT`；`SUPERSEDED`/`INVALIDATED` 是账本转换而非
  就地修改（模型 frozen）。
- 请求市场必须落在包批准的 market 内；排期必须落在包有效期内；
  timezone 必须是 IANA 时区。
- Proposal 不包含 Content Agent 私有 Context、Credential 或 Secret。

跨语言契约为 `packages/domain-contracts/schemas/campaign-proposal.v1.schema.json`，
Golden/Invalid fixtures 与 TypeScript（Ajv）/Python（Pydantic）双端共享。

## 验证

```bash
python3 -m pip install -e "packages/content-package" -e "packages/campaign-draft[dev]"
npm run campaigndraft:test
npm run campaigndraft:typecheck
npm run contract:test
```
