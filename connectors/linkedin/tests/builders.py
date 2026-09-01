"""Shared deterministic builders for linkedin-connector tests."""

from __future__ import annotations

import copy
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from campaign_draft import CampaignProposalV1, DraftRequest, build_campaign_draft
from connector_sdk import ChannelPolicy
from content_package import ApprovedContentPackageV1

from linkedin_connector import LinkedInConnectorConfig

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = REPO_ROOT / "config" / "linkedin.yaml"
PACKAGE_FIXTURE = (
    REPO_ROOT
    / "packages"
    / "content-package"
    / "fixtures"
    / "phase03"
    / "approved-content-package.sample.json"
)

FAKE_NOW = "2026-09-14T00:00:00Z"


def config_document(**overrides: Any) -> dict[str, Any]:
    document: dict[str, Any] = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    base = copy.deepcopy(document)
    for key, value in overrides.items():
        if value is ...:
            base.pop(key, None)
        else:
            base[key] = value
    return base


def make_config(**overrides: Any) -> LinkedInConnectorConfig:
    return LinkedInConnectorConfig.model_validate(config_document(**overrides))


def load_package() -> ApprovedContentPackageV1:
    document = json.loads(PACKAGE_FIXTURE.read_text(encoding="utf-8"))
    return ApprovedContentPackageV1.model_validate(document, strict=False)


def make_proposal(**overrides: Any) -> CampaignProposalV1:
    package = load_package()
    values: dict[str, Any] = {
        "tenant_id": "tenant-cshi",
        "run_id": "run-p3-0003",
        "requester_id": "emp-campaign-op",
        "channel": "linkedin",
        "account_id": "acct-linkedin-dev",
        "objective": "LEAD_GENERATION",
        "campaign_name": "alpha-q4-lead-gen",
        "currency": "USD",
        "total_limit": Decimal("1000.00"),
        "daily_limit": Decimal("100.00"),
        "timezone": "America/New_York",
        "start_at": "2026-09-21T00:00:00Z",
        "end_at": "2026-10-02T23:59:59Z",
        "markets": ("US",),
        "excluded_segments": (),
        "policy_version": "campaign-policy-1.0.0",
        "workflow_version": "1.0.0",
    }
    values.update(overrides)
    return build_campaign_draft(
        package=package,
        expected_content_hash=package.content_hash,
        request=DraftRequest(**values),
        as_of=FAKE_NOW,
    )


def make_policy(**overrides: Any) -> ChannelPolicy:
    values: dict[str, Any] = {
        "policy_version": "campaign-policy-1.0.0",
        "channel": "linkedin",
        "known_accounts": ("acct-linkedin-dev",),
        "allowed_objectives": ("LEAD_GENERATION", "BRAND_AWARENESS"),
        "allowed_currencies": ("USD", "EUR"),
        "max_total_budget_minor": 500000,
        "max_daily_budget_minor": 50000,
        "allowed_markets": ("US",),
        "max_duration_days": 30,
        "max_campaign_name_length": 100,
    }
    values.update(overrides)
    return ChannelPolicy(**values)
