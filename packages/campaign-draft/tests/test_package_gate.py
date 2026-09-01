"""RED tests: package validity, hash binding and channel variant gates.

The Campaign Agent may only consume an ``APPROVED``, unexpired,
hash-matching ``ApprovedContentPackage`` that carries the requested
channel variant. Everything else must be rejected with a structured
error — never replaced by model-guessed content.
"""

from __future__ import annotations

import pytest

from campaign_draft import (
    MissingChannelVariantError,
    PackageHashMismatchError,
    PackageNotConsumableError,
    build_campaign_draft,
)

from builders import FAKE_NOW, load_package, make_request


def test_approved_package_produces_draft() -> None:
    package = load_package()
    proposal = build_campaign_draft(
        package=package,
        expected_content_hash=package.content_hash,
        request=make_request(),
        as_of=FAKE_NOW,
    )
    assert proposal.status == "DRAFT"
    assert proposal.content_package_id == package.package_id
    assert proposal.content_package_hash == package.content_hash


def test_revoked_package_is_blocked() -> None:
    package = load_package(status="REVOKED")
    with pytest.raises(PackageNotConsumableError):
        build_campaign_draft(
            package=package,
            expected_content_hash=package.content_hash,
            request=make_request(),
            as_of=FAKE_NOW,
        )


def test_superseded_ledger_status_is_blocked() -> None:
    package = load_package()
    with pytest.raises(PackageNotConsumableError):
        build_campaign_draft(
            package=package,
            expected_content_hash=package.content_hash,
            request=make_request(),
            as_of=FAKE_NOW,
            ledger_status="SUPERSEDED",
        )


def test_expired_package_is_blocked() -> None:
    package = load_package(expires_at="2026-09-01T00:00:00Z")
    with pytest.raises(PackageNotConsumableError):
        build_campaign_draft(
            package=package,
            expected_content_hash=package.content_hash,
            request=make_request(),
            as_of=FAKE_NOW,
        )


def test_content_hash_mismatch_is_blocked() -> None:
    package = load_package()
    with pytest.raises(PackageHashMismatchError):
        build_campaign_draft(
            package=package,
            expected_content_hash="sha256:" + "0" * 64,
            request=make_request(),
            as_of=FAKE_NOW,
        )


def test_tampered_approval_binding_is_blocked() -> None:
    tampered = load_package(
        approvals=tuple(
            approval.model_copy(update={"artifact_hash": "sha256:" + "f" * 64})
            for approval in load_package().approvals
        )
    )
    with pytest.raises(PackageNotConsumableError):
        build_campaign_draft(
            package=tampered,
            expected_content_hash=tampered.content_hash,
            request=make_request(),
            as_of=FAKE_NOW,
        )


def test_missing_channel_variant_is_blocked() -> None:
    package = load_package()
    with pytest.raises(MissingChannelVariantError):
        build_campaign_draft(
            package=package,
            expected_content_hash=package.content_hash,
            request=make_request(channel="google_ads"),
            as_of=FAKE_NOW,
        )


def test_tenant_mismatch_is_blocked() -> None:
    package = load_package()
    with pytest.raises(PackageNotConsumableError):
        build_campaign_draft(
            package=package,
            expected_content_hash=package.content_hash,
            request=make_request(tenant_id="tenant-other"),
            as_of=FAKE_NOW,
        )
