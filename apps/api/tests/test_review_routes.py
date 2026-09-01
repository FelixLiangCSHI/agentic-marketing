"""Review route tests: two-track approval, server-side role→track mapping,
artifact-hash binding, separation of duties, BLOCKED gate authority, and
content-change invalidation."""

from __future__ import annotations

import hashlib
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from dmt_api.identity.provider import FakeIdentityProvider
from dmt_api.identity.roles import Role
from dmt_api.main import create_app

GROUP_MAPPING: dict[str, frozenset[Role]] = {
    "grp-content": frozenset({Role.CONTENT_CREATOR}),
    "grp-medical": frozenset({Role.MEDICAL_REVIEWER}),
    "grp-marketing": frozenset({Role.MARKETING_REVIEWER}),
    "grp-audit": frozenset({Role.AUDITOR}),
}

HASH_V1 = "sha256:" + hashlib.sha256(b"content-v1").hexdigest()
HASH_V2 = "sha256:" + hashlib.sha256(b"content-v2").hexdigest()


@pytest.fixture()
def idp() -> FakeIdentityProvider:
    return FakeIdentityProvider(group_mapping=GROUP_MAPPING)


@pytest.fixture()
def client(idp: FakeIdentityProvider) -> Iterator[TestClient]:
    app = create_app(identity_provider=idp)
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": "Bearer " + token}


def create_payload(automated_status: str = "PASS") -> dict[str, object]:
    return {
        "run_id": "run-0001",
        "tenant": "tenant-cshi",
        "artifact_hash": HASH_V1,
        "policy_version": "1.0.0",
        "workflow_version": "0.1.0",
        "automated_status": automated_status,
        "content": {"headline": "H", "body": "B", "claims": [], "disclosures": []},
        "issues": [],
        "critic_questions": [],
        "sources": [{"source_id": "doc-alpha-pi", "source_version": "1.0.0"}],
    }


@pytest.fixture()
def tokens(idp: FakeIdentityProvider) -> dict[str, dict[str, str]]:
    return {
        "creator": bearer(idp.issue_session("carol", "Carol", groups=("grp-content",))),
        "medical": bearer(idp.issue_session("mia", "Mia", groups=("grp-medical",))),
        "marketing": bearer(
            idp.issue_session("mark", "Mark", groups=("grp-marketing",))
        ),
        "auditor": bearer(idp.issue_session("andy", "Andy", groups=("grp-audit",))),
    }


def create_review(
    client: TestClient,
    tokens: dict[str, dict[str, str]],
    automated_status: str = "PASS",
) -> str:
    response = client.post(
        "/api/v1/reviews", json=create_payload(automated_status), headers=tokens["creator"]
    )
    assert response.status_code == 201, response.text
    review_id = response.json()["review_id"]
    assert isinstance(review_id, str)
    return review_id


def decide(
    client: TestClient,
    review_id: str,
    headers: dict[str, str],
    *,
    decision: str = "approved",
    artifact_hash: str = HASH_V1,
    reason: str | None = None,
    rework_target: str | None = None,
) -> object:
    return client.post(
        f"/api/v1/reviews/{review_id}/decision",
        json={
            "artifact_hash": artifact_hash,
            "decision": decision,
            "reason": reason,
            "rework_target": rework_target,
        },
        headers=headers,
    )


