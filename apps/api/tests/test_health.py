from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


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
