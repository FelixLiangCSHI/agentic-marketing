"""Versioned job/asset contracts and the idempotency key scheme.

``idempotency_key = run_id_node_id_input_hash`` binds a media job to the
workflow run and node that requested it, so retries and worker restarts
can always reconcile instead of creating duplicate provider jobs.
"""

from __future__ import annotations

import hashlib
import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr

MediaFormat = Literal["png", "jpeg", "webp"]
JobState = Literal[
    "PENDING",
    "CREATED",
    "RUNNING",
    "COMPLETED",
    "FAILED",
    "CANCELLED",
    "NEEDS_RECONCILE",
]

_FORMAT_MIME: dict[str, str] = {
    "png": "image/png",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
}


def mime_for_format(fmt: MediaFormat) -> str:
    return _FORMAT_MIME[fmt]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"


class MediaJobRequestV1(_Model):
    """One image generation request derived from a workflow node."""

    request_id: Annotated[StrictStr, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")]
    run_id: Annotated[StrictStr, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")]
    node_id: Annotated[StrictStr, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")]
    tenant: Annotated[StrictStr, Field(min_length=1, max_length=128)]
    prompt: Annotated[StrictStr, Field(min_length=1, max_length=8000)]
    output_format: MediaFormat
    image_count: Annotated[StrictInt, Field(ge=1, le=8)]

    def input_hash(self) -> str:
        payload = json.dumps(self.model_dump(mode="json"), sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def idempotency_key(self) -> str:
        """``run_id_node_id_input_hash`` per the parent-plan retry policy."""
        return f"{self.run_id}_{self.node_id}_{self.input_hash()[:32]}"


class JobRecordV1(BaseModel):
    """Persisted job state; survives worker restarts (mutable by store)."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    idempotency_key: StrictStr
    request_hash: StrictStr
    provider_job_id: StrictStr | None = None
    state: JobState = "PENDING"
    polls: StrictInt = 0
    error_code: StrictStr | None = None
    asset_object_key: StrictStr | None = None
    asset_object_version: StrictInt | None = None
    asset_sha256: StrictStr | None = None


class GeneratedAssetV1(_Model):
    """A validated, object-store-imported generated asset (not approved)."""

    request_id: StrictStr
    provider_job_id: StrictStr
    object_key: StrictStr
    object_version: StrictInt
    sha256: Annotated[StrictStr, Field(pattern=r"^[0-9a-f]{64}$")]
    provider_response_hash: Annotated[StrictStr, Field(pattern=r"^[0-9a-f]{64}$")]
    content_type: StrictStr
    size_bytes: Annotated[StrictInt, Field(ge=1)]


def request_hash(request: MediaJobRequestV1, *, model_id: str, config_hash: str) -> str:
    payload = json.dumps(
        {
            "request": request.model_dump(mode="json"),
            "model_id": model_id,
            "config_hash": config_hash,
        },
        sort_keys=True,
    )
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()
