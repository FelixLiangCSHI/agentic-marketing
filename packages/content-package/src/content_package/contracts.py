"""Typed contracts for the immutable ``ApprovedContentPackage`` (v1).

The authoritative structure comes from the phase plan §6.12: a package is
only assembled server-side, binds claims to source versions and excerpt
hashes, carries the compliance result and human approvals, and is sealed
by a canonical content hash. Instances are frozen; any change of any
bound field yields a different ``content_hash`` and therefore a new
version — never an in-place edit.
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
PACKAGE_ID_PATTERN = r"^acp_[a-f0-9]{24}$"

Identifier = Annotated[StrictStr, Field(pattern=ID_PATTERN)]
Sha256Hash = Annotated[StrictStr, Field(pattern=HASH_PATTERN)]
IsoDatetime = Annotated[StrictStr, Field(pattern=DATETIME_PATTERN)]

Market = Literal["US", "CN"]
PackageStatus = Literal["APPROVED", "SUPERSEDED", "REVOKED"]
ReviewTrack = Literal["medical", "marketing"]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class ClaimBindingV1(_Frozen):
    """A claim bound to the exact source version and excerpt hash."""

    text: Annotated[StrictStr, Field(min_length=1, max_length=4000)]
    source_id: Identifier
    source_version: StrictStr
    source_excerpt_hash: Sha256Hash
    expires_at: IsoDatetime | None


class PackageApprovalV1(_Frozen):
    """One human approval track, bound to the reviewed artifact hash."""

    track: ReviewTrack
    approval_id: StrictStr
    approved_by: Identifier
    approved_at: IsoDatetime
    artifact_hash: Sha256Hash


class VersionBindingsV1(_Frozen):
    """Every version that shaped the content, sealed into the hash."""

    policy_version: StrictStr
    prompt_version: StrictStr
    model_id: StrictStr
    workflow_version: StrictStr
    skill_versions: tuple[tuple[StrictStr, StrictStr], ...]


class ApprovedContentPackageV1(_Frozen):
    """Immutable, versioned, hash-sealed approved content package."""

    schema_version: Literal["1.0"]
    package_id: Annotated[StrictStr, Field(pattern=PACKAGE_ID_PATTERN)]
    version: Annotated[StrictInt, Field(ge=1)]
    status: PackageStatus
    tenant_id: Identifier
    product_id: Identifier
    market: Market
    locale: StrictStr
    target_audience: tuple[StrictStr, ...]
    channel_variants: tuple[tuple[StrictStr, tuple[StrictStr, ...]], ...]
    asset_uris: tuple[StrictStr, ...]
    asset_hashes: tuple[Sha256Hash, ...]
    claims: tuple[ClaimBindingV1, ...]
    compliance_result_id: StrictStr
    versions: VersionBindingsV1
    approvals: tuple[PackageApprovalV1, ...]
    approved_at: IsoDatetime
    expires_at: IsoDatetime
    content_hash: Sha256Hash

    def package_hash(self) -> str:
        """Hash of the whole package document (audit fingerprint)."""
        payload = self.model_dump(mode="json")
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def canonical_content_hash(
    *,
    copy_hash: str,
    tenant_id: str,
    claims: tuple[ClaimBindingV1, ...],
    asset_hashes: tuple[str, ...],
    versions: VersionBindingsV1,
    channel_variants: tuple[tuple[str, tuple[str, ...]], ...],
) -> str:
    """Canonical hash binding content, claims, assets and versions.

    Any change to any bound field changes this hash, which forces a new
    package version and invalidates prior approvals (they are bound to the
    old artifact hash).
    """
    document = {
        "copy_hash": copy_hash,
        "tenant_id": tenant_id,
        "claims": [
            {
                "text": claim.text,
                "source_id": claim.source_id,
                "source_version": claim.source_version,
                "source_excerpt_hash": claim.source_excerpt_hash,
            }
            for claim in claims
        ],
        "asset_hashes": sorted(asset_hashes),
        "versions": versions.model_dump(mode="json"),
        "channel_variants": [
            [channel, list(content_ids)]
            for channel, content_ids in channel_variants
        ],
    }
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def package_id_for(content_hash: str, version: int) -> str:
    digest = hashlib.sha256(f"{content_hash}|{version}".encode("utf-8"))
    return "acp_" + digest.hexdigest()[:24]
