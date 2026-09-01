"""RED tests: request normalization — budget, currency, timezone, market.

Money is Decimal converted to integer minor units; floats, NaN, negative
and unsupported currencies are rejected. Timezones must exist in the IANA
database. Markets must stay inside the package's approved market.
"""

from __future__ import annotations

from decimal import Decimal

import pydantic
import pytest

from campaign_draft import (
    AudienceError,
    BudgetError,
    ScheduleError,
    build_campaign_draft,
)

from builders import FAKE_NOW, load_package, make_request


def _build(request_overrides: dict[str, object]) -> object:
    package = load_package()
    return build_campaign_draft(
        package=package,
        expected_content_hash=package.content_hash,
        request=make_request(**request_overrides),
        as_of=FAKE_NOW,
    )


def test_budget_is_stored_in_integer_minor_units() -> None:
    proposal = _build({"total_limit": Decimal("1000.50"), "daily_limit": Decimal("99.99")})
    assert proposal.budget.total_limit_minor == 100050  # type: ignore[attr-defined]
    assert proposal.budget.daily_limit_minor == 9999  # type: ignore[attr-defined]
    assert proposal.budget.currency == "USD"  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "value",
    [Decimal("-1"), Decimal("0"), Decimal("NaN"), Decimal("Infinity")],
)
def test_non_positive_or_non_finite_total_budget_rejected(value: Decimal) -> None:
    with pytest.raises((BudgetError, pydantic.ValidationError)):
        _build({"total_limit": value})


def test_float_budget_rejected() -> None:
    with pytest.raises(pydantic.ValidationError):
        make_request(total_limit=1000.5)  # type: ignore[arg-type]


def test_sub_minor_unit_precision_rejected() -> None:
    with pytest.raises(BudgetError):
        _build({"total_limit": Decimal("10.001")})


def test_unsupported_currency_rejected() -> None:
    with pytest.raises((BudgetError, pydantic.ValidationError)):
        _build({"currency": "XXX"})


def test_daily_limit_above_total_rejected() -> None:
    with pytest.raises(BudgetError):
        _build({"total_limit": Decimal("10"), "daily_limit": Decimal("100")})


def test_unknown_timezone_rejected() -> None:
    with pytest.raises(ScheduleError):
        _build({"timezone": "Mars/Olympus_Mons"})


def test_end_before_start_rejected() -> None:
    with pytest.raises(ScheduleError):
        _build({"start_at": "2026-10-01T00:00:00Z", "end_at": "2026-09-01T00:00:00Z"})


def test_start_in_the_past_rejected() -> None:
    with pytest.raises(ScheduleError):
        _build({"start_at": "2026-01-01T00:00:00Z", "end_at": "2026-10-01T00:00:00Z"})


def test_schedule_beyond_package_expiry_rejected() -> None:
    with pytest.raises(ScheduleError):
        _build({"end_at": "2028-01-01T00:00:00Z"})


def test_market_outside_package_market_rejected() -> None:
    with pytest.raises((AudienceError, pydantic.ValidationError)):
        _build({"markets": ("CN",)})


def test_empty_markets_rejected() -> None:
    with pytest.raises((AudienceError, pydantic.ValidationError)):
        _build({"markets": ()})


def test_unknown_request_field_rejected() -> None:
    with pytest.raises(pydantic.ValidationError):
        make_request(auto_increase_budget=True)
