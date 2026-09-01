"""LinkedIn Advertising Connector (Phase 03 / Subphase 03).

Mock/contract implementation on the shared Connector SDK. Real 3-legged
OAuth and test-account writes run only in protected DEV/SIT jobs.
"""

from linkedin_connector.auth import (
    MockOAuthTransport,
    OAuthAdapter,
    OAuthStateError,
    OAuthTransport,
    TokenGrant,
)
from linkedin_connector.config import (
    APPROVED_SCOPES,
    LinkedInConnectorConfig,
    load_linkedin_config,
)
from linkedin_connector.connector import (
    LinkedInAdvertisingConnector,
    LinkedInTransport,
    MockLinkedInTransport,
    PartialHierarchyError,
)
from linkedin_connector.mappers import (
    MappedCampaignRequest,
    VerificationRequiredMappingError,
    map_campaign_request,
    response_digest,
)
from linkedin_connector.metrics import MetricRow, MetricsPage, fetch_metrics_page

__all__ = [
    "APPROVED_SCOPES",
    "LinkedInAdvertisingConnector",
    "LinkedInConnectorConfig",
    "LinkedInTransport",
    "MappedCampaignRequest",
    "MetricRow",
    "MetricsPage",
    "MockLinkedInTransport",
    "MockOAuthTransport",
    "OAuthAdapter",
    "OAuthStateError",
    "OAuthTransport",
    "PartialHierarchyError",
    "TokenGrant",
    "VerificationRequiredMappingError",
    "fetch_metrics_page",
    "load_linkedin_config",
    "map_campaign_request",
    "response_digest",
]
