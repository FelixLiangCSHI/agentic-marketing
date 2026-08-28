"""product-rag: read-only approved product data contracts and adapters."""

from product_rag.adapter import ProductAdapter
from product_rag.errors import (
    FixtureValidationError,
    InvalidCursorError,
    ProductAdapterError,
    ProductIntegrityError,
    ProductNotFoundError,
    ProductVersionNotFoundError,
)
from product_rag.fake_adapter import FakeProductAdapter
from product_rag.models import (
    ChangePage,
    ProductChangeV1,
    ProductClaimV1,
    ProductDocumentV1,
    ProductRecord,
)

__all__ = [
    "ChangePage",
    "FakeProductAdapter",
    "FixtureValidationError",
    "InvalidCursorError",
    "ProductAdapter",
    "ProductAdapterError",
    "ProductChangeV1",
    "ProductClaimV1",
    "ProductDocumentV1",
    "ProductIntegrityError",
    "ProductNotFoundError",
    "ProductRecord",
    "ProductVersionNotFoundError",
]
