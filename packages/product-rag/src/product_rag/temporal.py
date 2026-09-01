"""UTC timestamp helpers for contract DateTimeUtc strings."""

from __future__ import annotations

import re
from datetime import datetime

from product_rag.models import DATETIME_PATTERN

_DATETIME_RE = re.compile(DATETIME_PATTERN)


def parse_utc(ts: str) -> datetime:
    if _DATETIME_RE.fullmatch(ts) is None:
        raise ValueError(f"timestamp does not match DateTimeUtc contract: {ts!r}")
    return datetime.fromisoformat(ts[:-1] + "+00:00")
