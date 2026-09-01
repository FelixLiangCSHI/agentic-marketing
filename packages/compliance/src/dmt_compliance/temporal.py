"""UTC timestamp helpers for frozen contract timestamp strings."""

from __future__ import annotations

import re
from datetime import datetime

_DATETIME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?Z$"
)


def parse_utc(ts: str) -> datetime:
    if _DATETIME_RE.fullmatch(ts) is None:
        raise ValueError(f"timestamp does not match DateTimeUtc contract: {ts!r}")
    return datetime.fromisoformat(ts[:-1] + "+00:00")
