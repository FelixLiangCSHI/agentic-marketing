"""Deterministic Campaign Draft builder (Phase 03 / Subphase 01).

``build_campaign_draft`` is an L1 operation with zero external side
effects: it consumes only an ``APPROVED``, unexpired, hash-matching
``ApprovedContentPackage`` (via the Phase 02 consumption gate), normalizes
the request (Decimal → integer minor units, IANA timezone, market subset)
and seals every bound field into a canonical ``input_hash``. The result is
always ``DRAFT``; no channel API is ever called here.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated
from zoneinfo import ZoneInfoNotFoundError, available_timezones

from content_package import ApprovedContentPackageV1, consumable
from content_package.temporal import parse_utc
from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator

from campaign_draft.contracts import (
    SUPPORTED_CURRENCIES,
    CampaignProposalV1,
    Channel,
    Identifier,
    IsoDatetime,
    Market,
    Objective,
    ProposalAudienceV1,
    ProposalBudgetV1,
    ProposalScheduleV1,
    canonical_input_hash,
    proposal_id_for,
)


class DraftError(Exception):
    """Base class for structured, auditable draft rejections."""


class PackageNotConsumableError(DraftError):
    """Package is not APPROVED / expired / revoked / tampered."""


class PackageHashMismatchError(DraftError):
    """The expected content hash does not match the sealed package hash."""


class MissingChannelVariantError(DraftError):
    """The approved package has no variant for the requested channel."""


class BudgetError(DraftError):
    """Budget is negative, non-finite, over-precise or unsupported."""


class ScheduleError(DraftError):
    """Timezone or time window is invalid or outside package validity."""


class AudienceError(DraftError):
    """Markets fall outside the package's approved market."""


