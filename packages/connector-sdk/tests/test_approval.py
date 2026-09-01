"""Tests for connector-side approval hash re-verification (defence in depth)."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from campaign_draft import CampaignProposalV1, DraftRequest, build_campaign_draft
from content_package import ApprovedContentPackageV1

from connector_sdk import SchemaInvalidError, verify_approved_input

FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "content-package"
    / "fixtures"
    / "phase03"
    / "approved-content-package.sample.json"
)


def make_proposal(**overrides: Any) -> CampaignProposalV1:
    document = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    package = ApprovedContentPackageV1.model_validate(document, strict=False)
    values: dict[str, Any] = {
        "tenant_id": "tenant-cshi",
        "run_id": "run-p3-0005",
        "requester_id": "emp-campaign-op",
        "channel": "linkedin",
        "account_id": "acct-linkedin-dev",
        "objective": "LEAD_GENERATION",
        "campaign_name": "alpha-q4-lead-gen",
        "currency": "USD",
        "total_limit": Decimal("1000.00"),
        "daily_limit": Decimal("100.00"),
        "timezone": "America/New_York",
        "start_at": "2026-09-21T00:00:00Z",
        "end_at": "2026-10-02T23:59:59Z",
        "markets": ("US",),
        "excluded_segments": (),
        "policy_version": "campaign-policy-1.0.0",
        "workflow_version": "1.0.0",
    }
    values.update(overrides)
    return build_campaign_draft(
        package=package,
        expected_content_hash=package.content_hash,
        request=DraftRequest(**values),
        as_of="2026-09-14T00:00:00Z",
    )


def test_matching_hashes_pass() -> None:
    proposal = make_proposal()
    verify_approved_input(proposal, input_hash=proposal.input_hash)


def test_caller_hash_mismatch_rejected() -> None:
    proposal = make_proposal()
    with pytest.raises(SchemaInvalidError):
        verify_approved_input(proposal, input_hash="sha256:" + "1" * 64)


def test_tampered_bound_field_rejected() -> None:
    proposal = make_proposal()
    approved_hash = proposal.input_hash
    tampered = proposal.model_copy(update={"campaign_name": "tampered-name"})
    with pytest.raises(SchemaInvalidError):
        verify_approved_input(tampered, input_hash=approved_hash)
