from __future__ import annotations

from collections.abc import Sequence

from streamlit_demo.buffer_service import BufferService
from streamlit_demo.configuration_store import LocalConfigurationStore
from streamlit_demo.data_models import ApplicationConfiguration, ConnectionResult
from streamlit_demo.mock_ai_service import MockAIService


class ConfigurationWorkflow:
    def __init__(
        self,
        store: LocalConfigurationStore | None = None,
        ai_service: MockAIService | None = None,
        buffer_service: BufferService | None = None,
    ) -> None:
        self.store = store or LocalConfigurationStore()
        self.ai_service = ai_service or MockAIService()
        self.buffer_service = buffer_service or BufferService()

    def load(self) -> ApplicationConfiguration | None:
        return self.store.load()

    def validate(
        self,
        configuration: ApplicationConfiguration,
    ) -> Sequence[ConnectionResult]:
        return (
            self.ai_service.validate_connection(
                "ai_insight", configuration.ai_insight
            ),
            self.ai_service.validate_connection("ai_plan", configuration.ai_plan),
            self.buffer_service.validate_connection(configuration.buffer),
        )

    def validate_and_save(
        self,
        configuration: ApplicationConfiguration,
    ) -> Sequence[ConnectionResult]:
        results = self.validate(configuration)
        if all(result.success for result in results):
            self.store.save(configuration)
        return results

