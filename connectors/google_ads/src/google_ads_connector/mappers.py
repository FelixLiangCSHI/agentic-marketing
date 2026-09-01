"""Proposal -> Google Ads campaign mutate mapper (verified fields only).

Emits the minimal mutate-shaped request. Customer and login-customer IDs
are carried as ``config://`` references — literal account IDs never enter
the request document built in this repo (protected jobs resolve them at
the proxy boundary). Objectives without a recorded official-doc mapping
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

from google_ads_connector.config import GoogleAdsConnectorConfig

# Internal objective -> provider objective marker. Only entries verified
# against the recorded official documentation may appear here; everything
# else must fail closed with verification_required.
VERIFIED_OBJECTIVE_MAP: dict[str, str] = {
    "LEAD_GENERATION": "LEAD_GENERATION",
    "BRAND_AWARENESS": "BRAND_AWARENESS",
    "WEBSITE_VISITS": "WEBSITE_TRAFFIC",
}


class VerificationRequiredMappingError(ConnectorSdkError):
    """The field/value lacks recorded official verification; fail closed."""

    code = "verification_required"


@dataclass(frozen=True)
class MappedCampaignMutate:
    """The mutate-shaped request plus its audit digest."""

    mutate_request: Mapping[str, Any]
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


def map_campaign_mutate(
    *, proposal: CampaignProposalV1, config: GoogleAdsConnectorConfig
) -> MappedCampaignMutate:
    """Map a frozen proposal onto the minimal verified mutate request."""
    provider_objective = VERIFIED_OBJECTIVE_MAP.get(proposal.objective)
    if provider_objective is None:
        raise VerificationRequiredMappingError(
            f"objective {proposal.objective} has no officially verified provider mapping"
        )
    mutate_request: dict[str, Any] = {
        "customer_id_ref": config.account.customer_id_ref,
        "login_customer_id_ref": config.account.login_customer_id_ref,
        "operations": [
            {
                "create": {
                    "name": proposal.campaign_name,
                    "objective": provider_objective,
                    "status": "PAUSED",
                    "budget": {
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
                    "schedule": {
                        "start_at": proposal.schedule.start_at,
                        "end_at": proposal.schedule.end_at,
                        "timezone": proposal.schedule.timezone,
                    },
                    "geo_targets": list(proposal.audience.markets),
                }
            }
        ],
    }
    return MappedCampaignMutate(
        mutate_request=mutate_request,
        request_hash=_canonical_digest(mutate_request),
        api_version_ref=config.endpoint.api_version_ref,
    )
