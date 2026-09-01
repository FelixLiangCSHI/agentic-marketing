"""Skill registry tests: minimal loading, expiry/revocation blocking,
fixture integrity and version selection."""

from __future__ import annotations

from pathlib import Path
import hashlib

import pytest

from content_workflow import (
    SkillExpiredError,
    SkillFixtureError,
    SkillMetadata,
    SkillNotFoundError,
    SkillRegistry,
    SkillRevokedError,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "skills.json"
AS_OF = "2026-06-01T00:00:00Z"


@pytest.fixture()
def registry() -> SkillRegistry:
    return SkillRegistry.from_fixture_file(FIXTURE)


def _skill(kind: str, **overrides: object) -> SkillMetadata:
    guidance = str(overrides.pop("guidance", f"{kind} guidance"))
    payload: dict[str, object] = {
        "schema_version": "1.0",
        "skill_id": f"skill-{kind}-fractional",
        "version": "1.0.0",
        "agent": "content",
        "kind": kind,
        "owner": "owner-1",
        "tenant": "tenant-cshi",
        "markets": ("US",),
        "locales": ("en-US",),
        "channels": ("linkedin",),
        "approval_status": "APPROVED",
        "effective_from": "2026-01-01T00:00:00Z",
        "expires_at": "2027-01-01T00:00:00Z",
        "revoked_at": None,
        "guidance": guidance,
        "content_hash": "sha256:" + hashlib.sha256(guidance.encode()).hexdigest(),
    }
    payload.update(overrides)
    return SkillMetadata.model_validate(payload)


class TestMinimalLoad:
    def test_loads_one_skill_per_kind_for_scope(
        self, registry: SkillRegistry
    ) -> None:
        skill_set = registry.load(
            agent="content",
            tenant="tenant-cshi",
            market="US",
            locale="en-US",
            channel="linkedin",
            as_of=AS_OF,
        )
        assert skill_set.brand.skill_id == "skill-brand-core"
        assert skill_set.medical.skill_id == "skill-medical-us"
        assert skill_set.market.skill_id == "skill-market-us"
        assert skill_set.channel.skill_id == "skill-channel-linkedin"
        assert skill_set.all_approved
        assert skill_set.versions == {
            "skill-brand-core": "1.2.0",
            "skill-medical-us": "2.0.0",
            "skill-market-us": "1.1.0",
            "skill-channel-linkedin": "1.0.0",
        }

    def test_draft_skill_loads_but_marks_set_unapproved(
        self, registry: SkillRegistry
    ) -> None:
        skill_set = registry.load(
            agent="content",
            tenant="tenant-cshi",
            market="US",
            locale="en-US",
            channel="google_ads",
            as_of=AS_OF,
        )
        assert skill_set.channel.approval_status == "DRAFT"
        assert not skill_set.all_approved

    def test_missing_scope_raises_typed_error(
        self, registry: SkillRegistry
    ) -> None:
        with pytest.raises(SkillNotFoundError):
            registry.load(
                agent="content",
                tenant="tenant-other",
                market="US",
                locale="en-US",
                channel="linkedin",
                as_of=AS_OF,
            )


class TestExpiryAndRevocation:
    def test_expired_skill_blocks_scope(self, registry: SkillRegistry) -> None:
        with pytest.raises(SkillExpiredError):
            registry.load(
                agent="content",
                tenant="tenant-cshi",
                market="US",
                locale="de-DE",
                channel="linkedin",
                as_of=AS_OF,
            )

    def test_expired_skill_valid_before_expiry(
        self, registry: SkillRegistry
    ) -> None:
        skill_set = registry.load(
            agent="content",
            tenant="tenant-cshi",
            market="US",
            locale="de-DE",
            channel="linkedin",
            as_of="2026-04-01T00:00:00Z",
        )
        assert skill_set.medical.skill_id == "skill-medical-de-expired"

    def test_fractional_expiry_after_as_of_is_valid(self) -> None:
        registry = SkillRegistry(
            [
                _skill("brand", expires_at="2026-06-01T00:00:00.5Z"),
                _skill("medical"),
                _skill("market"),
                _skill("channel"),
            ]
        )

        skill_set = registry.load(
            agent="content",
            tenant="tenant-cshi",
            market="US",
            locale="en-US",
            channel="linkedin",
            as_of="2026-06-01T00:00:00Z",
        )

        assert skill_set.brand.skill_id == "skill-brand-fractional"

    def test_revoked_skill_blocks_scope(self, registry: SkillRegistry) -> None:
        with pytest.raises(SkillRevokedError):
            registry.load(
                agent="content",
                tenant="tenant-cshi",
                market="CN",
                locale="zh-CN",
                channel="linkedin",
                as_of=AS_OF,
            )


class TestFixtureIntegrity:
    def test_content_hash_mismatch_rejected_at_load(self) -> None:
        registry = SkillRegistry.from_fixture_file(FIXTURE)
        skill = registry.load(
            agent="content",
            tenant="tenant-cshi",
            market="US",
            locale="en-US",
            channel="linkedin",
            as_of=AS_OF,
        ).brand
        tampered = SkillMetadata.model_validate_json(
            skill.model_copy(update={"guidance": "tampered text"}).model_dump_json()
        )
        with pytest.raises(SkillFixtureError):
            SkillRegistry([tampered])

    def test_skill_metadata_is_frozen(self, registry: SkillRegistry) -> None:
        skill = registry.load(
            agent="content",
            tenant="tenant-cshi",
            market="US",
            locale="en-US",
            channel="linkedin",
            as_of=AS_OF,
        ).medical
        with pytest.raises(Exception):
            skill.guidance = "mutated"  # type: ignore[misc,unused-ignore]
