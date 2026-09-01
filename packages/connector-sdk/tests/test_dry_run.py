"""RED tests: side-effect-free channel dry-run with 100% interception.

The shared dry-run validates account, objective, budget, currency,
timezone, dates, markets, audience and creative constraints against the
channel policy. Every violation yields a structured error; the dry-run
never performs any external call.
"""

from __future__ import annotations

from typing import Any

from connector_sdk import run_dry_run

from builders import FAKE_NOW, make_policy, make_proposal


def _dry_run(proposal_overrides: dict[str, Any] | None = None, **policy_overrides: Any):  # type: ignore[no-untyped-def]
    proposal = make_proposal(**(proposal_overrides or {}))
    policy = make_policy(**policy_overrides)
    return run_dry_run(proposal=proposal, policy=policy, as_of=FAKE_NOW)


def test_valid_proposal_passes_with_fingerprint() -> None:
    result = _dry_run()
    assert result.valid
    assert result.errors == ()
    assert result.request_fingerprint.startswith("sha256:")
    assert result.normalized_request["channel"] == "linkedin"


def test_same_proposal_same_fingerprint() -> None:
    assert _dry_run().request_fingerprint == _dry_run().request_fingerprint


def test_unknown_account_intercepted() -> None:
    result = _dry_run({}, known_accounts=("acct-other",))
    assert not result.valid
    assert any(error.code == "account_unknown" for error in result.errors)


def test_channel_mismatch_intercepted() -> None:
    result = _dry_run(channel="google_ads")
    assert not result.valid
    assert any(error.code == "channel_mismatch" for error in result.errors)


def test_objective_not_allowed_intercepted() -> None:
    result = _dry_run(allowed_objectives=("BRAND_AWARENESS",))
    assert not result.valid
    assert any(error.code == "objective_not_allowed" for error in result.errors)


def test_budget_over_policy_cap_intercepted() -> None:
    result = _dry_run(max_total_budget_minor=1000)
    assert not result.valid
    assert any(error.code == "budget_over_limit" for error in result.errors)


def test_daily_budget_over_cap_intercepted() -> None:
    result = _dry_run(max_daily_budget_minor=100)
    assert not result.valid
    assert any(error.code == "daily_budget_over_limit" for error in result.errors)


def test_currency_not_allowed_intercepted() -> None:
    result = _dry_run(allowed_currencies=("EUR",))
    assert not result.valid
    assert any(error.code == "currency_not_allowed" for error in result.errors)


def test_market_not_allowed_intercepted() -> None:
    result = _dry_run(allowed_markets=())
    assert not result.valid
    assert any(error.code == "market_not_allowed" for error in result.errors)


def test_duration_over_policy_intercepted() -> None:
    result = _dry_run(max_duration_days=3)
    assert not result.valid
    assert any(error.code == "schedule_too_long" for error in result.errors)


def test_start_in_past_intercepted() -> None:
    proposal = make_proposal()
    policy = make_policy()
    from connector_sdk import run_dry_run as dr

    result = dr(proposal=proposal, policy=policy, as_of="2026-09-25T00:00:00Z")
    assert not result.valid
    assert any(error.code == "schedule_start_in_past" for error in result.errors)


def test_campaign_name_too_long_intercepted() -> None:
    result = _dry_run(max_campaign_name_length=3)
    assert not result.valid
    assert any(error.code == "campaign_name_too_long" for error in result.errors)


def test_multiple_violations_all_reported() -> None:
    result = _dry_run(
        allowed_objectives=("BRAND_AWARENESS",),
        max_total_budget_minor=1,
        allowed_currencies=("EUR",),
    )
    codes = {error.code for error in result.errors}
    assert {"objective_not_allowed", "budget_over_limit", "currency_not_allowed"} <= codes


def test_dry_run_result_is_frozen_and_serializable() -> None:
    result = _dry_run()
    document = result.to_document(proposal_id=make_proposal().proposal_id)
    assert document["schema_version"] == "1.0"
    assert document["valid"] is True
    assert document["request_fingerprint"] == result.request_fingerprint
