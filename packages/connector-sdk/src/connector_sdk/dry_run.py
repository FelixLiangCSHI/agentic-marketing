"""Side-effect-free channel dry-run (100% interception, zero external calls).

``run_dry_run`` is pure deterministic code: it validates a frozen
:class:`CampaignProposalV1` against a versioned :class:`ChannelPolicy`
and returns every violation as a structured error. It never talks to a
provider — the request fingerprint lets later execution prove it sends
exactly what was previewed.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

import pydantic

from campaign_draft import CampaignProposalV1


class _Frozen(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid", frozen=True)


class ChannelPolicy(_Frozen):
    """Versioned per-channel constraints used by the shared dry-run."""

    policy_version: str = pydantic.Field(min_length=1, max_length=64)
    channel: str = pydantic.Field(min_length=1)
    known_accounts: tuple[str, ...]
    allowed_objectives: tuple[str, ...]
    allowed_currencies: tuple[str, ...]
    max_total_budget_minor: int = pydantic.Field(ge=1)
    max_daily_budget_minor: int = pydantic.Field(ge=1)
    allowed_markets: tuple[str, ...]
    max_duration_days: int = pydantic.Field(ge=1)
    max_campaign_name_length: int = pydantic.Field(ge=1)


class DryRunError(_Frozen):
    """A single structured interception; ``code`` is stable and machine-readable."""

    code: str = pydantic.Field(pattern=r"^[a-z0-9][a-z0-9_]{1,63}$")
    message: str = pydantic.Field(min_length=1, max_length=500)
    field: str = pydantic.Field(min_length=1, max_length=200)


class DryRunResult(_Frozen):
    """Outcome of a side-effect-free dry-run."""

    valid: bool
    errors: tuple[DryRunError, ...]
    warnings: tuple[str, ...]
    normalized_request: dict[str, Any]
    request_fingerprint: str = pydantic.Field(pattern=r"^sha256:[0-9a-f]{64}$")
    policy_version: str
    evaluated_at: str

    def to_document(self, *, proposal_id: str) -> dict[str, Any]:
        """Serialize to the ``campaign-dry-run.v1`` contract shape."""
        return {
            "schema_version": "1.0",
            "proposal_id": proposal_id,
            "policy_version": self.policy_version,
            "valid": self.valid,
            "request_fingerprint": self.request_fingerprint,
            "errors": [error.model_dump(mode="json") for error in self.errors],
            "warnings": list(self.warnings),
            "evaluated_at": self.evaluated_at,
        }


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _fingerprint(normalized_request: dict[str, Any]) -> str:
    canonical = json.dumps(
        normalized_request, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def run_dry_run(
    *,
    proposal: CampaignProposalV1,
    policy: ChannelPolicy,
    as_of: str,
) -> DryRunResult:
    """Validate ``proposal`` against ``policy``; report every violation."""
    errors: list[DryRunError] = []

    def intercept(code: str, field: str, message: str) -> None:
        errors.append(DryRunError(code=code, message=message, field=field))

    if proposal.channel != policy.channel:
        intercept(
            "channel_mismatch",
            "channel",
            f"proposal channel {proposal.channel} does not match policy channel {policy.channel}",
        )
    if proposal.account_id not in policy.known_accounts:
        intercept("account_unknown", "account_id", "account is not on the known-accounts list")
    if proposal.objective not in policy.allowed_objectives:
        intercept(
            "objective_not_allowed",
            "objective",
            f"objective {proposal.objective} is not allowed by policy",
        )
    if proposal.budget.currency not in policy.allowed_currencies:
        intercept(
            "currency_not_allowed",
            "budget.currency",
            f"currency {proposal.budget.currency} is not allowed by policy",
        )
    if proposal.budget.total_limit_minor > policy.max_total_budget_minor:
        intercept(
            "budget_over_limit",
            "budget.total_limit_minor",
            "total budget exceeds the policy cap",
        )
    if (
        proposal.budget.daily_limit_minor is not None
        and proposal.budget.daily_limit_minor > policy.max_daily_budget_minor
    ):
        intercept(
            "daily_budget_over_limit",
            "budget.daily_limit_minor",
            "daily budget exceeds the policy cap",
        )
    for market in proposal.audience.markets:
        if market not in policy.allowed_markets:
            intercept(
                "market_not_allowed",
                "audience.markets",
                f"market {market} is not allowed by policy",
            )
    start_at = _parse_utc(proposal.schedule.start_at)
    end_at = _parse_utc(proposal.schedule.end_at)
    now = _parse_utc(as_of)
    if start_at < now:
        intercept(
            "schedule_start_in_past",
            "schedule.start_at",
            "campaign start is in the past",
        )
    duration_days = (end_at - start_at).total_seconds() / 86400
    if duration_days > policy.max_duration_days:
        intercept(
            "schedule_too_long",
            "schedule.end_at",
            "campaign duration exceeds the policy maximum",
        )
    if len(proposal.campaign_name) > policy.max_campaign_name_length:
        intercept(
            "campaign_name_too_long",
            "campaign_name",
            "campaign name exceeds the channel limit",
        )

    normalized_request: dict[str, Any] = {
        "channel": proposal.channel,
        "account_id": proposal.account_id,
        "objective": proposal.objective,
        "campaign_name": proposal.campaign_name,
        "budget": proposal.budget.model_dump(mode="json"),
        "schedule": proposal.schedule.model_dump(mode="json"),
        "audience": proposal.audience.model_dump(mode="json"),
        "channel_variant_refs": list(proposal.channel_variant_refs),
        "content_package_hash": proposal.content_package_hash,
        "input_hash": proposal.input_hash,
        "policy_version": policy.policy_version,
    }

    return DryRunResult(
        valid=not errors,
        errors=tuple(errors),
        warnings=(),
        normalized_request=normalized_request,
        request_fingerprint=_fingerprint(normalized_request),
        policy_version=policy.policy_version,
        evaluated_at=as_of,
    )
