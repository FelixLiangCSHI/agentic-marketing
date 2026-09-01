"""Builder hard-gate tests (written first per the subphase prompt):
unapproved, expired, hash mismatch, missing channel variant, asset
modification and duplicate build.
"""

from __future__ import annotations

import pytest
from builders import (
    AS_OF,
    make_approval,
    make_claim,
    make_draft,
    make_inputs,
    make_media,
)

from content_package import (
    AssetTamperedError,
    ExpiredInputError,
    MissingChannelVariantError,
    NotApprovedError,
    PackageBuilder,
    RevokedInputError,
    StaleApprovalError,
    UncitedClaimError,
    consumable,
    verify_package_integrity,
)

BUILDER = PackageBuilder()


class TestHappyPath:
    def test_builds_sealed_approved_package(self) -> None:
        package = BUILDER.build(make_inputs(), as_of=AS_OF)
        assert package.schema_version == "1.0"
        assert package.status == "APPROVED"
        assert package.tenant_id == "tenant-cshi"
        assert package.package_id.startswith("acp_")
        assert package.version == 1
        assert package.content_hash.startswith("sha256:")
        assert package.claims[0].source_excerpt_hash.startswith("sha256:")
        assert {a.track for a in package.approvals} == {"medical", "marketing"}
        assert verify_package_integrity(package)
        assert consumable(package, as_of=AS_OF) == (True, "consumable")

    def test_package_is_immutable(self) -> None:
        package = BUILDER.build(make_inputs(), as_of=AS_OF)
        with pytest.raises(Exception):
            package.status = "REVOKED"  # type: ignore[misc, unused-ignore]


class TestUnapproved:
    def test_blocked_compliance_can_never_be_packaged(self) -> None:
        draft = make_draft(headline="A miracle cure headline")
        inputs = make_inputs(draft=draft)
        assert inputs.compliance_result.automated_status == "BLOCKED"
        with pytest.raises(NotApprovedError):
            BUILDER.build(inputs, as_of=AS_OF)

    def test_missing_marketing_track_is_refused(self) -> None:
        base = make_inputs()
        inputs = make_inputs(
            approvals=(
                make_approval(
                    "medical", artifact_hash=base.approvals[0].artifact_hash
                ),
            )
        )
        with pytest.raises(NotApprovedError, match="marketing"):
            BUILDER.build(inputs, as_of=AS_OF)

    def test_same_identity_cannot_approve_both_tracks(self) -> None:
        base = make_inputs()
        artifact_hash = base.approvals[0].artifact_hash
        inputs = make_inputs(
            approvals=(
                make_approval(
                    "medical", artifact_hash=artifact_hash, approved_by="emp-dual"
                ),
                make_approval(
                    "marketing", artifact_hash=artifact_hash, approved_by="emp-dual"
                ),
            )
        )
        with pytest.raises(NotApprovedError, match="same identity"):
            BUILDER.build(inputs, as_of=AS_OF)

    def test_uncited_claim_is_refused(self) -> None:
        draft = make_draft(claims=(make_claim(cited=False),))
        # bypass compliance objection focus: builder itself must refuse.
        base = make_inputs()
        inputs = make_inputs(
            draft=draft, compliance_result=base.compliance_result
        )
        with pytest.raises(UncitedClaimError):
            BUILDER.build(inputs, as_of=AS_OF)


