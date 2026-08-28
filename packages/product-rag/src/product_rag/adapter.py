"""Read-only product adapter interface (frozen for Phase 02).

The adapter is the ONLY sanctioned path from agents to product data. It is
strictly read-only, tenant-scoped, and returns only approved, unexpired,
unrevoked records by default. Free text in returned records is untrusted
data and must never be executed as instructions.
"""

from __future__ import annotations

from typing import Protocol

from product_rag.models import (
    ChangePage,
    ProductClaimV1,
    ProductDocumentV1,
    ProductRecord,
)


class ProductAdapter(Protocol):
    """Read-only contract; implementations must not expose write operations."""

    def get_product(
        self, product_id: str, version: str | None = None, *, tenant: str
    ) -> ProductRecord:
        """Return the product summary or raise ``ProductNotFoundError``."""
        ...

    def list_approved_documents(
        self,
        product_id: str,
        market: str,
        locale: str,
        as_of: str,
        *,
        tenant: str,
    ) -> tuple[ProductDocumentV1, ...]:
        """Return only APPROVED, effective, unexpired, unrevoked documents."""
        ...

    def get_claims(
        self,
        product_id: str,
        market: str,
        locale: str,
        as_of: str,
        *,
        tenant: str,
    ) -> tuple[ProductClaimV1, ...]:
        """Return only APPROVED, effective, unexpired, unrevoked claims."""
        ...

    def get_changes(self, cursor: str | None, *, tenant: str) -> ChangePage:
        """Return a deterministic, replayable change page for the cursor."""
        ...
