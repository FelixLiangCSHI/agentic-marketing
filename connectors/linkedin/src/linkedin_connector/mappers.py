"""Proposal -> LinkedIn campaign resource mapper (verified fields only).

Only fields whose semantics are covered by the recorded official-doc
verification are emitted. Objectives without a verified provider mapping
raise ``verification_required`` instead of guessing. Request and response
digests (sha256 over canonical JSON) are kept for audit binding.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping

from campaign_draft import CampaignProposalV1

from connector_sdk.errors import ConnectorSdkError

# Internal objective -> provider objective type. Only entries verified
# against the recorded official documentation may appear here; everything
# else must fail closed with verification_required.
VERIFIED_OBJECTIVE_MAP: dict[str, str] = {
    "LEAD_GENERATION": "LEAD_GENERATION",
    "BRAND_AWARENESS": "BRAND_AWARENESS",
    "WEBSITE_VISITS": "WEBSITE_VISIT",
}


class VerificationRequiredMappingError(ConnectorSdkError):
    """The field/value lacks recorded official verification; fail closed."""

    code = "verification_required"


@dataclass(frozen=True)
class MappedCampaignRequest:
    """The provider-shaped resource plus its audit digest."""

    resource: Mapping[str, Any]
    request_hash: str
    api_version_ref: str


def _canonical_digest(document: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def response_digest(response: Mapping[str, Any]) -> str:
    """Stable sha256 digest of a provider response for audit binding."""
    return _canonical_digest(response)


def map_campaign_request(
    *, proposal: CampaignProposalV1, api_version: str
) -> MappedCampaignRequest:
    """Map a frozen proposal onto the minimal verified provider resource."""
    provider_objective = VERIFIED_OBJECTIVE_MAP.get(proposal.objective)
    if provider_objective is None:
        raise VerificationRequiredMappingError(
            f"objective {proposal.objective} has no officially verified provider mapping"
        )
    resource: dict[str, Any] = {
        "account": proposal.account_id,
        "name": proposal.campaign_name,
        "objective_type": provider_objective,
        "total_budget": {
            "amount_minor": proposal.budget.total_limit_minor,
            "currency": proposal.budget.currency,
        },
        "daily_budget": (
            {
                "amount_minor": proposal.budget.daily_limit_minor,
                "currency": proposal.budget.currency,
            }
            if proposal.budget.daily_limit_minor is not None
            else None
        ),
        "run_schedule": {
            "start_at": proposal.schedule.start_at,
            "end_at": proposal.schedule.end_at,
            "timezone": proposal.schedule.timezone,
        },
        "locale_targets": list(proposal.audience.markets),
        "status": "DRAFT",
    }
    return MappedCampaignRequest(
        resource=resource,
        request_hash=_canonical_digest(resource),
        api_version_ref=api_version,
    )