class TestExpiryAndRevocation:
    def test_expired_claim_source_is_refused(self) -> None:
        draft = make_draft(
            claims=(make_claim(expires_at="2026-05-01T00:00:00Z"),)
        )
        base = make_inputs()
        inputs = make_inputs(draft=draft, compliance_result=base.compliance_result)
        with pytest.raises(ExpiredInputError, match="expired"):
            BUILDER.build(inputs, as_of=AS_OF)

    def test_package_expiry_must_be_in_future(self) -> None:
        inputs = make_inputs(expires_at="2026-05-01T00:00:00Z")
        with pytest.raises(ExpiredInputError, match="expiry"):
            BUILDER.build(inputs, as_of=AS_OF)

    def test_revoked_product_blocks_build(self) -> None:
        inputs = make_inputs(product_status="REVOKED")
        with pytest.raises(RevokedInputError, match="product"):
            BUILDER.build(inputs, as_of=AS_OF)

    def test_expired_skill_blocks_build(self) -> None:
        inputs = make_inputs(skill_statuses={"copywriting": "EXPIRED"})
        with pytest.raises(RevokedInputError, match="skill"):
            BUILDER.build(inputs, as_of=AS_OF)

    def test_revoked_policy_blocks_build(self) -> None:
        inputs = make_inputs(policy_status="REVOKED")
        with pytest.raises(RevokedInputError, match="policy"):
            BUILDER.build(inputs, as_of=AS_OF)


class TestHashBinding:
    def test_approval_bound_to_other_version_is_stale(self) -> None:
        wrong_hash = "sha256:" + "0" * 64
        inputs = make_inputs(
            approvals=(
                make_approval("medical", artifact_hash=wrong_hash),
                make_approval("marketing", artifact_hash=wrong_hash),
            )
        )
        with pytest.raises(StaleApprovalError):
            BUILDER.build(inputs, as_of=AS_OF)

    def test_content_change_after_approval_invalidates_it(self) -> None:
        base = make_inputs()
        # 内容在批准后被改动：审批还绑定旧 hash → 拒绝。
        changed = make_inputs(
            draft=make_draft(headline="Edited after approval"),
            approvals=base.approvals,
        )
        with pytest.raises(StaleApprovalError):
            BUILDER.build(changed, as_of=AS_OF)

    def test_asset_modification_changes_hash_and_invalidates(self) -> None:
        base = make_inputs()
        tampered = make_inputs(
            media=(make_media("tampered"),), approvals=base.approvals
        )
        with pytest.raises(StaleApprovalError):
            BUILDER.build(tampered, as_of=AS_OF)

    def test_asset_uri_count_mismatch_is_tampering(self) -> None:
        inputs = make_inputs(asset_uris=())
        with pytest.raises(AssetTamperedError):
            BUILDER.build(inputs, as_of=AS_OF)


class TestChannelVariants:
    def test_missing_requested_channel_variant_is_refused(self) -> None:
        inputs = make_inputs(requested_channels=("linkedin", "google_ads"))
        with pytest.raises(MissingChannelVariantError, match="google_ads"):
            BUILDER.build(inputs, as_of=AS_OF)

    def test_empty_variant_list_is_refused(self) -> None:
        draft = make_draft()
        inputs = make_inputs(
            draft=draft, channel_variants=(("linkedin", ()),)
        )
        with pytest.raises(MissingChannelVariantError):
            BUILDER.build(inputs, as_of=AS_OF)


class TestDuplicateBuild:
    def test_duplicate_build_is_idempotent(self) -> None:
        first = BUILDER.build(make_inputs(), as_of=AS_OF)
        second = BUILDER.build(make_inputs(), as_of=AS_OF)
        assert first.package_id == second.package_id
        assert first.content_hash == second.content_hash
        assert first.package_hash() == second.package_hash()

    def test_any_bound_field_change_creates_new_identity(self) -> None:
        first = BUILDER.build(make_inputs(), as_of=AS_OF)
        changed_draft = make_draft(headline="A different headline")
        second = BUILDER.build(make_inputs(draft=changed_draft), as_of=AS_OF)
        assert first.content_hash != second.content_hash
        assert first.package_id != second.package_id

    def test_tenant_is_bound_to_content_hash(self) -> None:
        first = BUILDER.build(make_inputs(tenant_id="tenant-cshi"), as_of=AS_OF)
        second = BUILDER.build(make_inputs(tenant_id="tenant-other"), as_of=AS_OF)
        assert first.content_hash != second.content_hash
        assert first.package_id != second.package_id
