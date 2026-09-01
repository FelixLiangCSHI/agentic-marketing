"""Approval consumption tests: atomic single-use, hash binding, expiry and
revocation — consumption failure means no external call is possible."""

from __future__ import annotations

import pytest

from campaign_activation import ApprovalInvalidError, FakeApprovalConsumer

from builders import FAKE_NOW

HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64
REF = "approvaltoken://campaign/run/one"


class TestConsume:
    def test_consume_returns_approval_id(self) -> None:
        approvals = FakeApprovalConsumer()
        approvals.mint(token_ref=REF, input_hash=HASH_A, approval_id="appr-1")
        assert (
            approvals.consume(
                token_ref=REF, input_hash=HASH_A, consumed_by="worker-1", now=FAKE_NOW
            )
            == "appr-1"
        )

    def test_token_is_single_use(self) -> None:
        approvals = FakeApprovalConsumer()
        approvals.mint(token_ref=REF, input_hash=HASH_A, approval_id="appr-1")
        approvals.consume(token_ref=REF, input_hash=HASH_A, consumed_by="w", now=FAKE_NOW)
        with pytest.raises(ApprovalInvalidError, match="consumed"):
            approvals.consume(token_ref=REF, input_hash=HASH_A, consumed_by="w", now=FAKE_NOW)

    def test_hash_mismatch_burns_token_and_rejects(self) -> None:
        approvals = FakeApprovalConsumer()
        approvals.mint(token_ref=REF, input_hash=HASH_A, approval_id="appr-1")
        with pytest.raises(ApprovalInvalidError, match="binding"):
            approvals.consume(token_ref=REF, input_hash=HASH_B, consumed_by="w", now=FAKE_NOW)
        # fail closed: the token is burned by the mismatch attempt
        with pytest.raises(ApprovalInvalidError):
            approvals.consume(token_ref=REF, input_hash=HASH_A, consumed_by="w", now=FAKE_NOW)

    def test_unknown_token_rejected(self) -> None:
        approvals = FakeApprovalConsumer()
        with pytest.raises(ApprovalInvalidError, match="unknown"):
            approvals.consume(
                token_ref="approvaltoken://nope", input_hash=HASH_A, consumed_by="w", now=FAKE_NOW
            )

    def test_expired_token_rejected(self) -> None:
        approvals = FakeApprovalConsumer()
        approvals.mint(
            token_ref=REF,
            input_hash=HASH_A,
            approval_id="appr-1",
            expires_at="2026-09-13T00:00:00Z",
        )
        with pytest.raises(ApprovalInvalidError, match="expired"):
            approvals.consume(token_ref=REF, input_hash=HASH_A, consumed_by="w", now=FAKE_NOW)

    def test_revoked_token_rejected(self) -> None:
        approvals = FakeApprovalConsumer()
        approvals.mint(token_ref=REF, input_hash=HASH_A, approval_id="appr-1")
        approvals.revoke(token_ref=REF)
        with pytest.raises(ApprovalInvalidError, match="revoked"):
            approvals.consume(token_ref=REF, input_hash=HASH_A, consumed_by="w", now=FAKE_NOW)
