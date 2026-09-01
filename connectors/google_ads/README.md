# Google Ads Connector (Phase 03 / Subphase 04)

Mock/contract-first Google Ads connector on the shared
[`connector-sdk`](../../packages/connector-sdk) protocol. **This repository
ships only the mock path** — real Google Ads API calls (Developer Token,
OAuth refresh, test-account mutates) run exclusively in protected DEV/SIT
jobs and remain **BLOCKED** until the Developer Token, Cloud Project, test
Manager/Customer accounts, approved quota and official-doc verification
are recorded.

## Layout

| Path | Purpose |
|---|---|
| `src/google_ads_connector/config.py` | Strict loader for `config/google_ads.yaml`: reference-only credentials (Developer Token / client secret / refresh token must be `secretref://`), official endpoint lock, GAQL/`GoogleAdsService` lock, Service-Account⇔approval consistency gate, mode-readiness gate. |
| `src/google_ads_connector/auth.py` | OAuth-by-default credential minting with masked `SecretValue` handles; the Service Account branch fails closed without a recorded enterprise-ownership approval; `DEVELOPER_TOKEN_INVALID` is non-retryable. |
| `src/google_ads_connector/mappers.py` | Proposal → minimal verified mutate request. Customer/login-customer IDs stay `config://` references; unverified objectives raise `verification_required`; request hash for audit binding. |
| `src/google_ads_connector/metrics.py` | GAQL reads (Search/SearchStream shape): raw provider fields preserved verbatim (micros stay int64 strings, missing stays missing), page-token pagination, per-page response hash, GAQL query text retained. |
| `src/google_ads_connector/connector.py` | `GoogleAdsConnector` + `MockGoogleAdsTransport`: approval/input-hash/idempotency gates, duplicate delivery ⇒ one object, 429/RESOURCE_EXHAUSTED with Retry-After, timeout-after-create ⇒ `UNKNOWN` + reconcile-before-retry, partial mutate stops writes and records created IDs, interrupted pagination resumes from the last page token. |
| `fixtures/` | Deterministic synthetic fixtures (success pages + fault scenarios). |

## Config

The authoritative config is [`config/google_ads.yaml`](../../config/google_ads.yaml)
(`enabled: false`, `mode: mock`). Notable gates:

- `auth.developer_token_ref`, `oauth_client_secret_ref`, `refresh_token_ref`
  must be `secretref://` Secret Manager references — literals, `env://` and
  `config://` are rejected for true secrets.
- `auth.use_service_account` may only be `true` together with
  `auth.method: service_account_approved`; at runtime the adapter also
  requires a recorded approval with `approved` **and**
  `enterprise_owned_account` both true. OAuth is the default.
- `account.customer_id_ref` / `login_customer_id_ref` are references;
  `manager_account_required` / `test_account_required` are locked `true`.
- `query` is locked to `GoogleAdsService` + `GAQL` (`Search`/`SearchStream`);
  no invented reporting API.
- `sandbox`/`live` require `endpoint.verification: verified` and
  `enabled: true` (`require_ready_for_mode()`), which stay unset here.

## Running the gates

```bash
npm run googleads:test        # pytest (58 tests)
npm run googleads:typecheck   # mypy --strict (src)
cd connectors/google_ads && python3 -m mypy tests
```
