"""Deterministic fake product adapter backed by synthetic JSON fixtures.

Used by unit/contract tests and local development. Behaviour mirrors the
frozen adapter contract:

* read-only; no write methods exist;
* default filters return only ``APPROVED``, effective, unexpired, unrevoked
  records whose tenant/market/locale match exactly;
* records failing contract validation or hash integrity are rejected at
  load time (never silently served);
* change pages are deterministic: replaying the same cursor returns the
  same page;
* free text is passed through verbatim as data — this adapter never parses
  or executes instructions found in product content.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from pathlib import Path

from pydantic import ValidationError

from product_rag.errors import (
    FixtureValidationError,
    InvalidCursorError,
    ProductIntegrityError,
    ProductNotFoundError,
    ProductVersionNotFoundError,
)
from product_rag.models import (
    ChangePage,
    Locale,
    Market,
    ProductChangeV1,
    ProductClaimV1,
    ProductDocumentV1,
    ProductRecord,
)

_DEFAULT_PAGE_SIZE = 100


def _is_effective(
    *,
    approval_status: str,
    effective_from: str,
    expires_at: str | None,
    revoked_at: str | None,
    as_of: str,
) -> bool:
    """Approved-and-valid gate. ISO-8601 UTC strings compare lexicographically."""
    if approval_status != "APPROVED":
        return False
    if revoked_at is not None:
        return False
    if effective_from > as_of:
        return False
    if expires_at is not None and expires_at <= as_of:
        return False
    return True


class FakeProductAdapter:
    """In-memory, deterministic implementation of the read-only adapter."""

    def __init__(
        self,
        *,
        documents: Sequence[ProductDocumentV1] = (),
        claims: Sequence[ProductClaimV1] = (),
        changes: Sequence[ProductChangeV1] = (),
        page_size: int = _DEFAULT_PAGE_SIZE,
    ) -> None:
        _check_hash_integrity(documents)
        self._documents = tuple(documents)
        self._claims = tuple(claims)
        # 变更流按 cursor 排序，保证 replay 确定性。
        self._changes = tuple(sorted(changes, key=lambda c: c.cursor))
        self._page_size = page_size

    @classmethod
    def from_fixture_dir(cls, fixture_dir: Path) -> "FakeProductAdapter":
        """Load synthetic fixtures; reject anything violating the contract."""

        def _load(name: str) -> list[dict[str, object]]:
            path = fixture_dir / name
            if not path.is_file():
                return []
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                raise FixtureValidationError(f"{name} must contain a JSON array")
            return data

        try:
            documents = [
                ProductDocumentV1.model_validate(entry)
                for entry in _load("documents.json")
            ]
            claims = [
                ProductClaimV1.model_validate(entry) for entry in _load("claims.json")
            ]
            changes = [
                ProductChangeV1.model_validate(entry)
                for entry in _load("changes.json")
            ]
        except ValidationError as exc:
            raise FixtureValidationError(
                f"fixture data violates the v1 product contracts: {exc}"
            ) from exc
        return cls(documents=documents, claims=claims, changes=changes)

    def get_product(
        self, product_id: str, version: str | None = None, *, tenant: str
    ) -> ProductRecord:
        docs = [
            doc
            for doc in self._documents
            if doc.product_id == product_id
            and doc.tenant == tenant
            and doc.approval_status == "APPROVED"
            and doc.revoked_at is None
        ]
        if not docs:
            raise ProductNotFoundError(
                f"no approved product {product_id!r} for this tenant"
            )
        if version is not None:
            docs = [doc for doc in docs if doc.source_version == version]
            if not docs:
                raise ProductVersionNotFoundError(
                    f"product {product_id!r} has no approved version {version!r}"
                )
        latest = max(docs, key=lambda d: _semver_key(d.source_version))
        markets: tuple[Market, ...] = tuple(sorted({doc.market for doc in docs}))
        locales: tuple[Locale, ...] = tuple(sorted({doc.locale for doc in docs}))
        return ProductRecord(
            product_id=product_id,
            tenant=tenant,
            latest_approved_version=latest.source_version,
            markets=markets,
            locales=locales,
            updated_at=max(doc.updated_at for doc in docs),
        )

    def list_approved_documents(
        self,
        product_id: str,
        market: str,
        locale: str,
        as_of: str,
        *,
        tenant: str,
    ) -> tuple[ProductDocumentV1, ...]:
        return tuple(
            doc
            for doc in self._documents
            if doc.product_id == product_id
            and doc.tenant == tenant
            and doc.market == market
            and doc.locale == locale
            and _is_effective(
                approval_status=doc.approval_status,
                effective_from=doc.effective_from,
                expires_at=doc.expires_at,
                revoked_at=doc.revoked_at,
                as_of=as_of,
            )
        )

    def get_claims(
        self,
        product_id: str,
        market: str,
        locale: str,
        as_of: str,
        *,
        tenant: str,
    ) -> tuple[ProductClaimV1, ...]:
        return tuple(
            claim
            for claim in self._claims
            if claim.product_id == product_id
            and claim.tenant == tenant
            and claim.market == market
            and claim.locale == locale
            and _is_effective(
                approval_status=claim.approval_status,
                effective_from=claim.effective_from,
                expires_at=claim.expires_at,
                revoked_at=claim.revoked_at,
                as_of=as_of,
            )
        )

    def get_changes(self, cursor: str | None, *, tenant: str) -> ChangePage:
        scoped = [change for change in self._changes if change.tenant == tenant]
        if cursor is None:
            remaining = scoped
        else:
            if all(change.cursor != cursor for change in scoped):
                raise InvalidCursorError(f"unknown change cursor {cursor!r}")
            remaining = [change for change in scoped if change.cursor > cursor]
        page = tuple(remaining[: self._page_size])
        next_cursor = page[-1].cursor if page else cursor
        return ChangePage(cursor=cursor, next_cursor=next_cursor, changes=page)


def _semver_key(version: str) -> tuple[int, int, int]:
    major, minor, patch = version.split(".")
    return int(major), int(minor), int(patch)


def _check_hash_integrity(documents: Iterable[ProductDocumentV1]) -> None:
    seen: dict[tuple[str, str], str] = {}
    for doc in documents:
        key = (doc.source_id, doc.source_version)
        existing = seen.get(key)
        if existing is not None and existing != doc.content_hash:
            raise ProductIntegrityError(
                f"source {doc.source_id!r} version {doc.source_version!r} has "
                "conflicting content hashes"
            )
        seen[key] = doc.content_hash
