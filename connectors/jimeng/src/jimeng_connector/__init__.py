"""Official enterprise Jimeng media connector (Phase 02 / Subphase 05).

Deterministic async mock by default; real calls only in approved DEV
remote jobs. No cookies, reverse-engineered APIs or third-party proxies.
See ``config/jimeng.yaml``.
"""

from jimeng_connector.config import (
    JimengConfig,
    ResolvedAuth,
    RuntimeSettings,
    load_config,
    resolve_runtime,
)
from jimeng_connector.connector import DryRunReport, JimengConnector, ValidationReport
from jimeng_connector.contracts import (
    GeneratedAssetV1,
    JobRecordV1,
    MediaJobRequestV1,
    mime_for_format,
    request_hash,
)
from jimeng_connector.errors import (
    AssetValidationError,
    AuthenticationError,
    BudgetExceededError,
    ConnectorConfigError,
    ConnectorErrorV1,
    CreateTimeoutError,
    ForbiddenAuthError,
    JimengConnectorError,
    JobCancelledError,
    JobFailedError,
    LocalQueueFullError,
    MalwareRejectedError,
    NotSupportedError,
    PollDeadlineExceededError,
    ProviderRateLimitedError,
    ProviderRequestError,
    ProviderServerError,
    RealModeBlockedError,
    RequestInvalidError,
    ResultUrlExpiredError,
    UnknownJobError,
)
from jimeng_connector.governance import MOCK_COST_PER_IMAGE, JobRateLimiter, MediaBudget
from jimeng_connector.media_generator import JimengMediaGenerator
from jimeng_connector.storage import (
    ALLOWED_MIME,
    APPROVED_AGENT,
    GENERATED_AGENT,
    AssetImporter,
    synthetic_malware_scan,
)
from jimeng_connector.transport import (
    MALWARE_MARKER,
    DownloadedAsset,
    JimengMockTransport,
    MediaTransport,
    ProviderJob,
    ProviderResult,
    RateLimited,
    TransportTimeout,
)
from jimeng_connector.worker import (
    POLL_TOPIC,
    InMemoryJobStore,
    JimengMediaWorker,
    JobStore,
)

__all__ = [
    "ALLOWED_MIME",
    "APPROVED_AGENT",
    "AssetImporter",
    "AssetValidationError",
    "AuthenticationError",
    "BudgetExceededError",
    "ConnectorConfigError",
    "ConnectorErrorV1",
    "CreateTimeoutError",
    "DownloadedAsset",
    "DryRunReport",
    "ForbiddenAuthError",
    "GENERATED_AGENT",
    "GeneratedAssetV1",
    "InMemoryJobStore",
    "JimengConfig",
    "JimengConnector",
    "JimengConnectorError",
    "JimengMediaGenerator",
    "JimengMediaWorker",
    "JimengMockTransport",
    "JobCancelledError",
    "JobFailedError",
    "JobRateLimiter",
    "JobRecordV1",
    "JobStore",
    "LocalQueueFullError",
    "MALWARE_MARKER",
    "MOCK_COST_PER_IMAGE",
    "MalwareRejectedError",
    "MediaBudget",
    "MediaJobRequestV1",
    "MediaTransport",
    "NotSupportedError",
    "POLL_TOPIC",
    "PollDeadlineExceededError",
    "ProviderJob",
    "ProviderRateLimitedError",
    "ProviderRequestError",
    "ProviderResult",
    "ProviderServerError",
    "RateLimited",
    "RealModeBlockedError",
    "RequestInvalidError",
    "ResolvedAuth",
    "ResultUrlExpiredError",
    "RuntimeSettings",
    "TransportTimeout",
    "UnknownJobError",
    "ValidationReport",
    "load_config",
    "mime_for_format",
    "request_hash",
    "resolve_runtime",
    "synthetic_malware_scan",
]
