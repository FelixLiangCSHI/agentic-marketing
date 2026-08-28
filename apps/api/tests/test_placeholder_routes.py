from __future__ import annotations

from fastapi.testclient import TestClient

ERROR_ENVELOPE_KEYS = {"code", "message", "trace_id", "retryable", "details"}

VALID_RUN_CREATE = {
    "agent_type": "content",
    "workflow_name": "content.generate.v1",
    "workflow_version": "1.0.0",
    "tenant": "cshi",
    "business_unit": "marketing",
    "requester_id": "user-alice",
}


def _assert_not_implemented(body: dict[str, object]) -> None:
    assert set(body) == ERROR_ENVELOPE_KEYS
    assert body["code"] == "not_implemented"
    assert body["retryable"] is False


def test_create_run_is_typed_and_not_implemented(client: TestClient) -> None:
    response = client.post("/api/v1/runs", json=VALID_RUN_CREATE)
    assert response.status_code == 501
    _assert_not_implemented(response.json())


def test_create_run_rejects_unknown_fields(client: TestClient) -> None:
    payload = dict(VALID_RUN_CREATE, secret_token="never")
    response = client.post("/api/v1/runs", json=payload)
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    assert body["retryable"] is False


def test_create_run_rejects_free_text_agent_type(client: TestClient) -> None:
    payload = dict(VALID_RUN_CREATE, agent_type="marketing helper")
    response = client.post("/api/v1/runs", json=payload)
    assert response.status_code == 422


def test_get_run_not_implemented(client: TestClient) -> None:
    response = client.get("/api/v1/runs/run-0001")
    assert response.status_code == 501
    _assert_not_implemented(response.json())


def test_cancel_run_not_implemented(client: TestClient) -> None:
    response = client.post("/api/v1/runs/run-0001/cancel")
    assert response.status_code == 501
    _assert_not_implemented(response.json())


def test_list_tasks_not_implemented(client: TestClient) -> None:
    response = client.get("/api/v1/tasks")
    assert response.status_code == 501
    _assert_not_implemented(response.json())


def test_list_approvals_is_implemented_and_guarded(client: TestClient) -> None:
    # Implemented in Subphase 05: unauthenticated access is rejected, not 501.
    response = client.get("/api/v1/approvals")
    assert response.status_code == 401
