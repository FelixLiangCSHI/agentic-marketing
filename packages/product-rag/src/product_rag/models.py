"""Runtime models mirroring the v1 product/content JSON Schemas.

Authoritative cross-language contracts live in
``packages/domain-contracts/schemas/*.v1.schema.json``. These Pydantic models
mirror them exactly (strict types, ``extra="forbid"``). Tests validate both
against the shared golden/invalid fixtures; do not loosen one side without
the other.

All free-text fields (``content``, ``claim_text``) are UNTRUSTED DATA: they
must be carried as data only and never interpreted as instructions.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr

ID_PATTERN = r"^[a-z0-9][a-z0-9_-]{0,63}$"
SEMVER_PATTERN = r"^\d+\.\d+\.\d+$"
DATETIME_PATTERN = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?Z$"
HASH_PATTERN = r"^sha256:[a-f0-9]{64}$"
LOCALE_PATTERN = r"^[a-z]{2}(-[A-Z]{2})?$"
CURSOR_PATTERN = r"^[A-Za-z0-9_-]{1,128}$"

Identifier = Annotated[StrictStr, Field(pattern=ID_PATTERN)]
SemVer = Annotated[StrictStr, Field(pattern=SEMVER_PATTERN)]
DateTimeUtc = Annotated[StrictStr, Field(pattern=DATETIME_PATTERN)]
Sha256Hash = Annotated[StrictStr, Field(pattern=HASH_PATTERN)]
Locale = Annotated[StrictStr, Field(pattern=LOCALE_PATTERN)]
Cursor = Annotated[StrictStr, Field(pattern=CURSOR_PATTERN)]

Market = Literal["US", "CN"]
ProductApprovalStatus = Literal["APPROVED", "DRAFT", "REVOKED"]
Classification = Literal["internal", "confidential-approved-for-provider"]
ProductChangeType = Literal["CREATED", "UPDATED", "REVOKED", "DELETED"]
ProductEntityType = Literal["document", "claim"]


class _ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: Literal["1.0"]


class ProductDocumentV1(_ContractModel):
    """Approved product source document. ``content`` is untrusted free text."""

    source_id: Identifier
    source_version: SemVer
    product_id: Identifier
    tenant: Identifier
    market: Market
    locale: Locale
    approval_status: ProductApprovalStatus
    approved_by: Identifier | None
    effective_from: DateTimeUtc
    expires_at: DateTimeUtc | None
    revoked_at: DateTimeUtc | None
    classification: Classification
    content_hash: Sha256Hash
    content: Annotated[StrictStr, Field(max_length=100000)]
    updated_at: DateTimeUtc


class ProductClaimV1(_ContractModel):
    """Approved product claim bound to its source document."""

    claim_id: Identifier
    product_id: Identifier
    tenant: Identifier
    market: Market
    locale: Locale
    claim_text: Annotated[StrictStr, Field(min_length=1, max_length=4000)]
    source_id: Identifier
    source_version: SemVer
    approval_status: ProductApprovalStatus
    approved_by: Identifier | None
    effective_from: DateTimeUtc
    expires_at: DateTimeUtc | None
    revoked_at: DateTimeUtc | None
    classification: Classification
    content_hash: Sha256Hash
    updated_at: DateTimeUtc


class ProductChangeV1(_ContractModel):
    """Single incremental product change feed event."""

    change_id: Identifier
    cursor: Cursor
    change_type: ProductChangeType
    entity_type: ProductEntityType
    entity_id: Identifier
    product_id: Identifier
    tenant: Identifier
    source_version: SemVer
    content_hash: Sha256Hash | None
    occurred_at: DateTimeUtc


class ProductRecord(BaseModel):
    """Package-internal product master summary returned by ``get_product``.

    Not a frozen cross-language contract yet; derived from approved
    documents. Do not add write fields.
    """

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    product_id: Identifier
    tenant: Identifier
    latest_approved_version: SemVer
    markets: tuple[Market, ...]
    locales: tuple[Locale, ...]
    updated_at: DateTimeUtc


class ChangePage(BaseModel):
    """Cursor page returned by ``get_changes``: deterministic and replayable."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    cursor: Cursor | None
    next_cursor: Cursor | None
    changes: tuple[ProductChangeV1, ...]
