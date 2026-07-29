from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal


ServiceKind = Literal["ai_insight", "ai_plan", "buffer"]


@dataclass(frozen=True)
class ServiceConfiguration:
    endpoint: str
    credential: str = field(repr=False)

    @classmethod
    def from_dict(cls, value: Any) -> ServiceConfiguration:
        if not isinstance(value, dict):
            raise ValueError("Service configuration must be an object.")
        endpoint = value.get("endpoint")
        credential = value.get("credential")
        if not isinstance(endpoint, str) or not isinstance(credential, str):
            raise ValueError("Service endpoint and credential must be strings.")
        return cls(endpoint=endpoint, credential=credential)

    def to_dict(self) -> dict[str, str]:
        return {"endpoint": self.endpoint, "credential": self.credential}


@dataclass(frozen=True)
class ApplicationConfiguration:
    ai_insight: ServiceConfiguration
    ai_plan: ServiceConfiguration
    buffer: ServiceConfiguration
    version: int = 1
    saved_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )

    @classmethod
    def from_dict(cls, value: Any) -> ApplicationConfiguration:
        if not isinstance(value, dict) or value.get("version") != 1:
            raise ValueError("Unsupported application configuration.")
        saved_at = value.get("savedAt")
        if not isinstance(saved_at, str):
            raise ValueError("Configuration timestamp is missing.")
        return cls(
            ai_insight=ServiceConfiguration.from_dict(value.get("aiInsight")),
            ai_plan=ServiceConfiguration.from_dict(value.get("aiPlan")),
            buffer=ServiceConfiguration.from_dict(value.get("buffer")),
            version=1,
            saved_at=saved_at,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "savedAt": self.saved_at,
            "aiInsight": self.ai_insight.to_dict(),
            "aiPlan": self.ai_plan.to_dict(),
            "buffer": self.buffer.to_dict(),
        }

    def service(self, kind: ServiceKind) -> ServiceConfiguration:
        return {
            "ai_insight": self.ai_insight,
            "ai_plan": self.ai_plan,
            "buffer": self.buffer,
        }[kind]


@dataclass(frozen=True)
class ConnectionResult:
    service: ServiceKind
    success: bool
    message: str