class TestAccessControl:
    def test_create_requires_content_creator(
        self, client: TestClient, tokens: dict[str, dict[str, str]]
    ) -> None:
        response = client.post(
            "/api/v1/reviews", json=create_payload(), headers=tokens["medical"]
        )
        assert response.status_code == 403

    def test_decision_requires_reviewer_role(
        self, client: TestClient, tokens: dict[str, dict[str, str]]
    ) -> None:
        review_id = create_review(client, tokens)
        response = decide(client, review_id, tokens["auditor"])
        assert response.status_code == 403  # type: ignore[attr-defined]

    def test_unauthenticated_is_rejected(self, client: TestClient) -> None:
        assert client.get("/api/v1/reviews").status_code == 401

    def test_detail_is_side_by_side(
        self, client: TestClient, tokens: dict[str, dict[str, str]]
    ) -> None:
        review_id = create_review(client, tokens)
        response = client.get(f"/api/v1/reviews/{review_id}", headers=tokens["auditor"])
        assert response.status_code == 200
        body = response.json()
        # 并排呈现：内容、Claim、来源、政策版本、内容版本与合规结论。
        assert body["content"]["headline"] == "H"
        assert body["sources"][0]["source_id"] == "doc-alpha-pi"
        assert body["policy_version"] == "1.0.0"
        assert body["artifact_hash"] == HASH_V1
        assert body["automated_status"] == "PASS"
        assert body["medical"]["status"] == "PENDING"
        assert body["marketing"]["status"] == "PENDING"

    def test_list_and_detail_are_tenant_scoped(
        self, client: TestClient, tokens: dict[str, dict[str, str]], idp: FakeIdentityProvider
    ) -> None:
        own_id = create_review(client, tokens)
        other_creator = bearer(
            idp.issue_session(
                "olivia", "Olivia", tenant="tenant-other", groups=("grp-content",)
            )
        )
        other_payload = {**create_payload(), "tenant": "tenant-other", "run_id": "run-0002"}
        other = client.post(
            "/api/v1/reviews", json=other_payload, headers=other_creator
        )
        assert other.status_code == 201
        other_id = other.json()["review_id"]

        listing = client.get("/api/v1/reviews", headers=tokens["auditor"])
        assert listing.status_code == 200
        assert [item["review_id"] for item in listing.json()] == [own_id]
        hidden = client.get(f"/api/v1/reviews/{other_id}", headers=tokens["auditor"])
        assert hidden.status_code == 404


class TestTwoTrackApproval:
    def test_both_tracks_required_for_approved(
        self, client: TestClient, tokens: dict[str, dict[str, str]]
    ) -> None:
        review_id = create_review(client, tokens)
        first = decide(client, review_id, tokens["medical"])
        assert first.status_code == 200  # type: ignore[attr-defined]
        assert first.json()["status"] == "AWAITING_REVIEW"  # type: ignore[attr-defined]
        second = decide(client, review_id, tokens["marketing"])
        assert second.json()["status"] == "APPROVED"  # type: ignore[attr-defined]
        assert second.json()["medical"]["decided_by"] == "mia"  # type: ignore[attr-defined]
        assert second.json()["marketing"]["decided_by"] == "mark"  # type: ignore[attr-defined]

    def test_track_is_derived_from_server_roles_not_client(
        self, client: TestClient, tokens: dict[str, dict[str, str]]
    ) -> None:
        review_id = create_review(client, tokens)
        response = client.post(
            f"/api/v1/reviews/{review_id}/decision",
            json={
                "artifact_hash": HASH_V1,
                "decision": "approved",
                "track": "marketing",  # forged field must be rejected
            },
            headers=tokens["medical"],
        )
        assert response.status_code == 422

    def test_same_track_cannot_be_decided_twice(
        self, client: TestClient, tokens: dict[str, dict[str, str]], idp: FakeIdentityProvider
    ) -> None:
        review_id = create_review(client, tokens)
        assert decide(client, review_id, tokens["medical"]).status_code == 200  # type: ignore[attr-defined]
        second_medical = bearer(
            idp.issue_session("mina", "Mina", groups=("grp-medical",))
        )
        response = decide(client, review_id, second_medical)
        assert response.status_code == 409  # type: ignore[attr-defined]
        assert response.json()["code"] == "illegal_state"  # type: ignore[attr-defined]


class TestSeparationOfDuties:
    def test_creator_cannot_review(
        self, client: TestClient, tokens: dict[str, dict[str, str]], idp: FakeIdentityProvider
    ) -> None:
        review_id = create_review(client, tokens)
        creator_as_reviewer = bearer(
            idp.issue_session("carol", "Carol", groups=("grp-medical",))
        )
        response = decide(client, review_id, creator_as_reviewer)
        assert response.status_code == 403  # type: ignore[attr-defined]
        assert response.json()["code"] == "separation_of_duties"  # type: ignore[attr-defined]

    def test_same_identity_cannot_decide_both_tracks(
        self, client: TestClient, tokens: dict[str, dict[str, str]], idp: FakeIdentityProvider
    ) -> None:
        review_id = create_review(client, tokens)
        assert decide(client, review_id, tokens["medical"]).status_code == 200  # type: ignore[attr-defined]
        mia_as_marketing = bearer(
            idp.issue_session("mia", "Mia", groups=("grp-marketing",))
        )
        response = decide(client, review_id, mia_as_marketing)
        assert response.status_code == 403  # type: ignore[attr-defined]
        assert response.json()["code"] == "separation_of_duties"  # type: ignore[attr-defined]


