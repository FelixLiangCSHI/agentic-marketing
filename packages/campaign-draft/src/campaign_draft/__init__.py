"""Campaign Draft domain (Phase 03 / Subphase 01).

Deterministic, hash-sealed ``CampaignProposal`` drafts built only from
``APPROVED``, unexpired, hash-matching content packages. No channel API
access lives in this package.
"""

from campaign_draft.builder import (
    AudienceError,
    BudgetError,
    DraftError,
    DraftRequest,
    MissingChannelVariantError,
    PackageHashMismatchError,
    PackageNotConsumableError,
    ScheduleError,
    build_campaign_draft,
)
from campaign_draft.contracts import (
    SCHEMA_VERSION,
    SUPPORTED_CURRENCIES,
    CampaignProposalV1,
    ProposalAudienceV1,
    ProposalBudgetV1,
    ProposalScheduleV1,
    canonical_input_hash,
    proposal_id_for,
)

__all__ = [
    "SCHEMA_VERSION",
    "SUPPORTED_CURRENCIES",
    "AudienceError",
    "BudgetError",
    "CampaignProposalV1",
    "DraftError",
    "DraftRequest",
    "MissingChannelVariantError",
    "PackageHashMismatchError",
    "PackageNotConsumableError",
    "ProposalAudienceV1",
    "ProposalBudgetV1",
    "ProposalScheduleV1",
    "ScheduleError",
    "build_campaign_draft",
    "canonical_input_hash",
    "proposal_id_for",
]
