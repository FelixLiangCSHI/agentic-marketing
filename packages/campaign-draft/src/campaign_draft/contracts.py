"""Typed contracts for the ``CampaignProposal`` draft (v1).

Mirrors ``packages/domain-contracts/schemas/campaign-proposal.v1.schema.json``.
A proposal is a frozen, server-side artifact: money lives in integer minor
units, every bound field is sealed into ``input_hash``, and any change of
any bound field yields a new hash / proposal id / version — never an
in-place edit. Status here is always ``DRAFT``; later lifecycle states
(``SUPERSEDED`` / ``INVALIDATED``) are ledger transitions, not edits.
"""

from __future__ import annotations

import hashlib
import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr

SCHEMA_VERSION = "1.0"

ID_PATTERN = r"^[a-z0-9][a-z0-9_-]{0,63}$"
HASH_PATTERN = r"^sha256:[a-f0-9]{64}$"
DATETIME_PATTERN = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$"
PROPOSAL_ID_PATTERN = r"^cpr_[a-f0-9]{24}$"
PACKAGE_ID_PATTERN = r"^acp_[a-f0-9]{24}$"

Identifier = Annotated[StrictStr, Field(pattern=ID_PATTERN)]
Sha256Hash = Annotated[StrictStr, Field(pattern=HASH_PATTERN)]
IsoDatetime = Annotated[StrictStr, Field(pattern=DATETIME_PATTERN)]

Channel = Literal["linkedin", "google_ads"]
Market = Literal["US", "CN"]
Objective = Literal[
    "LEAD_GENERATION",
    "BRAND_AWARENESS",
    "WEBSITE_VISITS",
    "ENGAGEMENT",
    "CONVERSIONS",
]
ProposalStatus = Literal["DRAFT", "SUPERSEDED", "INVALIDATED"]

# Supported currencies mapped to their minor-unit exponent. Anything else
# is rejected — never guessed.
SUPPORTED_CURRENCIES: dict[str, int] = {
    "USD": 2,
    "EUR": 2,
    "GBP": 2,
    "CNY": 2,
}


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class ProposalBudgetV1(_Frozen):
    """Budget in integer minor units — no floats, no NaN, no negatives."""

    currency: Annotated[StrictStr, Field(pattern=r"^[A-Z]{3}$")]
    total_limit_minor: Annotated[StrictInt, Field(ge=1)]
    daily_limit_minor: Annotated[StrictInt, Field(ge=1)] | None


class ProposalScheduleV1(_Frozen):
    timezone: Annotated[StrictStr, Field(min_length=1, max_length=64)]
    start_at: IsoDatetime
    end_at: IsoDatetime


class ProposalAudienceV1(_Frozen):
    markets: Annotated[tuple[Market, ...], Field(min_length=1)]
    excluded_segments: tuple[Annotated[StrictStr, Field(min_length=1, max_length=200)], ...]


class CampaignProposalV1(_Frozen):
    """Immutable, versioned, hash-sealed campaign draft proposal."""

    schema_version: Literal["1.0"]
    proposal_id: Annotated[StrictStr, Field(pattern=PROPOSAL_ID_PATTERN)]
    version: Annotated[StrictInt, Field(ge=1)]
    status: ProposalStatus
    tenant_id: Identifier
    run_id: Identifier
    content_package_id: Annotated[StrictStr, Field(pattern=PACKAGE_ID_PATTERN)]
    content_package_hash: Sha256Hash
    channel: Channel
    account_id: Identifier
    objective: Objective
    campaign_name: Annotated[StrictStr, Field(min_length=1, max_length=255)]
    budget: ProposalBudgetV1
    schedule: ProposalScheduleV1
    audience: ProposalAudienceV1
    channel_variant_refs: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    asset_hashes: tuple[Sha256Hash, ...]
    policy_version: Annotated[StrictStr, Field(min_length=1, max_length=64)]
    workflow_version: Annotated[StrictStr, Field(min_length=1, max_length=64)]
    input_hash: Sha256Hash
    warnings: tuple[Annotated[StrictStr, Field(min_length=1, max_length=500)], ...]
    created_by: Identifier
    created_at: IsoDatetime


def canonical_input_hash(
    *,
    content_package_hash: str,
    tenant_id: str,
    channel: str,
    account_id: str,
    objective: str,
    campaign_name: str,
    budget: ProposalBudgetV1,
    schedule: ProposalScheduleV1,
    audience: ProposalAudienceV1,
    channel_variant_refs: tuple[str, ...],
    asset_hashes: tuple[str, ...],
    policy_version: str,
    workflow_version: str,
) -> str:
    """Canonical hash over every field bound to an approval.

    Any change to any bound field changes this hash, forcing a new
    proposal version and invalidating prior approvals. The clock and
    other unbound metadata are deliberately excluded so that the same
    input is deterministic.
    """
    document = {
        "content_package_hash": content_package_hash,
        "tenant_id": tenant_id,
        "channel": channel,
        "account_id": account_id,
        "objective": objective,
        "campaign_name": campaign_name,
        "budget": budget.model_dump(mode="json"),
        "schedule": schedule.model_dump(mode="json"),
        "audience": audience.model_dump(mode="json"),
        "channel_variant_refs": list(channel_variant_refs),
        "asset_hashes": list(asset_hashes),
        "policy_version": policy_version,
        "workflow_version": workflow_version,
    }
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def proposal_id_for(input_hash: str, version: int) -> str:
    """Stable proposal id derived from the input hash and version."""
    digest = hashlib.sha256(f"{input_hash}|v{version}".encode("utf-8")).hexdigest()
    return "cpr_" + digest[:24]
