"""Campaign metrics pipeline (Phase 03 / Subphase 06).

Immutable raw provider metrics, independent recomputable normalization,
watermark/cursor ingest, traceable performance reports and DRAFT-only
strategy recommendations. Real DEV/SIT pulls run only in protected jobs.
"""

from campaign_metrics.adapters import google_ads_fetcher, linkedin_fetcher
from campaign_metrics.ingest import (
    IngestResult,
    MetricsIngestor,
    PageFetcher,
    ProviderPage,
    ProviderRow,
)
from campaign_metrics.models import (
    CANONICAL_METRICS,
    IngestCheckpoint,
    IngestContext,
    MetricsError,
    NormalizedMetric,
    QualityStatus,
    RawImmutableError,
    RawMetricRecord,
)
from campaign_metrics.normalize import FORMULA_VERSION, normalize
from campaign_metrics.report import ReportInputError, build_performance_report
from campaign_metrics.stores import (
    FakeNormalizedMetricStore,
    FakeRawMetricStore,
    FakeWatermarkStore,
    NormalizedMetricStore,
    RawMetricStore,
    WatermarkStore,
)
from campaign_metrics.strategy import (
    StrategyEvidenceError,
    build_strategy_recommendation,
)

__all__ = [
    "CANONICAL_METRICS",
    "FORMULA_VERSION",
    "FakeNormalizedMetricStore",
    "FakeRawMetricStore",
    "FakeWatermarkStore",
    "IngestCheckpoint",
    "IngestContext",
    "IngestResult",
    "MetricsError",
    "MetricsIngestor",
    "NormalizedMetric",
    "NormalizedMetricStore",
    "PageFetcher",
    "ProviderPage",
    "ProviderRow",
    "QualityStatus",
    "RawImmutableError",
    "RawMetricRecord",
    "RawMetricStore",
    "ReportInputError",
    "StrategyEvidenceError",
    "WatermarkStore",
    "build_performance_report",
    "build_strategy_recommendation",
    "google_ads_fetcher",
    "linkedin_fetcher",
    "normalize",
]
