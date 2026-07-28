from __future__ import annotations

import unittest
from pathlib import Path

from streamlit_demo.bridge_client import (
    BridgeClient,
    BridgeClientError,
    encode_upload,
)


ROOT = Path(__file__).resolve().parents[1]


class BridgeClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = BridgeClient(ROOT)

    def test_health_uses_short_lived_non_persistent_runtime(self) -> None:
        health = self.client.call("health")
        self.assertEqual(health["status"], "ok")
        self.assertEqual(health["runtime"], "short-lived-node-process")
        self.assertFalse(health["rawFilePersistence"])

    def test_uses_committed_bundle_without_node_modules_at_runtime(self) -> None:
        self.assertEqual(
            Path(self.client.command[-1]).resolve(),
            (ROOT / "dist" / "streamlit-bridge.cjs").resolve(),
        )
        self.assertNotIn("node_modules", self.client.command[-1])

    def test_synthetic_analysis_is_complete_and_deterministic(self) -> None:
        first = self.client.call(
            "analyze_synthetic",
            {"now": "2026-07-28T01:00:00.000Z"},
        )
        second = self.client.call(
            "analyze_synthetic",
            {"now": "2026-07-28T01:00:00.000Z"},
        )
        self.assertEqual(first["analysisStatus"], "ready")
        self.assertEqual(len(first["parseSummaries"]), 3)
        self.assertEqual(
            first["snapshot"]["snapshotId"],
            second["snapshot"]["snapshotId"],
        )

    def test_file_bytes_are_validated_by_the_node_bridge(self) -> None:
        invalid = encode_upload(
            slot="followers",
            name="followers.csv",
            mime_type="text/csv",
            data=b"\x00\x01\x02",
        )
        with self.assertRaises(BridgeClientError) as context:
            self.client.call(
                "analyze_uploads",
                {
                    "now": "2026-07-28T01:00:00.000Z",
                    "files": [invalid],
                },
            )
        self.assertEqual(
            context.exception.failure.code,
            "FILE_SIGNATURE_MISMATCH",
        )
        self.assertTrue(context.exception.failure.preserve_project_data)

    def test_timeout_preserves_the_current_project(self) -> None:
        with self.assertRaises(BridgeClientError) as context:
            self.client.call(
                "analyze_synthetic",
                timeout_seconds=0.0001,
            )
        self.assertEqual(
            context.exception.failure.code,
            "BRIDGE_UNAVAILABLE",
        )
        self.assertTrue(context.exception.failure.preserve_project_data)


if __name__ == "__main__":
    unittest.main()
