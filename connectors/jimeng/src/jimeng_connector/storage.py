"""Asset import: validate then store; generated/approved paths separated.

Validation order after download: TLS verified, MIME allowlist, size cap,
provider hash match, malware scan — any failure is a typed error and
nothing is stored. Imports go to the ``generated`` area; promotion copies
into the separate ``approved`` area. Object versions are immutable
(enforced by :class:`infra_core.objectstore.FakeObjectStore`), so any
modification creates a new version — never an in-place edit.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from infra_core.objectstore import ObjectKey, ObjectStore
from jimeng_connector.contracts import GeneratedAssetV1, MediaJobRequestV1
from jimeng_connector.errors import AssetValidationError, MalwareRejectedError
from jimeng_connector.transport import (
    MALWARE_MARKER,
    DownloadedAsset,
    ProviderResult,
)

ALLOWED_MIME = frozenset({"image/png", "image/jpeg", "image/webp"})
MAX_ASSET_BYTES = 10 * 1024 * 1024

GENERATED_AGENT = "content-agent-generated"
APPROVED_AGENT = "content-agent-approved"


def synthetic_malware_scan(data: bytes, _content_type: str) -> bool:
    """Fake DLP/Malware hook: rejects the synthetic malware marker."""
    return MALWARE_MARKER not in data


@dataclass
class AssetImporter:
    """Validates downloaded assets and imports them into the object store."""

    store: ObjectStore
    environment: str

    def import_generated(
        self,
        request: MediaJobRequestV1,
        result: ProviderResult,
        downloaded: DownloadedAsset,
    ) -> GeneratedAssetV1:
        if not downloaded.tls_verified:
            raise AssetValidationError("download was not TLS-verified; rejecting asset")
        if downloaded.content_type not in ALLOWED_MIME:
            raise AssetValidationError(
                f"content type {downloaded.content_type!r} is not an allowed image MIME"
            )
        if not downloaded.data:
            raise AssetValidationError("downloaded asset is empty")
        if len(downloaded.data) > MAX_ASSET_BYTES:
            raise AssetValidationError("downloaded asset exceeds the size limit")
        actual_hash = hashlib.sha256(downloaded.data).hexdigest()
        if actual_hash != result.content_sha256:
            raise AssetValidationError(
                "downloaded asset hash does not match the provider response hash"
            )
        if not synthetic_malware_scan(downloaded.data, downloaded.content_type):
            raise MalwareRejectedError("malware scan rejected the downloaded asset")
        key = ObjectKey(
            environment=self.environment,
            tenant=request.tenant,
            agent=GENERATED_AGENT,
            run_id=request.run_id,
            name=f"{request.node_id}-{result.provider_job_id}.{request.output_format}",
        )
        stored = self.store.put(key, downloaded.data, content_type=downloaded.content_type)
        return GeneratedAssetV1(
            request_id=request.request_id,
            provider_job_id=result.provider_job_id,
            object_key=stored.key,
            object_version=stored.version,
            sha256=stored.sha256,
            provider_response_hash=result.content_sha256,
            content_type=stored.content_type,
            size_bytes=stored.size,
        )

    def promote_to_approved(
        self, request: MediaJobRequestV1, asset: GeneratedAssetV1
    ) -> GeneratedAssetV1:
        """Copy a generated asset into the separate approved area.

        The generated original is untouched; the approved copy gets its
        own key/version so later re-approvals create new versions.
        """
        source_key = ObjectKey(
            environment=self.environment,
            tenant=request.tenant,
            agent=GENERATED_AGENT,
            run_id=request.run_id,
            name=asset.object_key.rsplit("/", 1)[-1],
        )
        stored_source = self.store.get(source_key, version=asset.object_version)
        approved_key = ObjectKey(
            environment=self.environment,
            tenant=request.tenant,
            agent=APPROVED_AGENT,
            run_id=request.run_id,
            name=asset.object_key.rsplit("/", 1)[-1],
        )
        stored = self.store.put(
            approved_key, stored_source.data, content_type=stored_source.content_type
        )
        return GeneratedAssetV1(
            request_id=asset.request_id,
            provider_job_id=asset.provider_job_id,
            object_key=stored.key,
            object_version=stored.version,
            sha256=stored.sha256,
            provider_response_hash=asset.provider_response_hash,
            content_type=stored.content_type,
            size_bytes=stored.size,
        )
