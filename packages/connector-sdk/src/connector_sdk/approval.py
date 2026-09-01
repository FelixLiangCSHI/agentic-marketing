"""Connector-side approval hash re-verification (defence in depth).

The activation worker already consumes a hash-bound approval token, but a
connector must never trust its caller blindly: before any external write
it recomputes the canonical input hash from the request's bound fields
and compares it with both the proposal's sealed ``input_hash`` and the
``input_hash`` the caller claims was approved. Any mismatch is a
non-retryable schema error — the write is never sent.
"""

from __future__ import annotations

from campaign_draft import CampaignProposalV1, canonical_input_hash

from connector_sdk.errors import SchemaInvalidError


def verify_approved_input(
    proposal: CampaignProposalV1, *, input_hash: str
) -> None:
    """Fail closed unless the recomputed hash matches proposal and caller."""
    recomputed = canonical_input_hash(
        content_package_hash=proposal.content_package_hash,
        tenant_id=proposal.tenant_id,
        channel=proposal.channel,
        account_id=proposal.account_id,
        objective=proposal.objective,
        campaign_name=proposal.campaign_name,
        budget=proposal.budget,
        schedule=proposal.schedule,
        audience=proposal.audience,
        channel_variant_refs=proposal.channel_variant_refs,
        asset_hashes=proposal.asset_hashes,
        policy_version=proposal.policy_version,
        workflow_version=proposal.workflow_version,
    )
    if recomputed != proposal.input_hash:
        raise SchemaInvalidError(
            "proposal input_hash does not match its bound fields; refusing write"
        )
    if recomputed != input_hash:
        raise SchemaInvalidError(
            "approved input_hash does not match this request; refusing write"
        )
