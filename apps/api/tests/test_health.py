from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from dmt_api.identity.provider import FakeIdentityProvider
from dmt_api.identity.roles import Role
from dmt_api.main import create_app


def test_live_only_checks_process(client: TestClient) -> None:
    response = client.get("/api/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "live"}


def test_ready_reports_config_checks_in_mock_mode(client: TestClient) -> None:
    response = client.get("/api/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"]["config"] == "ok"
    assert body["checks"]["mode"] == "mock"
    assert body["checks"]["database"] == "not_configured"


def test_ready_fails_closed_on_disallowed_mode(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DMT_MODE", "live")
    response = client.get("/api/health/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["code"] == "not_ready"
    assert body["retryable"] is True
    assert "trace_id" in body


def test_ready_checks_configured_database() -> None:
    app = create_app(database_url="sqlite:///:memory:")
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/health/ready")
    assert response.status_code == 200
    assert response.json()["checks"]["database"] == "ok"


def test_ready_fails_when_configured_database_is_unavailable() -> None:
    app = create_app(database_url="not-a-url")
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/health/ready")
    assert response.status_code == 503
    assert response.json()["details"]["checks"]["database"] == "unavailable"


def test_ready_reports_identity_provider_when_configured() -> None:
    app = create_app(
        identity_provider=FakeIdentityProvider(
            group_mapping={"grp-admin": frozenset({Role.ADMIN})}
        )
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/health/ready")
    assert response.status_code == 200
    assert response.json()["checks"]["identity_provider"] == "configured"
