"""Skill metadata and registry (Phase 02 / Subphase 03).

Skills are versioned, approved prompt/policy assets owned by humans
(Brand/Medical/Market/Channel Skill Owner). The registry loads the minimal
set for one agent/market/locale/channel scope:

* expired or revoked skills block the requesting node with a typed error —
  they are never silently skipped;
* DRAFT (not yet formally approved) skills are usable, but the workflow can
  then only produce a DRAFT package, never an approved one;
* skill content is read-only untrusted data; the versions used are written
  into the run journal.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from content_workflow.errors import (
    SkillExpiredError,
    SkillFixtureError,
    SkillNotFoundError,
    SkillRevokedError,
)
from product_rag.models import (
    DateTimeUtc,
    Identifier,
    Locale,
    Market,
    SemVer,
    Sha256Hash,
)

from content_workflow.temporal import parse_utc

SkillKind = Literal["brand", "medical", "market", "channel"]
SkillApprovalStatus = Literal["APPROVED", "DRAFT", "REVOKED"]
AgentName = Literal["content"]
Channel = Literal["linkedin", "google_ads"]

REQUIRED_SKILL_KINDS: tuple[SkillKind, ...] = ("brand", "medical", "market", "channel")


class SkillMetadata(BaseModel):
    """One versioned skill. ``guidance`` is untrusted free text."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: Literal["1.0"]
    skill_id: Identifier
    version: SemVer
    agent: AgentName
    kind: SkillKind
    owner: Identifier
    tenant: Identifier
    markets: tuple[Market, ...]
    locales: tuple[Locale, ...]
    channels: tuple[Channel, ...]
    approval_status: SkillApprovalStatus
    effective_from: DateTimeUtc
    expires_at: DateTimeUtc | None
    revoked_at: DateTimeUtc | None
    guidance: str
    content_hash: Sha256Hash
    # 结构化规则字段（供 Brief/Compliance 确定性消费，不经模型改写）。
    tone: str | None = None
    banned_phrases: tuple[str, ...] = ()
    required_disclosures: tuple[str, ...] = ()
    max_headline_chars: int | None = None


class SkillSet(BaseModel):
    """Minimal skill set loaded for one scope; versions go into the run."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    brand: SkillMetadata
    medical: SkillMetadata
    market: SkillMetadata
    channel: SkillMetadata

    @property
    def versions(self) -> dict[str, str]:
        return {
            skill.skill_id: skill.version
            for skill in (self.brand, self.medical, self.market, self.channel)
        }

    @property
    def all_approved(self) -> bool:
        return all(
            skill.approval_status == "APPROVED"
            for skill in (self.brand, self.medical, self.market, self.channel)
        )


def _skill_content_hash(guidance: str) -> str:
    return "sha256:" + hashlib.sha256(guidance.encode("utf-8")).hexdigest()


class SkillRegistry:
    """Read-only registry over validated skill metadata."""

    def __init__(self, skills: list[SkillMetadata]) -> None:
        for skill in skills:
            if skill.content_hash != _skill_content_hash(skill.guidance):
                raise SkillFixtureError(
                    f"skill {skill.skill_id!r} v{skill.version} content hash "
                    "does not match its guidance text"
                )
        self._skills = tuple(skills)

    @classmethod
    def from_fixture_file(cls, path: Path) -> "SkillRegistry":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise SkillFixtureError(f"cannot read skill fixture {path}: {exc}") from exc
        if not isinstance(data, list):
            raise SkillFixtureError("skill fixture must contain a JSON array")
        try:
            # JSON 模式校验：strict 下 JSON 数组正确映射到 tuple 字段。
            skills = [
                SkillMetadata.model_validate_json(json.dumps(entry))
                for entry in data
            ]
        except ValidationError as exc:
            raise SkillFixtureError(f"invalid skill fixture: {exc}") from exc
        return cls(skills)

    def load(
        self,
        *,
        agent: AgentName,
        tenant: str,
        market: str,
        locale: str,
        channel: str,
        as_of: str,
    ) -> SkillSet:
        """Load the minimal skill set for one scope.

        Picks the highest approved-or-draft version per kind; a skill that is
        expired or revoked at ``as_of`` blocks the scope with a typed error
        instead of being silently skipped.
        """
        chosen: dict[SkillKind, SkillMetadata] = {}
        as_of_dt = parse_utc(as_of)
        for kind in REQUIRED_SKILL_KINDS:
            candidates = [
                skill
                for skill in self._skills
                if skill.agent == agent
                and skill.kind == kind
                and skill.tenant == tenant
                and market in skill.markets
                and locale in skill.locales
                and channel in skill.channels
                and parse_utc(skill.effective_from) <= as_of_dt
            ]
            if not candidates:
                raise SkillNotFoundError(
                    f"no {kind} skill for agent={agent} tenant={tenant} "
                    f"market={market} locale={locale} channel={channel}"
                )
            best = max(candidates, key=lambda skill: _semver_key(skill.version))
            if best.revoked_at is not None or best.approval_status == "REVOKED":
                raise SkillRevokedError(
                    f"skill {best.skill_id!r} v{best.version} is revoked"
                )
            if best.expires_at is not None and parse_utc(best.expires_at) <= as_of_dt:
                raise SkillExpiredError(
                    f"skill {best.skill_id!r} v{best.version} expired at "
                    f"{best.expires_at}"
                )
            chosen[kind] = best
        return SkillSet(
            brand=chosen["brand"],
            medical=chosen["medical"],
            market=chosen["market"],
            channel=chosen["channel"],
        )


def _semver_key(version: str) -> tuple[int, int, int]:
    major, minor, patch = version.split(".")
    return int(major), int(minor), int(patch)
