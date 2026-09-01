"""RED tests: deterministic hashing, versioning and DRAFT-only status.

The same input + versions + fake clock must always produce the same
``input_hash`` and ``proposal_id``; any bound field change produces a new
hash, a new proposal id and a higher version. A draft never creates
external objects and is always ``DRAFT``.
"""

from __future__ import annotations

from decimal import Decimal

import pydantic
import pytest

from campaign_draft import CampaignProposalV1, build_campaign_draft

from builders import FAKE_NOW, load_package, make_request


def _draft(previous: CampaignProposalV1 | None = None, **overrides: object) -> CampaignProposalV1:
    package = load_package()
    return build_campaign_draft(
        package=package,
        expected_content_hash=package.content_hash,
        request=make_request(**overrides),
        as_of=FAKE_NOW,
        previous=previous,
    )


def test_same_input_and_clock_is_deterministic() -> None:
    first = _draft()
    second = _draft()
    assert first.input_hash == second.input_hash
    assert first.proposal_id == second.proposal_id
    assert first == second


def test_budget_change_produces_new_hash_and_version() -> None:
    first = _draft()
    second = _draft(previous=first, total_limit=Decimal("2000.00"))
    assert second.input_hash != first.input_hash
    assert second.proposal_id != first.proposal_id
    assert second.version == first.version + 1


def test_audience_change_produces_new_hash() -> None:
    first = _draft()
    second = _draft(previous=first, excluded_segments=("competitors",))
    assert second.input_hash != first.input_hash


def test_rebuild_with_same_input_is_idempotent_against_previous() -> None:
    first = _draft()
    again = _draft(previous=first)
    assert again == first
    assert again.version == first.version


def test_status_is_always_draft_and_hashes_are_bound() -> None:
    proposal = _draft()
    assert proposal.status == "DRAFT"
    assert proposal.schema_version == "1.0"
    assert proposal.version == 1
    assert proposal.input_hash.startswith("sha256:")
    assert proposal.proposal_id.startswith("cpr_")
    assert proposal.created_at == FAKE_NOW
    assert proposal.channel_variant_refs  # copied from the approved package
    assert proposal.asset_hashes == load_package().asset_hashes


def test_proposal_model_is_frozen_and_rejects_unknown_fields() -> None:
    proposal = _draft()
    with pytest.raises(pydantic.ValidationError):
        proposal.status = "SUPERSEDED"
    with pytest.raises(pydantic.ValidationError):
        CampaignProposalV1.model_validate(
            {**proposal.model_dump(mode="json"), "surprise": True}
        )


def test_proposal_never_contains_content_private_context() -> None:
    proposal = _draft()
    dumped = proposal.model_dump(mode="json")
    flat = str(dumped)
    for forbidden in ("credential", "secret", "refresh_token", "api_key"):
        assert forbidden not in flat
    assert set(dumped) == {
        "schema_version",
        "proposal_id",
        "version",
        "status",
        "tenant_id",
        "run_id",
        "content_package_id",
        "content_package_hash",
        "channel",
        "account_id",
        "objective",
        "campaign_name",
        "budget",
        "schedule",
        "audience",
        "channel_variant_refs",
        "asset_hashes",
        "policy_version",
        "workflow_version",
        "input_hash",
        "warnings",
        "created_by",
        "created_at",
    }
