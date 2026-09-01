"""Shared result models for connector external writes."""

from __future__ import annotations

from typing import Literal

import pydantic

WriteOutcome = Literal["CREATED", "ALREADY_EXISTS", "ACCEPTED", "UNKNOWN"]


class ExternalWriteResult(pydantic.BaseModel):
    """Outcome of an external write; UNKNOWN mandates reconcile before retry."""

    model_config = pydantic.ConfigDict(extra="forbid", frozen=True)

    outcome: WriteOutcome
    external_object_id: str | None
    operation_id: str = pydantic.Field(min_length=1)
    raw_response_ref: str | None = None
