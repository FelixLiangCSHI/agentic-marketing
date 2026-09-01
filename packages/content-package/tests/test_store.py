"""Store tests: versioning, supersession, audit trail, revocation and the
consumption gate for expired / revoked packages."""

from __future__ import annotations

import pytest
from builders import AS_OF, make_draft, make_inputs

from content_package import (
    DuplicateVersionError,
    InvalidPackageTransitionError,
    PackageBuilder,
    PackageStore,
    UnknownPackageError,
    consumable,
    lineage_key,
)

BUILDER = PackageBuilder()
NOW = "2026-06-01T01:00:00Z"


def _package(headline: str = "Product Alpha dosing overview", version: int = 1):  # type: ignore[no-untyped-def]
    return BUILDER.build(
        make_inputs(draft=make_draft(headline=headline)), as_of=AS_OF, version=version
    )


def _tenant_package(tenant_id: str, headline: str, version: int = 1):  # type: ignore[no-untyped-def]
    return BUILDER.build(
        make_inputs(tenant_id=tenant_id, draft=make_draft(headline=headline)),
        as_of=AS_OF,
        version=version,
    )


class TestVersioningAndAudit:
    def test_new_version_supersedes_old_and_keeps_audit(self) -> None:
        store = PackageStore()
        v1 = _package()
        v2 = _package("Updated headline", version=2)
        store.publish(v1, recorded_at=NOW)
        store.publish(v2, recorded_at="2026-06-01T02:00:00Z")

        assert store.get(v1.package_id).status == "SUPERSEDED"
        assert store.get(v2.package_id).status == "APPROVED"
        # 旧版本文档保留、可读，未被原位修改。
        assert store.get_package(v1.package_id).package_hash() == v1.package_hash()

        trail = store.audit_trail(lineage_key(v1))
        statuses = [entry.status for entry in trail]
        assert statuses == ["APPROVED", "SUPERSEDED", "APPROVED"]
        assert "superseded by" in trail[1].reason

    def test_duplicate_publish_is_idempotent(self) -> None:
        store = PackageStore()
        package = _package()
        first = store.publish(package, recorded_at=NOW)
        second = store.publish(package, recorded_at="2026-06-02T00:00:00Z")
        assert first is second
        assert len(store.audit_trail(lineage_key(package))) == 1

    def test_forged_package_with_reused_id_is_rejected(self) -> None:
        store = PackageStore()
        package = _package()
        store.publish(package, recorded_at=NOW)
        forged = package.model_copy(update={"expires_at": "2028-01-01T00:00:00Z"})
        with pytest.raises(DuplicateVersionError):
            store.publish(forged, recorded_at=NOW)

    def test_active_returns_latest_approved(self) -> None:
        store = PackageStore()
        v1 = _package()
        v2 = _package("Updated headline", version=2)
        store.publish(v1, recorded_at=NOW)
        store.publish(v2, recorded_at=NOW)
        active = store.active(lineage_key(v1))
        assert active is not None
        assert active.package.package_id == v2.package_id

    def test_publish_supersedes_only_within_same_tenant_lineage(self) -> None:
        store = PackageStore()
        tenant_a = _tenant_package("tenant-cshi", "Tenant A headline")
        tenant_b = _tenant_package("tenant-other", "Tenant B headline")

        store.publish(tenant_a, recorded_at=NOW)
        store.publish(tenant_b, recorded_at="2026-06-01T02:00:00Z")

        assert store.get(tenant_a.package_id).status == "APPROVED"
        assert store.get(tenant_b.package_id).status == "APPROVED"
        assert lineage_key(tenant_a).startswith("tenant-cshi|")
        assert lineage_key(tenant_b).startswith("tenant-other|")


class TestRevocationAndConsumption:
    def test_revoked_package_blocks_consumption(self) -> None:
        store = PackageStore()
        package = _package()
        store.publish(package, recorded_at=NOW)
        store.revoke(package.package_id, reason="source withdrawn", recorded_at=NOW)
        entry = store.get(package.package_id)
        assert entry.status == "REVOKED"
        allowed, reason = consumable(
            package, as_of=AS_OF, ledger_status=entry.status
        )
        assert allowed is False and "REVOKED" in reason

    def test_revoke_on_approved_still_works(self) -> None:
        store = PackageStore()
        package = _package()
        store.publish(package, recorded_at=NOW)

        revoked = store.revoke(
            package.package_id,
            reason="source withdrawn",
            recorded_at="2026-06-01T02:00:00Z",
        )

        assert revoked.status == "REVOKED"
        assert store.get(package.package_id) is revoked

    def test_revoke_on_revoked_package_is_invalid_transition(self) -> None:
        store = PackageStore()
        package = _package()
        store.publish(package, recorded_at=NOW)
        store.revoke(package.package_id, reason="source withdrawn", recorded_at=NOW)

        with pytest.raises(InvalidPackageTransitionError, match="REVOKED"):
            store.revoke(
                package.package_id,
                reason="duplicate revoke",
                recorded_at="2026-06-01T02:00:00Z",
            )

    def test_revoke_on_superseded_package_is_invalid_transition(self) -> None:
        store = PackageStore()
        v1 = _package()
        v2 = _package("Updated headline", version=2)
        store.publish(v1, recorded_at=NOW)
        store.publish(v2, recorded_at="2026-06-01T02:00:00Z")

        with pytest.raises(InvalidPackageTransitionError, match="SUPERSEDED"):
            store.revoke(
                v1.package_id,
                reason="old version withdrawn",
                recorded_at="2026-06-01T03:00:00Z",
            )

    def test_expired_package_blocks_consumption(self) -> None:
        package = _package()
        allowed, reason = consumable(package, as_of="2027-06-01T00:00:00Z")
        assert allowed is False and "expired" in reason

    def test_revoked_product_blocks_consumption(self) -> None:
        package = _package()
        allowed, reason = consumable(
            package, as_of=AS_OF, product_status="REVOKED"
        )
        assert allowed is False and "product" in reason

    def test_unknown_package_is_typed_error(self) -> None:
        store = PackageStore()
        with pytest.raises(UnknownPackageError):
            store.get("acp_" + "0" * 24)
