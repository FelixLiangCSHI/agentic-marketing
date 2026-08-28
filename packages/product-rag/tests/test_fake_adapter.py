"""Unit + security tests for the read-only FakeProductAdapter (P2-CP01).

Hard gates covered:
* unapproved / expired / revoked sources returned: must be 0;
* cross tenant/market/locale results: must be 0;
* source version, validity and hash completeness: 100%;
* free text is untrusted data — passed through verbatim, never executed;
* hash conflicts and invalid cursors raise typed errors (no fake success).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from product_rag import (
    FakeProductAdapter,
    FixtureValidationError,
    InvalidCursorError,
    ProductDocumentV1,
    ProductIntegrityError,
    ProductNotFoundError,
    ProductVersionNotFoundError,
)

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures"
TENANT = "tenant-cshi"
AS_OF = "2026-06-01T00:00:00Z"


@pytest.fixture()
def adapter() -> FakeProductAdapter:
    return FakeProductAdapter.from_fixture_dir(FIXTURE_DIR)


def _doc(**overrides: object) -> ProductDocumentV1:
    base: dict[str, object] = {
        "schema_version": "1.0",
        "source_id": "doc-x",
        "source_version": "1.0.0",
        "product_id": "product-x",
        "tenant": TENANT,
        "market": "US",
        "locale": "en-US",
        "approval_status": "APPROVED",
        "approved_by": "emp-1",
        "effective_from": "2026-01-01T00:00:00Z",
        "expires_at": None,
        "revoked_at": None,
        "classification": "internal",
        "content_hash": "sha256:" + "aa" * 32,
        "content": "text",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    base.update(overrides)
    return ProductDocumentV1.model_validate(base)


class TestDefaultFilters:
    def test_only_approved_unexpired_unrevoked_documents(
        self, adapter: FakeProductAdapter
    ) -> None:
        docs = adapter.list_approved_documents(
            "product-alpha", "US", "en-US", AS_OF, tenant=TENANT
        )
        ids = {doc.source_id for doc in docs}
        assert "doc-alpha-label" in ids
        assert "doc-alpha-dosing" in ids
        assert "doc-alpha-injection" in ids
        # 硬门：过期 / 撤销 / 草稿来源返回数必须为 0。
        assert "doc-alpha-expired" not in ids
        assert "doc-alpha-revoked" not in ids
        assert "doc-alpha-draft" not in ids

    def test_expired_by_as_of_boundary(self, adapter: FakeProductAdapter) -> None:
        docs = adapter.list_approved_documents(
            "product-alpha", "US", "en-US", "2027-01-01T00:00:00Z", tenant=TENANT
        )
        assert all(doc.source_id != "doc-alpha-label" for doc in docs)

    def test_not_yet_effective_excluded(self, adapter: FakeProductAdapter) -> None:
        docs = adapter.list_approved_documents(
            "product-alpha", "US", "en-US", "2026-01-15T00:00:00Z", tenant=TENANT
        )
        assert all(doc.source_id != "doc-alpha-dosing" for doc in docs)

    def test_claims_filtered_the_same_way(self, adapter: FakeProductAdapter) -> None:
        claims = adapter.get_claims(
            "product-alpha", "US", "en-US", AS_OF, tenant=TENANT
        )
        ids = {claim.claim_id for claim in claims}
        assert ids == {"claim-alpha-efficacy"}

    def test_every_result_has_version_validity_and_hash(
        self, adapter: FakeProductAdapter
    ) -> None:
        docs = adapter.list_approved_documents(
            "product-alpha", "US", "en-US", AS_OF, tenant=TENANT
        )
        assert docs, "expected approved documents in fixtures"
        for doc in docs:
            assert doc.source_version
            assert doc.effective_from
            assert doc.content_hash.startswith("sha256:")
            assert doc.approved_by is not None


class TestCrossBoundaryIsolation:
    def test_cross_tenant_results_are_zero(self, adapter: FakeProductAdapter) -> None:
        docs = adapter.list_approved_documents(
            "product-alpha", "US", "en-US", AS_OF, tenant="tenant-other"
        )
        assert {doc.tenant for doc in docs} <= {"tenant-other"}
        claims = adapter.get_claims(
            "product-alpha", "US", "en-US", AS_OF, tenant="tenant-other"
        )
        assert all(claim.tenant == "tenant-other" for claim in claims)

    def test_unknown_tenant_gets_nothing_not_error(
        self, adapter: FakeProductAdapter
    ) -> None:
        assert (
            adapter.list_approved_documents(
                "product-alpha", "US", "en-US", AS_OF, tenant="tenant-nobody"
            )
            == ()
        )

    def test_cross_market_results_are_zero(self, adapter: FakeProductAdapter) -> None:
        docs = adapter.list_approved_documents(
            "product-alpha", "CN", "en-US", AS_OF, tenant=TENANT
        )
        assert docs == ()

    def test_cross_locale_results_are_zero(self, adapter: FakeProductAdapter) -> None:
        docs = adapter.list_approved_documents(
            "product-alpha", "US", "fr-FR", AS_OF, tenant=TENANT
        )
        assert docs == ()

    def test_locale_variant_is_isolated(self, adapter: FakeProductAdapter) -> None:
        docs = adapter.list_approved_documents(
            "product-alpha", "US", "de-DE", AS_OF, tenant=TENANT
        )
        assert {doc.locale for doc in docs} == {"de-DE"}

    def test_change_feed_is_tenant_scoped(self, adapter: FakeProductAdapter) -> None:
        page = adapter.get_changes(None, tenant=TENANT)
        assert all(change.tenant == TENANT for change in page.changes)
        assert all(change.change_id != "chg-9001" for change in page.changes)


class TestGetProduct:
    def test_returns_latest_approved_version(
        self, adapter: FakeProductAdapter
    ) -> None:
        record = adapter.get_product("product-alpha", tenant=TENANT)
        assert record.latest_approved_version == "2.1.0"
        assert "US" in record.markets and "CN" in record.markets

    def test_unknown_product_raises_typed_error(
        self, adapter: FakeProductAdapter
    ) -> None:
        with pytest.raises(ProductNotFoundError):
            adapter.get_product("product-nonexistent", tenant=TENANT)

    def test_cross_tenant_product_is_not_found(
        self, adapter: FakeProductAdapter
    ) -> None:
        with pytest.raises(ProductNotFoundError):
            adapter.get_product("product-alpha", tenant="tenant-nobody")

    def test_unknown_version_raises_typed_error(
        self, adapter: FakeProductAdapter
    ) -> None:
        with pytest.raises(ProductVersionNotFoundError):
            adapter.get_product("product-alpha", "9.9.9", tenant=TENANT)


class TestIntegrity:
    def test_hash_conflict_rejected_at_load(self) -> None:
        first = _doc(content_hash="sha256:" + "aa" * 32)
        conflicting = _doc(content_hash="sha256:" + "bb" * 32)
        with pytest.raises(ProductIntegrityError):
            FakeProductAdapter(documents=[first, conflicting])

    def test_same_hash_duplicate_is_allowed(self) -> None:
        FakeProductAdapter(documents=[_doc(), _doc()])

    def test_invalid_fixture_data_rejected_at_load(self, tmp_path: Path) -> None:
        bad = [{"schema_version": "1.0", "source_id": "doc-x", "extra": "field"}]
        (tmp_path / "documents.json").write_text(json.dumps(bad), encoding="utf-8")
        with pytest.raises(FixtureValidationError):
            FakeProductAdapter.from_fixture_dir(tmp_path)


class TestChangeCursorReplay:
    def test_first_page_is_deterministic(self, adapter: FakeProductAdapter) -> None:
        first = adapter.get_changes(None, tenant=TENANT)
        replay = adapter.get_changes(None, tenant=TENANT)
        assert first == replay
        assert [c.cursor for c in first.changes] == sorted(
            c.cursor for c in first.changes
        )

    def test_cursor_replay_returns_same_page(
        self, adapter: FakeProductAdapter
    ) -> None:
        page = adapter.get_changes("cursor-000002", tenant=TENANT)
        replay = adapter.get_changes("cursor-000002", tenant=TENANT)
        assert page == replay
        assert all(c.cursor > "cursor-000002" for c in page.changes)

    def test_unknown_cursor_raises_typed_error(
        self, adapter: FakeProductAdapter
    ) -> None:
        with pytest.raises(InvalidCursorError):
            adapter.get_changes("cursor-does-not-exist", tenant=TENANT)

    def test_exhausted_feed_keeps_cursor_stable(
        self, adapter: FakeProductAdapter
    ) -> None:
        page = adapter.get_changes(None, tenant=TENANT)
        assert page.next_cursor is not None
        tail = adapter.get_changes(page.next_cursor, tenant=TENANT)
        assert tail.changes == ()
        assert tail.next_cursor == page.next_cursor

    def test_revocation_events_are_present_for_downstream_purge(
        self, adapter: FakeProductAdapter
    ) -> None:
        page = adapter.get_changes(None, tenant=TENANT)
        revoked = [c for c in page.changes if c.change_type == "REVOKED"]
        assert {c.entity_type for c in revoked} == {"document", "claim"}


class TestUntrustedFreeText:
    def test_injection_text_is_returned_verbatim_as_data(
        self, adapter: FakeProductAdapter
    ) -> None:
        docs = adapter.list_approved_documents(
            "product-alpha", "US", "en-US", AS_OF, tenant=TENANT
        )
        injected = next(d for d in docs if d.source_id == "doc-alpha-injection")
        assert "IGNORE ALL PREVIOUS INSTRUCTIONS" in injected.content
        # 契约保证：文档模型冻结，自由文本无法在返回路径上被改写或执行。
        assert injected.model_config.get("frozen") is True

    def test_adapter_exposes_no_write_methods(
        self, adapter: FakeProductAdapter
    ) -> None:
        forbidden = [
            name
            for name in dir(adapter)
            if not name.startswith("_")
            and any(
                name.startswith(prefix)
                for prefix in ("set_", "put_", "create_", "update_", "delete_")
            )
        ]
        assert forbidden == []
