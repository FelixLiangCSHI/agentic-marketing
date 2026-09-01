"""Approval token consumption: atomic, single-use, hash-bound.

The fake mirrors the Phase 01 ``ApprovalService`` semantics: a token is
consumed exactly once with a conditional update; a binding (input hash)
mismatch burns the token before rejecting, so a tampered request can never
retry its way into a write (fail closed).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from campaign_activation.models import ApprovalInvalidError


class ApprovalConsumer(Protocol):
    def consume(
        self, *, token_ref: str, input_hash: str, consumed_by: str, now: str
    ) -> str: ...


@dataclass
class _TokenState:
    input_hash: str
    approval_id: str
    expires_at: str | None
    consumed: bool = False
    revoked: bool = False


@dataclass
class FakeApprovalConsumer:
    """In-memory single-use approval tokens bound to an input hash."""

    _tokens: dict[str, _TokenState] = field(default_factory=dict)

    def mint(
        self,
        *,
        token_ref: str,
        input_hash: str,
        approval_id: str,
        expires_at: str | None = None,
    ) -> None:
        self._tokens[token_ref] = _TokenState(
            input_hash=input_hash, approval_id=approval_id, expires_at=expires_at
        )

    def revoke(self, *, token_ref: str) -> None:
        state = self._tokens.get(token_ref)
        if state is not None:
            state.revoked = True

    def consume(
        self, *, token_ref: str, input_hash: str, consumed_by: str, now: str
    ) -> str:
        state = self._tokens.get(token_ref)
        if state is None:
            raise ApprovalInvalidError("unknown approval token reference")
        if state.revoked:
            raise ApprovalInvalidError("approval token was revoked")
        if state.consumed:
            raise ApprovalInvalidError("approval token was already consumed (single-use)")
        if state.expires_at is not None and now > state.expires_at:
            raise ApprovalInvalidError("approval token expired")
        if state.input_hash != input_hash:
            # Burn the token before rejecting: binding mismatches fail closed.
            state.consumed = True
            raise ApprovalInvalidError(
                "approval token binding mismatch: input_hash differs from the approved input"
            )
        state.consumed = True
        return state.approval_id
