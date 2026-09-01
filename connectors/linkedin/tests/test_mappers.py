"""RED tests: proposal -> LinkedIn resource mapper.

The mapper only emits officially-verified minimal fields, keeps
request/response digests (sha256), never invents provider ID formats and
returns ``verification_required`` for anything not covered by the
recorded official-doc verification.
"""

from __future__ import annotations

import pytest

from linkedin_connector import (
    VerificationRequiredMappingError,
    map_campaign_request,
    response_digest,
)

from builders import make_proposal


def test_mapping_contains_only_verified_minimal_fields() -> None:
    mapped = map_campaign_request(proposal=make_proposal(), api_version="env://LINKEDIN_API_VERSION")
    assert set(mapped.resource.keys()) == {
        "account",
        "name",
        "objective_type",
        "total_budget",
        "daily_budget",
        "run_schedule",
        "locale_targets",
        "status",
    }
    assert mapped.resource["status"] == "DRAFT"
    assert mapped.resource["total_budget"] == {"amount_minor": 100000, "currency": "USD"}
    assert mapped.resource["run_schedule"] == {
        "start_at": "2026-09-21T00:00:00Z",
        "end_at": "2026-10-02T23:59:59Z",
        "timezone": "America/New_York",
    }


def test_request_hash_is_deterministic_sha256() -> None:
    first = map_campaign_request(proposal=make_proposal(), api_version="env://LINKEDIN_API_VERSION")
    second = map_campaign_request(proposal=make_proposal(), api_version="env://LINKEDIN_API_VERSION")
    assert first.request_hash == second.request_hash
    assert first.request_hash.startswith("sha256:")


def test_request_hash_changes_when_binding_field_changes() -> None:
    base = map_campaign_request(proposal=make_proposal(), api_version="env://LINKEDIN_API_VERSION")
    changed = map_campaign_request(
        proposal=make_proposal(campaign_name="alpha-q4-lead-gen-v2"),
        api_version="env://LINKEDIN_API_VERSION",
    )
    assert base.request_hash != changed.request_hash


def test_unverified_objective_returns_verification_required() -> None:
    with pytest.raises(VerificationRequiredMappingError) as excinfo:
        map_campaign_request(
            proposal=make_proposal(objective="ENGAGEMENT"),
            api_version="env://LINKEDIN_API_VERSION",
        )
    assert excinfo.value.code == "verification_required"


def test_response_digest_is_stable() -> None:
    payload = {"id": "urn:li:sponsoredCampaign:123", "status": "DRAFT"}
    assert response_digest(payload) == response_digest(dict(payload))
    assert response_digest(payload).startswith("sha256:")


def test_mapper_never_embeds_secret_or_token_fields() -> None:
    mapped = map_campaign_request(proposal=make_proposal(), api_version="env://LINKEDIN_API_VERSION")
    flat = str(mapped.resource).lower()
    for needle in ("token", "secret", "authorization", "cookie"):
        assert needle not in flat