class TestArtifactBindingAndGate:
    def test_stale_artifact_hash_is_conflict(
        self, client: TestClient, tokens: dict[str, dict[str, str]]
    ) -> None:
        review_id = create_review(client, tokens)
        response = decide(client, review_id, tokens["medical"], artifact_hash=HASH_V2)
        assert response.status_code == 409  # type: ignore[attr-defined]
        assert response.json()["code"] == "stale_artifact"  # type: ignore[attr-defined]

    def test_blocked_gate_cannot_be_approved_by_any_human(
        self, client: TestClient, tokens: dict[str, dict[str, str]]
    ) -> None:
        review_id = create_review(client, tokens, automated_status="BLOCKED")
        for reviewer in ("medical", "marketing"):
            response = decide(client, review_id, tokens[reviewer])
            assert response.status_code == 422  # type: ignore[attr-defined]
            assert response.json()["code"] == "invalid_decision"  # type: ignore[attr-defined]

    def test_blocked_gate_can_still_be_rejected_with_target(
        self, client: TestClient, tokens: dict[str, dict[str, str]]
    ) -> None:
        review_id = create_review(client, tokens, automated_status="BLOCKED")
        response = decide(
            client,
            review_id,
            tokens["medical"],
            decision="rejected",
            reason="uncited efficacy claim",
            rework_target="copy_issue",
        )
        assert response.status_code == 200  # type: ignore[attr-defined]
        assert response.json()["status"] == "REJECTED"  # type: ignore[attr-defined]

    def test_reject_requires_reason_and_target(
        self, client: TestClient, tokens: dict[str, dict[str, str]]
    ) -> None:
        review_id = create_review(client, tokens)
        missing_reason = decide(
            client, review_id, tokens["medical"], decision="rejected",
            rework_target="copy_issue",
        )
        assert missing_reason.status_code == 422  # type: ignore[attr-defined]
        missing_target = decide(
            client, review_id, tokens["medical"], decision="rejected", reason="why"
        )
        assert missing_target.status_code == 422  # type: ignore[attr-defined]


class TestContentChangeInvalidation:
    def test_content_change_invalidates_prior_approval(
        self, client: TestClient, tokens: dict[str, dict[str, str]]
    ) -> None:
        review_id = create_review(client, tokens)
        assert decide(client, review_id, tokens["medical"]).status_code == 200  # type: ignore[attr-defined]
        response = client.post(
            f"/api/v1/reviews/{review_id}/content-changed",
            json={
                "artifact_hash": HASH_V2,
                "automated_status": "PASS",
                "content": {"headline": "H2"},
            },
            headers=tokens["creator"],
        )
        assert response.status_code == 200
        body = response.json()
        assert body["revision"] == 2
        assert body["medical"]["status"] == "INVALIDATED"
        assert body["status"] == "AWAITING_REVIEW"
        # 旧版本的 hash 不再可用于决策。
        stale = decide(client, review_id, tokens["marketing"])
        assert stale.status_code == 409  # type: ignore[attr-defined]
        fresh = decide(
            client, review_id, tokens["marketing"], artifact_hash=HASH_V2
        )
        assert fresh.status_code == 200  # type: ignore[attr-defined]

    def test_only_creator_can_register_content_change(
        self, client: TestClient, tokens: dict[str, dict[str, str]]
    ) -> None:
        review_id = create_review(client, tokens)
        response = client.post(
            f"/api/v1/reviews/{review_id}/content-changed",
            json={"artifact_hash": HASH_V2, "automated_status": "PASS"},
            headers=tokens["medical"],
        )
        assert response.status_code == 403
