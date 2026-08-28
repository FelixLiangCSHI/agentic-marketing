"""Phase 03 contract fixture: a deterministic RC package document.

The fixture is regenerated from the builder on every test run and must
be byte-identical to the committed file — Phase 03 (Campaign Agent) can
develop against a stable, verified sample.
"""

from __future__ import annotations

import json
from pathlib import Path

from builders import AS_OF, make_inputs

from content_package import PackageBuilder, consumable, verify_package_integrity

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "phase03"
    / "approved-content-package.sample.json"
)


def _build_document() -> dict[str, object]:
    package = PackageBuilder().build(make_inputs(), as_of=AS_OF)
    return dict(package.model_dump(mode="json"))


class TestPhase03Fixture:
    def test_fixture_matches_builder_output_exactly(self) -> None:
        document = _build_document()
        committed = json.loads(FIXTURE.read_text(encoding="utf-8"))
        assert document == committed

    def test_fixture_is_independently_verifiable(self) -> None:
        from content_package import ApprovedContentPackageV1

        committed = ApprovedContentPackageV1.model_validate(
            json.loads(FIXTURE.read_text(encoding="utf-8")), strict=False
        )
        assert verify_package_integrity(committed)
        assert consumable(committed, as_of=AS_OF) == (True, "consumable")
