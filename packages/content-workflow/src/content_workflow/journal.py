"""Run journal: one entry per executed node, with versioned hashes.

The journal is append-only evidence: which node ran, in which order, over
which input/output content (hashes only, no payload duplication), under
which workflow version and schema version.
"""

from __future__ import annotations

import hashlib
from typing import Literal

from pydantic import BaseModel, ConfigDict, StrictStr

WorkflowNodeName = Literal[
    "validate_input",
    "retrieve_product_facts",
    "build_brief",
    "generate_copy",
    "generate_media",
    "compliance_check",
    "human_review",
    "package_approved",
]


class JournalEntryV1(BaseModel):
    """Evidence record for one node execution (order = list order)."""

    # strict=False：Checkpoint 恢复需宽松重建（见 contracts._NodeModel 注释）。
    model_config = ConfigDict(extra="forbid", strict=False, frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    node: WorkflowNodeName
    workflow_version: StrictStr
    input_hash: StrictStr
    output_hash: StrictStr
    detail: StrictStr


def text_hash(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
