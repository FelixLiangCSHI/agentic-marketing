"""Config gate tests: reference-only, secret-typed Developer Token, and the
Service Account approval gate (OAuth is the default; SA only for approved
enterprise-owned accounts)."""

from __future__ import annotations

from pathlib import Path

import pytest

from connector_sdk.errors import ConfigInvalidError

from google_ads_connector import load_google_ads_config

from builders import CONFIG_PATH, config_document, make_config


class TestLoadRepoConfig:
    def test_repo_config_loads_and_is_mock_disabled(self) -> None:
        config = load_google_ads_config(CONFIG_PATH)
        assert config.provider == "google_ads"
        assert config.mode == "mock"
        assert config.enabled is False
        assert config.auth.use_service_account is False
        assert config.auth.method == "oauth"
        assert config.query.reporting_service == "GoogleAdsService"
        assert config.query.query_language == "GAQL"
        assert config.query.stream_mode in ("Search", "SearchStream")

    def test_repo_config_file_exists(self) -> None:
        assert Path(CONFIG_PATH).is_file()


class TestReferenceOnlyFields:
    def test_developer_token_must_be_secretref(self) -> None:
        document = config_document()
        document["auth"]["developer_token_ref"] = "env://GOOGLE_ADS_DEVELOPER_TOKEN"
        with pytest.raises(ValueError, match="secretref://"):
            make_config(auth=document["auth"])

    def test_developer_token_literal_rejected(self) -> None:
        document = config_document()
        document["auth"]["developer_token_ref"] = "AbCdEf1234567890-real-looking-token"
        with pytest.raises(ValueError):
            make_config(auth=document["auth"])

    def test_oauth_client_secret_and_refresh_token_must_be_secretref(self) -> None:
        for key in ("oauth_client_secret_ref", "refresh_token_ref"):
            document = config_document()
            document["auth"][key] = "config://not/a/secret"
            with pytest.raises(ValueError, match="secretref://"):
                make_config(auth=document["auth"])

    def test_api_version_must_be_reference(self) -> None:
        document = config_document()
        document["endpoint"]["api_version_ref"] = "v21"
        with pytest.raises(ValueError):
            make_config(endpoint=document["endpoint"])

    def test_customer_ids_must_be_references(self) -> None:
        for key in ("customer_id_ref", "login_customer_id_ref"):
            document = config_document()
            document["account"][key] = "1234567890"
            with pytest.raises(ValueError):
                make_config(account=document["account"])

    def test_quota_refs_must_be_references(self) -> None:
        document = config_document()
        document["rate_limit"]["daily_operations_quota_ref"] = "15000"
        with pytest.raises(ValueError):
            make_config(rate_limit=document["rate_limit"])


class TestSafetyFlags:
    def test_unofficial_base_url_rejected(self) -> None:
        document = config_document()
        document["endpoint"]["base_url"] = "https://googleads.example.com"
        with pytest.raises(ValueError):
            make_config(endpoint=document["endpoint"])

    def test_proxy_required_and_no_inbound(self) -> None:
        document = config_document()
        document["proxy"]["required"] = False
        with pytest.raises(ValueError):
            make_config(proxy=document["proxy"])
        document = config_document()
        document["proxy"]["allow_inbound"] = True
        with pytest.raises(ValueError):
            make_config(proxy=document["proxy"])

    def test_manager_and_test_account_flags_locked(self) -> None:
        for key in (
            "manager_account_required",
            "test_account_required",
            "enterprise_owned_account_required_for_service_account",
        ):
            document = config_document()
            document["account"][key] = False
            with pytest.raises(ValueError):
                make_config(account=document["account"])

    def test_reconcile_and_retry_after_locked(self) -> None:
        for key in ("reconcile_before_retry", "honor_retry_after"):
            document = config_document()
            document["retry_strategy"][key] = False
            with pytest.raises(ValueError):
                make_config(retry_strategy=document["retry_strategy"])

    def test_unknown_fields_rejected(self) -> None:
        with pytest.raises(ValueError):
            make_config(surprise_field="nope")

    def test_query_service_locked_to_official_gaql(self) -> None:
        document = config_document()
        document["query"]["reporting_service"] = "InventedReportingAPI"
        with pytest.raises(ValueError):
            make_config(query=document["query"])


class TestServiceAccountGate:
    def test_use_service_account_requires_approved_method(self) -> None:
        document = config_document()
        document["auth"]["use_service_account"] = True  # method stays "oauth"
        with pytest.raises(ValueError, match="service_account_approved"):
            make_config(auth=document["auth"])

    def test_service_account_method_requires_flag(self) -> None:
        document = config_document()
        document["auth"]["method"] = "service_account_approved"  # flag stays False
        with pytest.raises(ValueError):
            make_config(auth=document["auth"])

    def test_approved_service_account_config_validates(self) -> None:
        document = config_document()
        document["auth"]["method"] = "service_account_approved"
        document["auth"]["use_service_account"] = True
        config = make_config(auth=document["auth"])
        assert config.auth.use_service_account is True


class TestModeGate:
    def test_mock_mode_is_ready(self) -> None:
        make_config().require_ready_for_mode()

    def test_sandbox_requires_verification(self) -> None:
        config = make_config(mode="sandbox", enabled=True)
        with pytest.raises(ConfigInvalidError, match="verified"):
            config.require_ready_for_mode()

    def test_sandbox_requires_enabled(self) -> None:
        document = config_document(mode="sandbox")
        document["endpoint"]["verification"] = "verified"
        config = make_config(mode="sandbox", endpoint=document["endpoint"])
        with pytest.raises(ConfigInvalidError, match="enabled"):
            config.require_ready_for_mode()
