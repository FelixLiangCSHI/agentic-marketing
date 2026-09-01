"""Google Ads Connector (Phase 03 / Subphase 04).

Mock/contract implementation on the shared Connector SDK. The Developer
Token is a Secret Reference only; OAuth is the default and Service
Accounts require a recorded enterprise-ownership approval. Real API
calls run only in protected DEV/SIT jobs.
"""

from google_ads_connector.auth import (
    DeveloperTokenInvalidError,
    GoogleAdsAuthAdapter,
    GoogleAdsCredentials,
    MockTokenTransport,
    ServiceAccountNotApprovedError,
    TokenTransport,
)
from google_ads_connector.config import (
    GoogleAdsConnectorConfig,
    load_google_ads_config,
)
from google_ads_connector.connector import (
    GoogleAdsConnector,
    GoogleAdsTransport,
    MockGoogleAdsTransport,
    PartialMutateError,
)
from google_ads_connector.mappers import (
    MappedCampaignMutate,
    VerificationRequiredMappingError,
    map_campaign_mutate,
    response_digest,
)
from google_ads_connector.metrics import GaqlPage, MetricRow, fetch_gaql_page

__all__ = [
    "DeveloperTokenInvalidError",
    "GaqlPage",
    "GoogleAdsAuthAdapter",
    "GoogleAdsConnector",
    "GoogleAdsConnectorConfig",
    "GoogleAdsCredentials",
    "GoogleAdsTransport",
    "MappedCampaignMutate",
    "MetricRow",
    "MockGoogleAdsTransport",
    "MockTokenTransport",
    "PartialMutateError",
    "ServiceAccountNotApprovedError",
    "TokenTransport",
    "VerificationRequiredMappingError",
    "fetch_gaql_page",
    "load_google_ads_config",
    "map_campaign_mutate",
    "response_digest",
]
