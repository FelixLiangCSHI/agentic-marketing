from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from streamlit_demo.approval_engine import ApprovalEngine
from streamlit_demo.configuration_store import (
    CONFIG_PATH_ENV,
    LocalConfigurationStore,
)
from streamlit_demo.data_models import (
    ApplicationConfiguration,
    ServiceConfiguration,
)
from streamlit_demo.workflow import ConfigurationWorkflow


ROOT = Path(__file__).resolve().parents[1]


def configuration(
    *,
    credential: str = "test-credential",
    saved_at: str | None = None,
) -> ApplicationConfiguration:
    return ApplicationConfiguration(
        ai_insight=ServiceConfiguration("mock://ai-insight", credential),
        ai_plan=ServiceConfiguration("mock://ai-plan", credential),
        buffer=ServiceConfiguration("mock://buffer", credential),
        **({"saved_at": saved_at} if saved_at else {}),
    )


class ConfigurationWorkflowTests(unittest.TestCase):
    def test_valid_connections_are_saved_and_loaded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = LocalConfigurationStore(Path(directory) / "config.json")
            workflow = ConfigurationWorkflow(store)

            results = workflow.validate_and_save(configuration())

            self.assertTrue(all(result.success for result in results))
            loaded = store.load()
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded, configuration(saved_at=loaded.saved_at))

    def test_invalid_connections_are_not_saved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = LocalConfigurationStore(Path(directory) / "config.json")
            workflow = ConfigurationWorkflow(store)

            results = workflow.validate_and_save(configuration(credential=""))

            self.assertFalse(all(result.success for result in results))
            self.assertIsNone(store.load())


class BufferSchedulingTests(unittest.TestCase):
    def test_mock_endpoint_schedules_posts(self) -> None:
        from streamlit_demo.buffer_service import BufferService

        result = BufferService().schedule_posts(
            ServiceConfiguration("mock://buffer", "buffer-test-credential"),
            [
                {
                    "itemId": "item-1",
                    "text": "Post copy",
                    "scheduledAt": "2026-08-01T10:00:00+08:00",
                    "mediaUrls": [],
                    "linkUrl": None,
                }
            ],
        )

        self.assertTrue(result["success"])
        self.assertEqual(len(result["results"]), 1)
        self.assertTrue(result["results"][0]["success"])
        self.assertEqual(result["results"][0]["itemId"], "item-1")

    def test_missing_credential_is_rejected(self) -> None:
        from streamlit_demo.buffer_service import BufferService

        result = BufferService().schedule_posts(
            ServiceConfiguration("mock://buffer", ""),
            [{"itemId": "item-1", "text": "Post copy"}],
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["results"], [])

    def test_first_run_wizard_saves_and_future_launch_loads_configuration(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            configuration_path = Path(directory) / "config.json"
            with patch.dict(
                os.environ,
                {CONFIG_PATH_ENV: str(configuration_path)},
            ):
                app = AppTest.from_file(
                    str(ROOT / "streamlit_app.py"),
                    default_timeout=60,
                ).run()
                self.assertEqual(list(app.exception), [])

                steps = (
                    ("mock://ai-insight", "insight-test-credential"),
                    ("mock://ai-plan", "plan-test-credential"),
                    ("mock://buffer", "buffer-test-credential"),
                )
                for endpoint, credential in steps:
                    endpoint_input = next(
                        item
                        for item in app.text_input
                        if item.label == "Service Endpoint"
                    )
                    app = endpoint_input.set_value(endpoint).run()
                    credential_input = next(
                        item
                        for item in app.text_input
                        if item.label
                        in {
                            "AI API 1 Key",
                            "AI API 2 Key",
                            "Buffer Access Token",
                        }
                    )
                    app = credential_input.set_value(credential).run()
                    continue_button = next(
                        item
                        for item in app.button
                        if item.label == "Continue"
                    )
                    app = continue_button.click().run()

                validate_button = next(
                    item
                    for item in app.button
                    if item.label == "Validate All Connections"
                )
                app = validate_button.click().run()

                self.assertEqual(list(app.exception), [])
                self.assertTrue(configuration_path.is_file())
                self.assertFalse(
                    any(
                        item.label
                        in {
                            "AI API 1 Key",
                            "AI API 2 Key",
                            "Buffer Access Token",
                        }
                        for item in app.text_input
                    )
                )

                relaunched = AppTest.from_file(
                    str(ROOT / "streamlit_app.py"),
                    default_timeout=60,
                ).run()
                self.assertEqual(list(relaunched.exception), [])
                self.assertFalse(
                    any(
                        item.label == "AI API 1 Key"
                        for item in relaunched.text_input
                    )
                )
                navigation = next(
                    item
                    for item in relaunched.radio
                    if item.key == "active_stage"
                )
                relaunched = navigation.set_value("Settings").run()
                edit_button = next(
                    item
                    for item in relaunched.button
                    if item.label == "Edit Configuration"
                )
                relaunched = edit_button.click().run()
                insight_key = next(
                    item
                    for item in relaunched.text_input
                    if item.label == "AI API 1 Key"
                )
                self.assertEqual(insight_key.value, "")


class ApprovalEngineTests(unittest.TestCase):
    def test_revoking_insight_resets_dependent_strategy(self) -> None:
        analysis = {
            "strategyBundle": {
                "insights": [
                    {"insightId": "insight-1", "approvalStatus": "approved"}
                ],
                "strategies": [
                    {
                        "strategyId": "strategy-1",
                        "insightIds": ["insight-1"],
                        "approvalStatus": "approved",
                    }
                ],
            }
        }

        updated = ApprovalEngine().update_insight(
            analysis,
            "insight-1",
            "rejected",
        )

        self.assertEqual(
            updated["strategyBundle"]["strategies"][0]["approvalStatus"],
            "draft",
        )
        self.assertEqual(
            analysis["strategyBundle"]["strategies"][0]["approvalStatus"],
            "approved",
        )


if __name__ == "__main__":
    unittest.main()
