"""Typed error model for the read-only product adapter boundary.

Adapters never silently return fake success: unknown products, integrity
violations and bad cursors raise these typed errors so callers can map them
to the versioned API error envelope.
"""

from __future__ import annotations


class ProductAdapterError(Exception):
    """Base class; carries a stable machine-readable code."""

    code: str = "product_adapter_error"
    retryable: bool = False

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ProductNotFoundError(ProductAdapterError):
    code = "product_not_found"


class ProductVersionNotFoundError(ProductAdapterError):
    code = "product_version_not_found"


class ProductIntegrityError(ProductAdapterError):
    """Same source_id + source_version resolved to different content hashes."""

    code = "product_integrity_violation"


class InvalidCursorError(ProductAdapterError):
    code = "invalid_change_cursor"


class FixtureValidationError(ProductAdapterError):
    """Synthetic fixture data failed contract validation on load."""

    code = "fixture_contract_violation"
