"""product-rag: read-only approved product data contracts and adapters."""

from product_rag.adapter import ProductAdapter
from product_rag.chunking import Chunk, chunk_document
from product_rag.citations import Citation
from product_rag.embedding import (
    EmbeddingMetadata,
    EmbeddingProvider,
    FakeEmbeddingProvider,
)
from product_rag.errors import (
    FixtureValidationError,
    IndexVersionMismatchError,
    IngestionRejectedError,
    InvalidCursorError,
    KnowledgeBaseNotConfiguredError,
    MissingRetrievalFilterError,
    ProductAdapterError,
    ProductIntegrityError,
    ProductNotFoundError,
    ProductVersionNotFoundError,
)
from product_rag.fake_adapter import FakeProductAdapter
from product_rag.index import (
    IndexEntry,
    InMemoryKnowledgeBaseIndex,
    KnowledgeBaseIndex,
    RetrievalFilters,
    ScoredEntry,
    make_index_version,
)
from product_rag.ingestion import (
    ChangeReport,
    IngestionPipeline,
    IngestionReport,
    SourceResult,
)
from product_rag.midea import MideaKnowledgeBaseConfig, MideaKnowledgeBaseIndex
from product_rag.models import (
    ChangePage,
    ProductChangeV1,
    ProductClaimV1,
    ProductDocumentV1,
    ProductRecord,
)
from product_rag.retrieval import RetrievedPassage, Retriever

__all__ = [
    "ChangePage",
    "ChangeReport",
    "Chunk",
    "Citation",
    "EmbeddingMetadata",
    "EmbeddingProvider",
    "FakeEmbeddingProvider",
    "FakeProductAdapter",
    "FixtureValidationError",
    "InMemoryKnowledgeBaseIndex",
    "IndexEntry",
    "IndexVersionMismatchError",
    "IngestionPipeline",
    "IngestionRejectedError",
    "IngestionReport",
    "InvalidCursorError",
    "KnowledgeBaseIndex",
    "KnowledgeBaseNotConfiguredError",
    "MideaKnowledgeBaseConfig",
    "MideaKnowledgeBaseIndex",
    "MissingRetrievalFilterError",
    "ProductAdapter",
    "ProductAdapterError",
    "ProductChangeV1",
    "ProductClaimV1",
    "ProductDocumentV1",
    "ProductIntegrityError",
    "ProductNotFoundError",
    "ProductRecord",
    "ProductVersionNotFoundError",
    "RetrievalFilters",
    "RetrievedPassage",
    "Retriever",
    "ScoredEntry",
    "SourceResult",
    "chunk_document",
    "make_index_version",
]
