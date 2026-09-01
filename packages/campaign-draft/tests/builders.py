"""Shared builders for campaign draft tests.

The approved package comes from the frozen Phase 02 → Phase 03 contract
fixture; tests mutate copies of it to produce invalid inputs. No channel
API, credential or network access exists anywhere in these tests.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from content_package import ApprovedContentPackageV1

from campaign_draft import DraftRequest

FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "content-package"
    / "fixtures"
    / "phase03"
    / "approved-content-package.sample.json"
)

FAKE_NOW = "2026-09-14T00:00:00Z"


def load_package(**overrides: Any) -> ApprovedContentPackageV1:
    document = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    package = ApprovedContentPackageV1.model_validate(document, strict=False)
    if overrides:
        package = package.model_copy(update=overrides)
    return package


def make_request(**overrides: Any) -> DraftRequest:
    values: dict[str, Any] = {
        "tenant_id": "tenant-cshi",
        "run_id": "run-p3-0001",
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
    return DraftRequest(**values)
