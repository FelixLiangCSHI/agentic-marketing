"""RED tests: shared channel connector config validation.

Real modes (sandbox/live) are rejected unless every reference (endpoint,
auth, api version, quota, proxy) is present and official verification is
recorded. Raw secret values never validate; only ``secretref://`` /
``env://`` / ``config://`` references do.
"""

from __future__ import annotations

import pydantic
import pytest

from connector_sdk import ConfigInvalidError

from builders import config_document, make_config


def test_mock_config_validates() -> None:
    config = make_config()
    assert config.mode == "mock"
    config.require_ready_for_mode()  # mock never raises


def test_unknown_field_rejected() -> None:
    with pytest.raises(pydantic.ValidationError):
        make_config(surprise=True)


@pytest.mark.parametrize(
    "section", ["endpoint", "auth", "rate_limit", "retry_strategy", "timeouts", "proxy"]
)
def test_missing_section_rejected(section: str) -> None:
    with pytest.raises(pydantic.ValidationError):
        make_config(**{section: ...})


def test_http_base_url_rejected() -> None:
    document = config_document()
    document["endpoint"]["base_url"] = "http://api.linkedin.com"
    with pytest.raises(pydantic.ValidationError):
        make_config(endpoint=document["endpoint"])


def test_raw_secret_value_in_auth_ref_rejected() -> None:
    document = config_document()
    document["auth"]["client_secret_ref"] = "AQXdSP_W41_UPs5ioT_t8HESyODB"
    with pytest.raises(pydantic.ValidationError):
        make_config(auth=document["auth"])


def test_api_version_must_be_reference_not_literal() -> None:
    document = config_document()
    document["endpoint"]["api_version_ref"] = "v2024_09"
    with pytest.raises(pydantic.ValidationError):
        make_config(endpoint=document["endpoint"])


def test_quota_must_be_reference_not_number() -> None:
    document = config_document()
    document["rate_limit"]["requests_per_window_ref"] = "500"
    with pytest.raises(pydantic.ValidationError):
        make_config(rate_limit=document["rate_limit"])


def test_proxy_not_required_rejected() -> None:
    document = config_document()
    document["proxy"]["required"] = False
    with pytest.raises(pydantic.ValidationError):
        make_config(proxy=document["proxy"])


def test_inbound_traffic_rejected() -> None:
    document = config_document()
    document["proxy"]["allow_inbound"] = True
    with pytest.raises(pydantic.ValidationError):
        make_config(proxy=document["proxy"])


def test_reconcile_before_retry_cannot_be_disabled() -> None:
    document = config_document()
    document["retry_strategy"]["reconcile_before_retry"] = False
    with pytest.raises(pydantic.ValidationError):
        make_config(retry_strategy=document["retry_strategy"])


def test_retry_after_cannot_be_ignored() -> None:
    document = config_document()
    document["retry_strategy"]["honor_retry_after"] = False
    with pytest.raises(pydantic.ValidationError):
        make_config(retry_strategy=document["retry_strategy"])


def test_sandbox_without_verification_blocked() -> None:
    config = make_config(mode="sandbox", enabled=True)
    with pytest.raises(ConfigInvalidError) as excinfo:
        config.require_ready_for_mode()
    assert "verification" in str(excinfo.value)


def test_live_without_verification_blocked() -> None:
    config = make_config(mode="live", enabled=True)
    with pytest.raises(ConfigInvalidError):
        config.require_ready_for_mode()


def test_sandbox_with_verified_endpoint_and_enabled_passes() -> None:
    document = config_document(mode="sandbox", enabled=True)
    document["endpoint"]["verification"] = "verified"
    config = make_config(**document)
    config.require_ready_for_mode()


def test_sandbox_disabled_flag_blocked_even_if_verified() -> None:
    document = config_document(mode="sandbox", enabled=False)
    document["endpoint"]["verification"] = "verified"
    config = make_config(**document)
    with pytest.raises(ConfigInvalidError):
        config.require_ready_for_mode()


def test_blocked_verification_never_ready_for_real_modes() -> None:
    document = config_document(mode="sandbox", enabled=True)
    document["endpoint"]["verification"] = "blocked"
    config = make_config(**document)
    with pytest.raises(ConfigInvalidError):
        config.require_ready_for_mode()
