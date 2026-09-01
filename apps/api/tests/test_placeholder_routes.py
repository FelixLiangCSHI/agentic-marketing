from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from dmt_api.identity.provider import FakeIdentityProvider
from dmt_api.identity.roles import Role
from dmt_api.main import create_app

ERROR_ENVELOPE_KEYS = {"code", "message", "trace_id", "retryable", "details"}

VALID_RUN_CREATE = {
    "agent_type": "content",
    "workflow_name": "content.generate.v1",
    "workflow_version": "1.0.0",
    "tenant": "cshi",
    "business_unit": "marketing",
    "requester_id": "user-alice",
}


@pytest.fixture()
def idp() -> FakeIdentityProvider:
    return FakeIdentityProvider(
        group_mapping={
            "grp-content": frozenset({Role.CONTENT_CREATOR}),
            "grp-campaign": frozenset({Role.CAMPAIGN_OPERATOR}),
            "grp-audit": frozenset({Role.AUDITOR}),
        }
    )


@pytest.fixture()
def client(idp: FakeIdentityProvider) -> TestClient:
    return TestClient(create_app(identity_provider=idp), raise_server_exceptions=False)


@pytest.fixture()
def headers(idp: FakeIdentityProvider) -> dict[str, str]:
    token = idp.issue_session("alice", "Alice", groups=("grp-content", "grp-campaign"))
    return {"Authorization": "Bearer " + token}


@pytest.fixture()
def auditor_headers(idp: FakeIdentityProvider) -> dict[str, str]:
    token = idp.issue_session("andy", "Andy", groups=("grp-audit",))
    return {"Authorization": "Bearer " + token}


def _assert_not_implemented(body: dict[str, object]) -> None:
    assert set(body) == ERROR_ENVELOPE_KEYS
    assert body["code"] == "not_implemented"
    assert body["retryable"] is False


def test_create_run_requires_authentication(client: TestClient) -> None:
    response = client.post("/api/v1/runs", json=VALID_RUN_CREATE)
    assert response.status_code == 401


def test_placeholder_reads_require_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/runs/run-0001").status_code == 401
    assert client.post("/api/v1/runs/run-0001/cancel").status_code == 401
    assert client.get("/api/v1/tasks").status_code == 401


def test_create_run_is_typed_and_not_implemented(
    client: TestClient, headers: dict[str, str]
) -> None:
    response = client.post("/api/v1/runs", json=VALID_RUN_CREATE, headers=headers)
    assert response.status_code == 501
    _assert_not_implemented(response.json())


def test_create_run_rejects_unknown_fields(
    client: TestClient, headers: dict[str, str]
) -> None:
    payload = dict(VALID_RUN_CREATE, secret_token="never")
    response = client.post("/api/v1/runs", json=payload, headers=headers)
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    assert body["retryable"] is False


def test_create_run_rejects_free_text_agent_type(
    client: TestClient, headers: dict[str, str]
) -> None:
    payload = dict(VALID_RUN_CREATE, agent_type="marketing helper")
    response = client.post("/api/v1/runs", json=payload, headers=headers)
    assert response.status_code == 422


def test_get_run_not_implemented(
    client: TestClient, auditor_headers: dict[str, str]
) -> None:
    response = client.get("/api/v1/runs/run-0001", headers=auditor_headers)
    assert response.status_code == 501
    _assert_not_implemented(response.json())


def test_cancel_run_not_implemented(
    client: TestClient, headers: dict[str, str]
) -> None:
    response = client.post("/api/v1/runs/run-0001/cancel", headers=headers)
    assert response.status_code == 501
    _assert_not_implemented(response.json())


def test_list_tasks_not_implemented(
    client: TestClient, auditor_headers: dict[str, str]
) -> None:
    response = client.get("/api/v1/tasks", headers=auditor_headers)
    assert response.status_code == 501
    _assert_not_implemented(response.json())


def test_list_approvals_is_implemented_and_guarded(client: TestClient) -> None:
    # Implemented in Subphase 05: unauthenticated access is rejected, not 501.
    response = client.get("/api/v1/approvals")
    assert response.status_code == 401
