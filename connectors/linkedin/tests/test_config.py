"""RED tests: config/linkedin.yaml loads into a strict, reference-only model.

API version is injected from configuration (never hardcoded); credentials
are references only; scopes cannot exceed the approved minimal set; real
modes are blocked without recorded official verification.
"""

from __future__ import annotations

import pydantic
import pytest

from connector_sdk import ConfigInvalidError

from linkedin_connector import LinkedInConnectorConfig, load_linkedin_config

from builders import CONFIG_PATH, config_document, make_config


def test_repo_config_file_loads_and_is_mock_disabled() -> None:
    config = load_linkedin_config(CONFIG_PATH)
    assert isinstance(config, LinkedInConnectorConfig)
    assert config.mode == "mock"
    assert config.enabled is False
    config.require_ready_for_mode()


def test_unknown_field_rejected() -> None:
    with pytest.raises(pydantic.ValidationError):
        make_config(surprise=True)


def test_api_version_must_come_from_reference() -> None:
    document = config_document()
    document["endpoint"]["api_version_ref"] = "202409"
    with pytest.raises(pydantic.ValidationError):
        LinkedInConnectorConfig.model_validate(document)


def test_raw_secret_in_auth_rejected() -> None:
    document = config_document()
    document["auth"]["refresh_token_ref"] = "AQXdSP_W41_UPs5ioT_t8HESyODB"
    with pytest.raises(pydantic.ValidationError):
        LinkedInConnectorConfig.model_validate(document)


def test_scopes_cannot_exceed_approved_minimum() -> None:
    document = config_document()
    document["auth"]["scopes"] = ["rw_ads", "r_organization_social"]
    with pytest.raises(pydantic.ValidationError):
        LinkedInConnectorConfig.model_validate(document)


def test_scopes_must_not_be_empty() -> None:
    document = config_document()
    document["auth"]["scopes"] = []
    with pytest.raises(pydantic.ValidationError):
        LinkedInConnectorConfig.model_validate(document)


def test_auth_method_must_be_3legged_oauth() -> None:
    document = config_document()
    document["auth"]["method"] = "client_credentials"
    with pytest.raises(pydantic.ValidationError):
        LinkedInConnectorConfig.model_validate(document)


def test_token_endpoints_must_be_official_https() -> None:
    document = config_document()
    document["auth"]["token_endpoint"] = "https://evil.example.com/token"
    with pytest.raises(pydantic.ValidationError):
        LinkedInConnectorConfig.model_validate(document)


def test_base_url_https_linkedin_only() -> None:
    document = config_document()
    document["endpoint"]["base_url"] = "http://api.linkedin.com"
    with pytest.raises(pydantic.ValidationError):
        LinkedInConnectorConfig.model_validate(document)


def test_test_account_required_cannot_be_disabled() -> None:
    document = config_document()
    document["account"]["test_account_required"] = False
    with pytest.raises(pydantic.ValidationError):
        LinkedInConnectorConfig.model_validate(document)


def test_proxy_and_retry_invariants_enforced() -> None:
    for section, key, bad in (
        ("proxy", "required", False),
        ("proxy", "allow_inbound", True),
        ("retry_strategy", "reconcile_before_retry", False),
        ("retry_strategy", "honor_retry_after", False),
    ):
        document = config_document()
        document[section][key] = bad
        with pytest.raises(pydantic.ValidationError):
            LinkedInConnectorConfig.model_validate(document)


def test_sandbox_without_verification_blocked() -> None:
    config = make_config(mode="sandbox", enabled=True)
    with pytest.raises(ConfigInvalidError):
        config.require_ready_for_mode()


def test_live_without_verification_blocked() -> None:
    config = make_config(mode="live", enabled=True)
    with pytest.raises(ConfigInvalidError):
        config.require_ready_for_mode()


def test_sandbox_verified_and_enabled_passes() -> None:
    document = config_document(mode="sandbox", enabled=True)
    document["endpoint"]["verification"] = "verified"
    LinkedInConnectorConfig.model_validate(document).require_ready_for_mode()


def test_fault_scenarios_cover_required_set() -> None:
    config = make_config()
    assert {
        "HTTP_429",
        "TIMEOUT_AFTER_EXTERNAL_CREATE",
        "AUTH_EXPIRED",
        "DUPLICATE_DELIVERY",
        "PARTIAL_HIERARCHY_SUCCESS",
    } <= set(config.mock.fault_injection.scenarios)
