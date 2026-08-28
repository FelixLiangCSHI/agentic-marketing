"""DeepSeek LLM connector (Phase 02 / Subphase 04).

Deterministic mock by default; real calls only in approved DEV remote
jobs through a protected pipeline. See ``config/deepseek.yaml``.
"""

from deepseek_connector.config import (
    DeepSeekConfig,
    RuntimeSettings,
    load_config,
    resolve_runtime,
)
from deepseek_connector.connector import (
    DeepSeekConnector,
    DryRunReport,
    NotSupportedResult,
    ValidationReport,
)
from deepseek_connector.contracts import (
    ChatMessageV1,
    ChatRequestV1,
    ChatResultV1,
    ChatUsageV1,
    request_hash,
)
from deepseek_connector.errors import (
    AuthenticationError,
    BudgetExceededError,
    ConnectorConfigError,
    ConnectorErrorV1,
    DeepSeekConnectorError,
    InvalidProviderOutputError,
    LocalQueueFullError,
    NotSupportedError,
    ProviderRateLimitedError,
    ProviderRefusalError,
    ProviderRequestError,
    ProviderServerError,
    ProviderTimeoutError,
    RealModeBlockedError,
    RequestInvalidError,
    TokenLimitExceededError,
)
from deepseek_connector.governance import BudgetTracker, LocalRateLimiter, estimate_cost
from deepseek_connector.observability import ConnectorJournal, RequestRecord
from deepseek_connector.transport import (
    DeepSeekMockTransport,
    FaultInjection,
    ScriptedTransport,
    Transport,
    TransportResponse,
    TransportTimeout,
)
from deepseek_connector.workflow_model import PROMPT_VERSION, DeepSeekContentModel

__all__ = [
    "AuthenticationError",
    "BudgetExceededError",
    "BudgetTracker",
    "ChatMessageV1",
    "ChatRequestV1",
    "ChatResultV1",
    "ChatUsageV1",
    "ConnectorConfigError",
    "ConnectorErrorV1",
    "ConnectorJournal",
    "DeepSeekConfig",
    "DeepSeekConnector",
    "DeepSeekConnectorError",
    "DeepSeekContentModel",
    "DeepSeekMockTransport",
    "DryRunReport",
    "FaultInjection",
    "InvalidProviderOutputError",
    "LocalQueueFullError",
    "LocalRateLimiter",
    "NotSupportedError",
    "NotSupportedResult",
    "PROMPT_VERSION",
    "ProviderRateLimitedError",
    "ProviderRefusalError",
    "ProviderRequestError",
    "ProviderServerError",
    "ProviderTimeoutError",
    "RealModeBlockedError",
    "RequestInvalidError",
    "RequestRecord",
    "RuntimeSettings",
    "ScriptedTransport",
    "TokenLimitExceededError",
    "Transport",
    "TransportResponse",
    "TransportTimeout",
    "ValidationReport",
    "estimate_cost",
    "load_config",
    "request_hash",
    "resolve_runtime",
]
