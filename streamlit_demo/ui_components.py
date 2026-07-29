"""Reusable layout components: header, journey stepper, settings, copilot."""

from __future__ import annotations

from typing import Any, Callable, Mapping, Sequence

import streamlit as st

from streamlit_demo.configuration_ui import begin_configuration_editing


STATUS_ICONS = {
    "completed": "✓",
    "running": "●",
    "pending": "○",
    "error": "⚠",
}

GLOBAL_STYLES = """
<style>
/* --- Journey stepper (sidebar) --- */
section[data-testid="stSidebar"] div[role="radiogroup"] > label {
    padding: 0.35rem 0.25rem;
    border-left: 2px solid rgba(128, 128, 128, 0.25);
    margin-left: 0.15rem;
}
section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) {
    border-left: 2px solid var(--primary-color, #ff4b4b);
    background: rgba(128, 128, 128, 0.08);
    border-radius: 0 0.4rem 0.4rem 0;
}

/* --- Floating Campaign Copilot --- */
div.st-key-copilot-fab {
    position: fixed;
    bottom: 1.5rem;
    right: 1.5rem;
    z-index: 999;
    width: auto;
}
div.st-key-copilot-fab button {
    border-radius: 999px;
    width: 3.25rem;
    height: 3.25rem;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.25);
}
div.st-key-copilot-panel {
    position: fixed;
    bottom: 1.5rem;
    right: 1.5rem;
    z-index: 999;
    width: min(23rem, calc(100vw - 2rem));
    max-height: 70vh;
    overflow-y: auto;
    background: var(--background-color, #ffffff);
    box-shadow: 0 8px 28px rgba(0, 0, 0, 0.25);
    border-radius: 0.75rem;
    padding: 1rem;
}
@media (max-width: 640px) {
    div.st-key-copilot-panel {
        width: calc(100vw - 2rem);
        max-height: 55vh;
    }
}
</style>
"""


def inject_global_styles() -> None:
    st.markdown(GLOBAL_STYLES, unsafe_allow_html=True)


def render_app_header(
    kicker: str,
    title: str,
    prepared_text: str,
    settings_panel: Callable[[], None],
) -> None:
    masthead, actions = st.columns([4, 1], vertical_alignment="bottom")
    with masthead:
        st.caption(kicker)
        st.title(title)
    with actions:
        st.caption(prepared_text)
        with st.popover(
            "Settings",
            icon=":material/settings:",
            help="Workspace settings",
            width="stretch",
        ):
            settings_panel()


def render_journey_stepper(
    options: Sequence[str],
    stage_states: Mapping[str, tuple[str, str]],
    extra_captions: Mapping[str, str],
    completed_count: int,
    total_count: int,
    key: str = "active_stage",
) -> None:
    st.subheader("Campaign Journey")
    st.progress(
        completed_count / total_count,
        text=f"{completed_count} of {total_count} steps complete",
    )

    def caption_for(stage: str) -> str:
        if stage in stage_states:
            status, text = stage_states[stage]
            return f"{STATUS_ICONS.get(status, '○')} {text}"
        return extra_captions.get(stage, "")

    st.radio(
        "Navigate to",
        options,
        key=key,
        label_visibility="collapsed",
        captions=[caption_for(stage) for stage in options],
    )


def _status_badge(ok: bool, label: str) -> str:
    color = "green" if ok else "gray"
    return f":{color}-badge[{label}]"


def render_settings_panel(
    connection_rows: Sequence[tuple[str, bool, str, str]],
    service_rows: Sequence[dict[str, Any]],
) -> None:
    """Render workspace settings.

    connection_rows: (name, connected, status label, detail caption).
    service_rows: table rows describing configured service endpoints.
    """
    st.caption("WORKSPACE SETTINGS")
    st.markdown("**Connections**")
    for name, connected, status_label, detail in connection_rows:
        name_column, badge_column = st.columns([2, 1])
        name_column.write(name)
        badge_column.markdown(_status_badge(connected, status_label))
        if detail:
            st.caption(detail)
    st.divider()

    st.markdown("**Preferences**")
    st.selectbox(
        "Brand voice",
        (
            "Clinical & evidence-led",
            "Executive & outcomes-focused",
            "Educational & accessible",
        ),
        key="brand_voice",
    )
    st.selectbox(
        "Compliance mode",
        ("Strict (medical device)", "Standard"),
        key="compliance_mode",
    )
    st.selectbox(
        "Theme",
        ("System", "Light", "Dark"),
        key="app_theme",
        help=(
            "Preference is stored for this workspace; switch the appearance "
            "from the Streamlit app menu."
        ),
    )
    st.caption(
        "Preferences guide AI drafting and review. They do not change the "
        "campaign journey progress."
    )
    st.divider()

    st.markdown("**Connected Services**")
    if service_rows:
        st.dataframe(list(service_rows), hide_index=True, width="stretch")
        st.caption(
            "Credentials remain hidden and are not requested again unless you "
            "choose to edit this configuration."
        )
        if st.button(
            "Edit Configuration",
            type="primary",
            icon=":material/settings:",
            key="settings-edit-configuration",
        ):
            begin_configuration_editing()
            st.rerun()
    else:
        st.info("Complete the first-run configuration wizard.")


def render_floating_copilot(
    stage: str,
    message: str,
    actions: Sequence[tuple[str, str]],
    on_navigate: Callable[[str], None],
) -> None:
    """Render the floating Campaign Copilot button and expandable panel."""
    if not st.session_state.get("copilot_open"):
        with st.container(key="copilot-fab"):
            if st.button(
                ":material/smart_toy:",
                key="copilot-open-button",
                help="Open Campaign Copilot",
            ):
                st.session_state["copilot_open"] = True
                st.rerun()
        return

    with st.container(key="copilot-panel"):
        title, minimize, close = st.columns(
            [4, 1, 1], vertical_alignment="center"
        )
        title.markdown("**Campaign Copilot**")
        if minimize.button(
            ":material/minimize:",
            key="copilot-minimize-button",
            help="Minimize the assistant",
        ):
            st.session_state["copilot_open"] = False
            st.rerun()
        if close.button(
            ":material/close:",
            key="copilot-close-button",
            help="Close the assistant",
        ):
            st.session_state["copilot_open"] = False
            st.rerun()
        st.caption(f"Guidance for: {stage}")
        st.write(message)
        for index, (label, target_stage) in enumerate(actions):
            if st.button(
                label,
                key=f"copilot-action-{index}",
                width="stretch",
            ):
                st.session_state["copilot_open"] = False
                on_navigate(target_stage)
