from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest
from streamlit_demo.configuration_store import CONFIG_PATH_ENV, LocalConfigurationStore
from streamlit_demo.data_models import (
    ApplicationConfiguration,
    ServiceConfiguration,
)


ROOT = Path(__file__).resolve().parents[1]


def navigate(app: AppTest, stage: str, timeout: float = 30) -> AppTest:
    navigation = next(
        radio for radio in app.radio if radio.key == "active_stage"
    )
    return navigation.set_value(stage).run(timeout=timeout)


def click_key(app: AppTest, key: str, timeout: float = 60) -> AppTest:
    button = next(item for item in app.button if item.key == key)
    return button.click().run(timeout=timeout)


def click_label(app: AppTest, label: str, timeout: float = 60) -> AppTest:
    button = next(item for item in app.button if item.label == label)
    return button.click().run(timeout=timeout)


class StreamlitDemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.configuration_directory = tempfile.TemporaryDirectory()
        configuration_path = (
            Path(cls.configuration_directory.name) / "config.json"
        )
        os.environ[CONFIG_PATH_ENV] = str(configuration_path)
        LocalConfigurationStore(configuration_path).save(
            ApplicationConfiguration(
                ai_insight=ServiceConfiguration(
                    "mock://ai-insight",
                    "test-credential",
                ),
                ai_plan=ServiceConfiguration(
                    "mock://ai-plan",
                    "test-credential",
                ),
                buffer=ServiceConfiguration(
                    "mock://buffer",
                    "test-credential",
                ),
            )
        )

    @classmethod
    def tearDownClass(cls) -> None:
        os.environ.pop(CONFIG_PATH_ENV, None)
        cls.configuration_directory.cleanup()

    def test_uploaded_synthetic_fixtures_analyze_and_export(self) -> None:
        fixtures = {
            "followers": (
                "synthetic_upload_followers.csv",
                (
                    "Synthetic test fixture - no real company data\n"
                    "Date,Total followers,New followers\n"
                    "2026-01-01,100,10\n"
                    "2026-01-02,112,12\n"
                    "2026-01-03,125,13\n"
                ).encode(),
            ),
            "visitors": (
                "synthetic_upload_visitors.csv",
                (
                    "Synthetic test fixture - no real company data\n"
                    "Date,Total page views,Total unique visitors\n"
                    "2026-01-01,200,100\n"
                    "2026-01-02,240,120\n"
                    "2026-01-03,300,150\n"
                ).encode(),
            ),
            "content": (
                "synthetic_upload_content.csv",
                (
                    "Synthetic test fixture - no real company data\n"
                    "Post title,Created date,Content Type,Impressions,"
                    "Clicks,Likes,Comments,Reposts\n"
                    "Ultrasound clinical workflow evidence,2026-01-01,Document,100,5,3,1,1\n"
                    "Patient monitoring outcomes briefing,2026-01-02,Document,100,10,5,3,2\n"
                    "Endoscopy KOL procedure review,2026-01-03,Video,100,20,8,4,3\n"
                ).encode(),
            ),
        }
        app = AppTest.from_file(
            str(ROOT / "streamlit_app.py"),
            default_timeout=60,
        ).run()

        for module, (name, content) in fixtures.items():
            uploader = next(
                item
                for item in app.get("file_uploader")
                if item.key == f"upload-{module}-0"
            )
            app = uploader.upload(name, content, "text/csv").run()

        app = click_label(
            app,
            "Process Data and Create Snapshot",
            timeout=90,
        )
        state = app.session_state.filtered_state
        self.assertEqual(list(app.exception), [])
        self.assertEqual(state["mode"], "uploaded")
        self.assertEqual(state["analysis"]["analysisStatus"], "ready")
        self.assertEqual(
            state["analysis"]["snapshot"]["records"],
            {"followers": 3, "visitors": 3, "content": 3},
        )

        app = navigate(app, "Data Intake")
        self.assertEqual(list(app.exception), [])
        self.assertTrue(
            any(
                "File Recognition Results" in markdown.value
                for markdown in app.markdown
            )
        )

        app = navigate(app, "Audience & Content Insights")
        self.assertTrue(
            any(
                "predefined demonstration rules" in info.value
                for info in app.info
            )
        )

        app = navigate(app, "Reports & Exports")
        app = click_label(app, "Prepare Campaign Reports")
        structured = app.session_state.filtered_state[
            "export_artifacts"
        ]["structuredJson"]["content"]
        self.assertEqual(json.loads(structured)["snapshot"]["inputMode"], "uploaded")
        self.assertNotIn("Synthetic test fixture - no real company data", structured)

    def test_complete_synthetic_demo_edit_chat_export_and_clear(self) -> None:
        app = AppTest.from_file(
            str(ROOT / "streamlit_app.py"),
            default_timeout=60,
        ).run()
        self.assertEqual(list(app.exception), [])
        self.assertEqual(len(app.get("file_uploader")), 3)

        app = click_label(app, "Start with Sample Data")
        state = app.session_state.filtered_state
        self.assertEqual(list(app.exception), [])
        self.assertEqual(state["mode"], "mock")
        self.assertEqual(state["analysis"]["analysisStatus"], "ready")
        self.assertEqual(state["active_stage"], "Performance Metrics")

        approval_steps = (
            (
                "Audience & Content Insights",
                (
                    "approve-insight-audience-followers",
                    "approve-insight-audience-visitors",
                    "approve-insight-content-performance",
                ),
            ),
            (
                "Campaign Strategy",
                (
                    "approve-strategy-content-experiment",
                    "approve-strategy-audience-path",
                ),
            ),
        )
        for stage, keys in approval_steps:
            app = navigate(app, stage)
            for key in keys:
                app = click_key(app, key)
            self.assertEqual(list(app.exception), [])

        app = navigate(app, "30-Day Campaign Plan")
        goal_confirmation = next(
            item
            for item in app.checkbox
            if item.key == "business_goal_confirmed"
        )
        app = goal_confirmation.set_value(True).run()
        app = click_label(app, "Create Campaign Draft", timeout=90)
        plan = app.session_state.filtered_state["plan"]
        self.assertEqual(list(app.exception), [])
        self.assertEqual(len(plan["fourWeekPlan"]), 4)
        self.assertEqual(len(plan["contentCalendar"]), 8)
        self.assertEqual(plan["status"], "ai_draft")

        topic_input = next(
            item for item in app.text_input if item.label == "Topic"
        )
        app = topic_input.set_value("用户确认的实验主题").run()
        app = click_label(app, "Save Item Changes", timeout=60)
        edited_plan = app.session_state.filtered_state["plan"]
        self.assertEqual(
            edited_plan["contentCalendar"][0]["topic"],
            "用户确认的实验主题",
        )
        app = click_label(app, "Undo Last Change")
        restored_plan = app.session_state.filtered_state["plan"]
        self.assertNotEqual(
            restored_plan["contentCalendar"][0]["topic"],
            "用户确认的实验主题",
        )

        app = click_label(app, "Approve Current Plan", timeout=60)
        self.assertEqual(
            app.session_state.filtered_state["plan"]["status"],
            "user_confirmed",
        )
        app = navigate(app, "Buffer Handoff", timeout=90)
        state = app.session_state.filtered_state
        self.assertEqual(list(app.exception), [])
        preview = state["buffer_preview"]
        self.assertIsNotNone(preview)
        self.assertGreater(preview["summary"]["exportableCount"], 0)
        self.assertEqual(preview["summary"]["blockingErrorCount"], 0)
        self.assertGreater(preview["summary"]["warningCount"], 0)
        self.assertFalse(
            any(
                issue["code"] == "UNSUPPORTED_BULK_POST_TYPE"
                for review in preview["reviews"]
                for issue in review["issues"]
            )
        )
        format_control = next(
            item for item in app.selectbox if item.label == "Content Format"
        )
        app = format_control.set_value("Document Carousel").run(timeout=60)
        app = click_label(app, "Save and Revalidate", timeout=90)
        preview = app.session_state.filtered_state["buffer_preview"]
        self.assertIsNotNone(preview)
        self.assertGreater(preview["summary"]["blockingErrorCount"], 0)
        blocked_review = next(
            review
            for review in preview["reviews"]
            if any(
                issue["code"] == "UNSUPPORTED_BULK_POST_TYPE"
                for issue in review["issues"]
            )
            and review["inDateRange"]
            and review["channelIncluded"]
        )
        blocked_topic = blocked_review["contentItem"]["topic"]
        editor = next(
            item
            for item in app.selectbox
            if str(item.key).startswith("buffer-editor-item-")
        )
        blocked_label = next(
            option for option in editor.options if blocked_topic in option
        )
        app = editor.set_value(blocked_label).run(timeout=60)
        format_control = next(
            item for item in app.selectbox if item.label == "Content Format"
        )
        app = format_control.set_value("Text Post").run(timeout=60)
        app = click_label(app, "Save and Revalidate", timeout=90)
        preview = app.session_state.filtered_state["buffer_preview"]
        self.assertIsNotNone(preview)
        self.assertEqual(preview["summary"]["blockingErrorCount"], 0)

        warning_ack = next(
            item
            for item in app.checkbox
            if item.key == "buffer_warnings_acknowledged"
        )
        app = warning_ack.set_value(True).run(timeout=60)
        app = click_label(
            app,
            "Create Buffer Handoff Files",
            timeout=90,
        )
        state = app.session_state.filtered_state
        result = state["buffer_export_result"]
        self.assertEqual(list(app.exception), [])
        self.assertIsNotNone(result)
        self.assertEqual(len(result["artifacts"]), 2)
        self.assertTrue(
            all(
                artifact["content"].startswith(
                    '\ufeff"Text","Image URL","Tags","Posting Time"'
                )
                for artifact in result["artifacts"]
            )
        )
        self.assertGreater(
            len(result["exportRecord"]["exportedItemIds"]),
            0,
        )
        self.assertTrue(
            all(
                item["workflowStatus"] != "published"
                for item in state["plan"]["contentCalendar"]
            )
        )
        self.assertTrue(
            any(
                "Buffer Import Checklist" in heading.value
                for heading in app.subheader
            )
        )

        app = navigate(app, "Campaign Evidence")
        app = click_key(app, "quick-0", timeout=60)
        chat = app.session_state.filtered_state["chat_history"]
        self.assertEqual(chat[-1]["role"], "assistant")
        self.assertEqual(chat[-1]["answer"]["status"], "answered")
        self.assertGreater(len(chat[-1]["answer"]["citations"]), 0)

        app = navigate(app, "Reports & Exports")
        app = click_label(app, "Prepare Campaign Reports", timeout=60)
        artifacts = app.session_state.filtered_state["export_artifacts"]
        self.assertEqual(
            app.session_state.filtered_state["export_status"],
            "ready",
        )
        self.assertIn("## Executive Summary", artifacts["markdown"]["content"])
        self.assertTrue(artifacts["calendarCsv"]["content"].startswith("\ufeff"))
        structured = artifacts["structuredJson"]["content"]
        self.assertNotIn('"rawValues"', structured)
        self.assertNotIn('"fileName"', structured)
        self.assertFalse(
            json.loads(structured)["privacy"]["containsRawFile"]
        )

        app = click_label(app, "Clear Campaign Data")
        cleared = app.session_state.filtered_state
        self.assertEqual(list(app.exception), [])
        self.assertIsNone(cleared["analysis"])
        self.assertIsNone(cleared["plan"])
        self.assertIsNone(cleared["export_artifacts"])
        self.assertEqual(cleared["buffer_export_records"], [])

    def test_buffer_handoff_empty_state_without_plan(self) -> None:
        app = AppTest.from_file(
            str(ROOT / "streamlit_app.py"),
            default_timeout=60,
        ).run()
        app = navigate(app, "Buffer Handoff")
        self.assertEqual(list(app.exception), [])
        self.assertTrue(
            any(
                "Create a 30-day campaign plan first" in info.value
                for info in app.info
            )
        )


if __name__ == "__main__":
    unittest.main()
