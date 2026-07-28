from __future__ import annotations

from typing import Any

import streamlit as st

from streamlit_demo.data_models import (
    ApplicationConfiguration,
    ConnectionResult,
    ServiceConfiguration,
)
from streamlit_demo.workflow import ConfigurationWorkflow


STEP_TITLES = {
    1: "Configure AI Insight Service (AI API 1)",
    2: "Configure AI 30-day Plan Service (AI API 2)",
    3: "Configure Buffer (Buffer API)",
    4: "Validate all connections",
}


def _configuration_draft(
    configuration: ApplicationConfiguration | None,
) -> dict[str, str]:
    if configuration is None:
        return {
            "insight_endpoint": "",
            "insight_credential": "",
            "plan_endpoint": "",
            "plan_credential": "",
            "buffer_endpoint": "",
            "buffer_credential": "",
        }
    return {
        "insight_endpoint": configuration.ai_insight.endpoint,
        "insight_credential": configuration.ai_insight.credential,
        "plan_endpoint": configuration.ai_plan.endpoint,
        "plan_credential": configuration.ai_plan.credential,
        "buffer_endpoint": configuration.buffer.endpoint,
        "buffer_credential": configuration.buffer.credential,
    }


def initialize_configuration_state(workflow: ConfigurationWorkflow) -> None:
    if "configuration" not in st.session_state:
        st.session_state["configuration"] = workflow.load()
    st.session_state.setdefault("configuration_editing", False)
    st.session_state.setdefault("configuration_wizard_step", 1)
    st.session_state.setdefault("configuration_validation_results", [])
    if "configuration_draft" not in st.session_state:
        st.session_state["configuration_draft"] = _configuration_draft(
            st.session_state["configuration"]
        )


def _draft_configuration() -> ApplicationConfiguration:
    draft = st.session_state["configuration_draft"]
    return ApplicationConfiguration(
        ai_insight=ServiceConfiguration(
            draft["insight_endpoint"].strip(),
            draft["insight_credential"].strip(),
        ),
        ai_plan=ServiceConfiguration(
            draft["plan_endpoint"].strip(),
            draft["plan_credential"].strip(),
        ),
        buffer=ServiceConfiguration(
            draft["buffer_endpoint"].strip(),
            draft["buffer_credential"].strip(),
        ),
    )


def _service_fields(
    endpoint_key: str,
    credential_key: str,
    *,
    credential_label: str,
) -> None:
    draft = st.session_state["configuration_draft"]
    endpoint = st.text_input(
        "Service Endpoint",
        value=draft[endpoint_key],
        placeholder="https://service.example.com",
        key=f"configuration-{endpoint_key}",
    )
    credential = st.text_input(
        credential_label,
        value=draft[credential_key],
        type="password",
        key=f"configuration-{credential_key}",
    )
    draft[endpoint_key] = endpoint
    draft[credential_key] = credential


def _navigation(step: int) -> None:
    left, right = st.columns(2)
    if left.button("Back", disabled=step == 1, width="stretch"):
        st.session_state["configuration_wizard_step"] = step - 1
        st.rerun()
    if right.button("Continue", type="primary", width="stretch"):
        st.session_state["configuration_wizard_step"] = step + 1
        st.rerun()


def _render_validation_results(results: list[ConnectionResult]) -> None:
    labels = {
        "ai_insight": "AI Insight Service",
        "ai_plan": "AI 30-day Plan Service",
        "buffer": "Buffer",
    }
    for result in results:
        message = f"{labels[result.service]}: {result.message}"
        if result.success:
            st.success(message)
        else:
            st.error(message)


@st.dialog("Workspace Configuration", width="large", dismissible=False)
def render_configuration_dialog(workflow: ConfigurationWorkflow) -> None:
    step = int(st.session_state["configuration_wizard_step"])
    st.caption(f"Step {step} of 4")
    st.subheader(STEP_TITLES[step])

    if step == 1:
        _service_fields(
            "insight_endpoint",
            "insight_credential",
            credential_label="AI API 1 Key",
        )
        _navigation(step)
    elif step == 2:
        _service_fields(
            "plan_endpoint",
            "plan_credential",
            credential_label="AI API 2 Key",
        )
        _navigation(step)
    elif step == 3:
        _service_fields(
            "buffer_endpoint",
            "buffer_credential",
            credential_label="Buffer Access Token",
        )
        _navigation(step)
    else:
        st.write(
            "Test the two AI services and Buffer before saving this "
            "configuration locally."
        )
        results = st.session_state["configuration_validation_results"]
        _render_validation_results(results)
        left, right = st.columns(2)
        if left.button("Back", width="stretch"):
            st.session_state["configuration_validation_results"] = []
            st.session_state["configuration_wizard_step"] = 3
            st.rerun()
        if right.button(
            "Validate All Connections",
            type="primary",
            width="stretch",
        ):
            configuration = _draft_configuration()
            try:
                validation = list(workflow.validate_and_save(configuration))
            except OSError:
                st.error("The local configuration could not be saved.")
                return
            st.session_state["configuration_validation_results"] = validation
            if all(result.success for result in validation):
                st.session_state["configuration"] = configuration
                st.session_state["configuration_editing"] = False
                st.session_state["configuration_wizard_step"] = 1
                st.session_state["configuration_validation_results"] = []
                st.session_state["_configuration_notice"] = (
                    "All connections were validated and the configuration was saved."
                )
                st.rerun()
            st.rerun()

    if (
        st.session_state.get("configuration") is not None
        and st.session_state.get("configuration_editing")
    ):
        if st.button("Cancel Editing", width="stretch"):
            st.session_state["configuration_editing"] = False
            st.session_state["configuration_wizard_step"] = 1
            st.session_state["configuration_validation_results"] = []
            st.session_state["configuration_draft"] = _configuration_draft(
                st.session_state["configuration"]
            )
            st.rerun()


def configuration_dialog_required() -> bool:
    return (
        st.session_state.get("configuration") is None
        or st.session_state.get("configuration_editing", False)
    )


def _masked_credential(credential: str) -> str:
    return "Configured" if credential else "Not configured"


def render_settings() -> None:
    st.markdown(
        '<span class="section-kicker">Local configuration</span>',
        unsafe_allow_html=True,
    )
    st.header("Settings")
    configuration = st.session_state.get("configuration")
    if not isinstance(configuration, ApplicationConfiguration):
        st.info("Complete the first-run configuration wizard.")
        return

    rows: list[dict[str, Any]] = []
    for label, service in (
        ("AI Insight Service", configuration.ai_insight),
        ("AI 30-day Plan Service", configuration.ai_plan),
        ("Buffer", configuration.buffer),
    ):
        rows.append(
            {
                "Service": label,
                "Endpoint": service.endpoint,
                "Credential": _masked_credential(service.credential),
            }
        )
    st.dataframe(rows, hide_index=True, width="stretch")
    st.caption(
        "Credentials remain hidden and are not requested again unless you choose "
        "to edit this configuration."
    )
    if st.button("Edit Configuration", type="primary"):
        st.session_state["configuration_editing"] = True
        st.session_state["configuration_wizard_step"] = 1
        st.session_state["configuration_validation_results"] = []
        st.session_state["configuration_draft"] = _configuration_draft(
            configuration
        )
        st.rerun()