class DraftRequest(BaseModel):
    """Validated, normalized draft input. Unknown fields are rejected.

    Money fields are strict ``Decimal``; floats never enter the model.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    tenant_id: Identifier
    run_id: Identifier
    requester_id: Identifier
    channel: Channel
    account_id: Identifier
    objective: Objective
    campaign_name: Annotated[StrictStr, Field(min_length=1, max_length=255)]
    currency: Annotated[StrictStr, Field(pattern=r"^[A-Z]{3}$")]
    total_limit: Decimal
    daily_limit: Decimal | None
    timezone: Annotated[StrictStr, Field(min_length=1, max_length=64)]
    start_at: IsoDatetime
    end_at: IsoDatetime
    markets: Annotated[tuple[Market, ...], Field(min_length=1)]
    excluded_segments: tuple[
        Annotated[StrictStr, Field(min_length=1, max_length=200)], ...
    ]
    policy_version: Annotated[StrictStr, Field(min_length=1, max_length=64)]
    workflow_version: Annotated[StrictStr, Field(min_length=1, max_length=64)]

    @field_validator("total_limit", "daily_limit")
    @classmethod
    def _finite(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and not value.is_finite():
            raise ValueError("budget amounts must be finite decimals")
        return value


def _to_minor_units(amount: Decimal, currency: str, *, field: str) -> int:
    exponent = SUPPORTED_CURRENCIES.get(currency)
    if exponent is None:
        raise BudgetError(f"unsupported currency: {currency}")
    if not amount.is_finite():
        raise BudgetError(f"{field} must be a finite decimal")
    if amount <= 0:
        raise BudgetError(f"{field} must be > 0")
    quantum = Decimal(1).scaleb(-exponent)
    minor = amount / quantum
    if minor != minor.to_integral_value():
        raise BudgetError(
            f"{field} has sub-minor-unit precision for {currency}: {amount}"
        )
    return int(minor)


def _normalize_budget(request: DraftRequest) -> ProposalBudgetV1:
    total_minor = _to_minor_units(
        request.total_limit, request.currency, field="total_limit"
    )
    daily_minor: int | None = None
    if request.daily_limit is not None:
        daily_minor = _to_minor_units(
            request.daily_limit, request.currency, field="daily_limit"
        )
        if daily_minor > total_minor:
            raise BudgetError("daily_limit cannot exceed total_limit")
    return ProposalBudgetV1(
        currency=request.currency,
        total_limit_minor=total_minor,
        daily_limit_minor=daily_minor,
    )


def _normalize_schedule(
    request: DraftRequest, package: ApprovedContentPackageV1, *, as_of: str
) -> ProposalScheduleV1:
    try:
        if request.timezone not in available_timezones():
            raise ZoneInfoNotFoundError(request.timezone)
    except ZoneInfoNotFoundError as exc:
        raise ScheduleError(f"unknown IANA timezone: {request.timezone}") from exc
    start = parse_utc(request.start_at)
    end = parse_utc(request.end_at)
    if end <= start:
        raise ScheduleError("end_at must be after start_at")
    if start < parse_utc(as_of):
        raise ScheduleError("start_at must not be in the past")
    if end > parse_utc(package.expires_at):
        raise ScheduleError("schedule ends after the approved package expires")
    return ProposalScheduleV1(
        timezone=request.timezone,
        start_at=request.start_at,
        end_at=request.end_at,
    )


def _normalize_audience(
    request: DraftRequest, package: ApprovedContentPackageV1
) -> ProposalAudienceV1:
    outside = [market for market in request.markets if market != package.market]
    if outside:
        raise AudienceError(
            f"markets {outside} are outside the package's approved market "
            f"{package.market}"
        )
    return ProposalAudienceV1(
        markets=tuple(sorted(set(request.markets))),
        excluded_segments=tuple(sorted(set(request.excluded_segments))),
    )


def _channel_variant_refs(
    request: DraftRequest, package: ApprovedContentPackageV1
) -> tuple[str, ...]:
    for channel, refs in package.channel_variants:
        if channel == request.channel and refs:
            return tuple(refs)
    raise MissingChannelVariantError(
        f"approved package has no channel variant for {request.channel}"
    )


def build_campaign_draft(
    *,
    package: ApprovedContentPackageV1,
    expected_content_hash: str,
    request: DraftRequest,
    as_of: str,
    previous: CampaignProposalV1 | None = None,
    ledger_status: str | None = None,
    product_status: str = "APPROVED",
) -> CampaignProposalV1:
    """Build a deterministic ``DRAFT`` proposal — no external objects.

    Same input + versions + fake clock ⇒ same ``input_hash`` and
    ``proposal_id``. Passing ``previous`` gives idempotent rebuilds for
    unchanged input and a new version (``previous.version + 1``) when any
    bound field changed.
    """
    if package.content_hash != expected_content_hash:
        raise PackageHashMismatchError(
            "expected content hash does not match the approved package"
        )
    if request.tenant_id != package.tenant_id:
        raise PackageNotConsumableError(
            "request tenant does not own the approved package"
        )
    ok, reason = consumable(
        package,
        as_of=as_of,
        ledger_status=ledger_status,
        product_status=product_status,
    )
    if not ok:
        raise PackageNotConsumableError(reason)

    budget = _normalize_budget(request)
    schedule = _normalize_schedule(request, package, as_of=as_of)
    audience = _normalize_audience(request, package)
    variant_refs = _channel_variant_refs(request, package)

    input_hash = canonical_input_hash(
        content_package_hash=package.content_hash,
        tenant_id=request.tenant_id,
        channel=request.channel,
        account_id=request.account_id,
        objective=request.objective,
        campaign_name=request.campaign_name,
        budget=budget,
        schedule=schedule,
        audience=audience,
        channel_variant_refs=variant_refs,
        asset_hashes=tuple(package.asset_hashes),
        policy_version=request.policy_version,
        workflow_version=request.workflow_version,
    )

    if previous is not None and previous.input_hash == input_hash:
        return previous
    version = 1 if previous is None else previous.version + 1

    return CampaignProposalV1(
        schema_version="1.0",
        proposal_id=proposal_id_for(input_hash, version),
        version=version,
        status="DRAFT",
        tenant_id=request.tenant_id,
        run_id=request.run_id,
        content_package_id=package.package_id,
        content_package_hash=package.content_hash,
        channel=request.channel,
        account_id=request.account_id,
        objective=request.objective,
        campaign_name=request.campaign_name,
        budget=budget,
        schedule=schedule,
        audience=audience,
        channel_variant_refs=variant_refs,
        asset_hashes=tuple(package.asset_hashes),
        policy_version=request.policy_version,
        workflow_version=request.workflow_version,
        input_hash=input_hash,
        warnings=(),
        created_by=request.requester_id,
        created_at=as_of,
    )
