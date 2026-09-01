"""Mutate mapper tests: verified fields only, deterministic request hash,
customer-id references (never literals), unverified objectives fail closed."""

from __future__ import annotations

from decimal import Decimal

import pytest

from google_ads_connector import (
    VerificationRequiredMappingError,
    map_campaign_mutate,
    response_digest,
)

from builders import make_config, make_proposal


class TestMapCampaignMutate:
    def test_maps_verified_fields_only(self) -> None:
        config = make_config()
        proposal = make_proposal()
        mapped = map_campaign_mutate(proposal=proposal, config=config)
        operation = mapped.mutate_request["operations"][0]["create"]
        assert mapped.mutate_request["customer_id_ref"] == config.account.customer_id_ref
        assert mapped.mutate_request["login_customer_id_ref"] == (
            config.account.login_customer_id_ref
        )
        assert operation["name"] == proposal.campaign_name
        assert operation["status"] == "PAUSED"
        assert operation["budget"]["amount_minor"] == proposal.budget.total_limit_minor
        assert operation["budget"]["currency"] == proposal.budget.currency
        assert operation["schedule"]["start_at"] == proposal.schedule.start_at
        assert operation["geo_targets"] == list(proposal.audience.markets)

    def test_request_hash_is_deterministic(self) -> None:
        config = make_config()
        first = map_campaign_mutate(proposal=make_proposal(), config=config)
        second = map_campaign_mutate(proposal=make_proposal(), config=config)
        assert first.request_hash == second.request_hash
        assert first.request_hash.startswith("sha256:")

    def test_budget_change_changes_hash(self) -> None:
        config = make_config()
        base = map_campaign_mutate(proposal=make_proposal(), config=config)
        changed = map_campaign_mutate(
            proposal=make_proposal(total_limit=Decimal("2000.00")), config=config
        )
        assert base.request_hash != changed.request_hash

    def test_unverified_objective_fails_closed(self) -> None:
        config = make_config()
        proposal = make_proposal(objective="BRAND_AWARENESS").model_copy(
            update={"objective": "TRAFFIC_SURGE"}
        )
        with pytest.raises(VerificationRequiredMappingError) as excinfo:
            map_campaign_mutate(proposal=proposal, config=config)
        assert excinfo.value.code == "verification_required"

    def test_no_literal_customer_id_in_request(self) -> None:
        mapped = map_campaign_mutate(proposal=make_proposal(), config=make_config())
        assert mapped.mutate_request["customer_id_ref"].startswith("config://")


class TestResponseDigest:
    def test_digest_is_stable_and_order_insensitive(self) -> None:
        assert response_digest({"a": 1, "b": 2}) == response_digest({"b": 2, "a": 1})
        assert response_digest({"a": 1}).startswith("sha256:")
