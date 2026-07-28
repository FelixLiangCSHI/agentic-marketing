from __future__ import annotations

import copy
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import streamlit as st

from streamlit_demo.bridge_client import (
    BridgeClient,
    BridgeClientError,
    BridgeFailure,
    encode_upload,
)


APP_TITLE = "Medical Device LinkedIn Campaign Workspace"
MODULES = ("followers", "visitors", "content")
MODULE_LABELS = {
    "followers": "Followers",
    "visitors": "Visitors",
    "content": "Content",
}
MODULE_IMPACTS = {
    "followers": "Required for follower growth and audience profile analysis.",
    "visitors": "Required for company page traffic and audience analysis.",
    "content": "Required for content performance and campaign planning.",
}
NAVIGATION = (
    "Data Intake",
    "Data Quality",
    "Performance Metrics",
    "Audience Insights",
    "Content Insights",
    "Campaign Strategy",
    "30-Day Campaign Plan",
    "Buffer Handoff",
    "Campaign Evidence",
    "Reports & Exports",
)
PIPELINE_STAGES = (
    "Data Intake",
    "Data Quality",
    "Performance Metrics",
    "Audience Insights",
    "Content Insights",
    "Campaign Strategy",
    "30-Day Campaign Plan",
    "Buffer Handoff",
)
TIME_ZONES = (
    "Asia/Shanghai",
    "Asia/Singapore",
    "Europe/London",
    "America/Los_Angeles",
    "America/New_York",
    "UTC",
)
QUICK_QUESTIONS = (
    "How is follower growth trending?",
    "How is company page traffic trending?",
    "What is the current engagement rate?",
    "What should the campaign publish next month?",
    "What are the current data quality limitations?",
)
BUFFER_CHANNEL_LABELS = {
    "linkedin_page": "LinkedIn Page",
    "linkedin_profile": "LinkedIn Profile",
}
BUFFER_APPROVAL_LABELS = {
    "ai_draft": "Draft / Pending Review",
    "confirmed": "Approved",
    "rejected": "Rejected",
}
BUFFER_WORKFLOW_LABELS = {
    "planning": "Planning",
    "ready_for_buffer": "Ready for Buffer",
    "exported_to_buffer": "Handoff File Created",
    "published": "Publication Confirmed",
    "failed": "Handoff Failed",
}
BUFFER_BULK_UPLOAD_URL = (
    "https://support.buffer.com/article/"
    "926-how-to-upload-posts-in-bulk-to-buffer"
)


st.set_page_config(
    page_title=APP_TITLE,
    page_icon="L",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    :root {
      --brand: #0a66c2;
      --ink: #172033;
      --muted: #5f6b7a;
      --line: #d9e2ec;
      --surface: #ffffff;
      --soft: #edf4fb;
      --success: #147d64;
      --warning: #946200;
      --danger: #b42318;
    }
    .stApp { background: #f4f7fa; color: var(--ink); }
    .block-container { max-width: 1480px; padding-top: 1.25rem; }
    .demo-hero {
      background: linear-gradient(135deg, #102a43 0%, #0a66c2 100%);
      border-radius: 18px;
      color: white;
      padding: 1.5rem 1.75rem;
      margin-bottom: 1rem;
      box-shadow: 0 12px 32px rgba(16, 42, 67, .14);
    }
    .demo-hero__eyebrow {
      font-size: .75rem;
      font-weight: 700;
      letter-spacing: .12em;
      opacity: .78;
      text-transform: uppercase;
    }
    .demo-hero h1 { color: white; font-size: 2rem; margin: .25rem 0; }
    .demo-hero p { margin: 0; max-width: 850px; opacity: .9; }
    .privacy-panel {
      background: #eff8ff;
      border: 1px solid #b9dcff;
      border-radius: 12px;
      color: #163a5f;
      padding: .9rem 1rem;
      margin-bottom: 1rem;
    }
    .privacy-panel strong { color: #0b4f8a; }
    .status-row {
      align-items: center;
      border-bottom: 1px solid #e6edf3;
      display: flex;
      font-size: .86rem;
      justify-content: space-between;
      padding: .45rem 0;
    }
    .status-label { color: #334e68; font-weight: 600; }
    .status-text { color: #52606d; font-size: .78rem; }
    .status-text--completed { color: var(--success); }
    .status-text--running { color: var(--brand); }
    .status-text--error { color: var(--danger); }
    .section-kicker {
      color: var(--brand);
      font-size: .75rem;
      font-weight: 750;
      letter-spacing: .09em;
      text-transform: uppercase;
    }
    div[data-testid="stMetric"] {
      background: white;
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: .8rem 1rem;
    }
    div[data-testid="stExpander"] {
      background: white;
      border-color: var(--line);
      border-radius: 10px;
    }
    div[data-testid="stFileUploader"] {
      background: white;
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: .4rem .7rem;
    }
    div[data-testid="stChatMessage"] {
      border: 1px solid #e1e8ef;
      border-radius: 12px;
      padding: .4rem .65rem;
    }
    .evidence-tag {
      background: #e8f3ff;
      border-radius: 999px;
      color: #07599f;
      display: inline-block;
      font-family: monospace;
      font-size: .72rem;
      margin: .1rem .2rem .1rem 0;
      padding: .18rem .45rem;
    }
    .mock-badge {
      background: #fff4ce;
      border: 1px solid #f0cf6a;
      border-radius: 999px;
      color: #714f00;
      display: inline-block;
      font-size: .75rem;
      font-weight: 700;
      padding: .18rem .55rem;
    }
    @media (max-width: 760px) {
      .block-container { padding-left: .8rem; padding-right: .8rem; }
      .demo-hero { border-radius: 12px; padding: 1.1rem; }
      .demo-hero h1 { font-size: 1.45rem; }
      div[data-testid="stHorizontalBlock"] { gap: .5rem; }
      div[data-testid="stDataFrame"] { max-width: calc(100vw - 2rem); }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def default_start_date(time_zone: str = "Asia/Shanghai") -> date:
    local_today = datetime.now(timezone.utc).astimezone(ZoneInfo(time_zone)).date()
    return local_today + timedelta(days=1)


def local_today(time_zone: str = "Asia/Shanghai") -> date:
    return datetime.now(timezone.utc).astimezone(ZoneInfo(time_zone)).date()


def initialize_state() -> None:
    buffer_start = local_today()
    defaults: dict[str, Any] = {
        "active_stage": "Data Intake",
        "analysis": None,
        "plan": None,
        "plan_history": [],
        "chat_history": [
            {
                "role": "assistant",
                "answer": {
                    "status": "answered",
                    "dataStatement": (
                        "Complete the analysis to review metrics, trends, quality, "
                        "supporting evidence, and proposed plan changes."
                    ),
                    "possibleMeaning": None,
                    "suggestedValidation": (
                        "Metric responses include the metric ID, reporting period, "
                        "and source module."
                    ),
                    "citations": [],
                    "suggestedPlanChange": None,
                },
            }
        ],
        "applied_chat_changes": [],
        "export_artifacts": None,
        "export_status": "idle",
        "buffer_preview": None,
        "buffer_preview_attempted": False,
        "buffer_export_result": None,
        "buffer_export_records": [],
        "buffer_export_status": "idle",
        "buffer_start_date": buffer_start,
        "buffer_end_date": buffer_start + timedelta(days=13),
        "buffer_timezone": "Asia/Shanghai",
        "buffer_channels": list(BUFFER_CHANNEL_LABELS),
        "buffer_selected_item_ids": [],
        "buffer_warnings_acknowledged": False,
        "buffer_editor_generation": 0,
        "last_error": None,
        "last_success": None,
        "mode": None,
        "operation_in_progress": False,
        "operation_name": None,
        "quality_acknowledged": False,
        "plan_generation_cancelled": False,
        "upload_generation": 0,
        "project_id": "linkedin-project",
        "business_goal": (
            "Build a compliant, measurable LinkedIn campaign for medical device "
            "marketing stakeholders"
        ),
        "business_goal_confirmed": False,
        "plan_timezone": "Asia/Shanghai",
        "plan_start_date": default_start_date(),
        "posts_per_week": 2,
        "team_size": 0,
        "content_resources": ["Copywriting", "Design"],
        "target_market": "North America",
        "focus_audience": (
            "Healthcare professionals, hospital decision-makers, and "
            "medical technology partners"
        ),
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def clear_buffer_selection_widgets() -> None:
    for key in list(st.session_state.keys()):
        if str(key).startswith("buffer-include-"):
            del st.session_state[key]


def reset_buffer_workspace(
    plan: dict[str, Any] | None = None,
    *,
    preserve_records: bool = True,
) -> None:
    time_zone = (
        plan.get("preferences", {}).get("timeZone", "Asia/Shanghai")
        if plan
        else st.session_state.get("plan_timezone", "Asia/Shanghai")
    )
    try:
        start = local_today(time_zone)
    except (KeyError, ValueError):
        time_zone = "Asia/Shanghai"
        start = local_today(time_zone)
    records = (
        list(st.session_state.get("buffer_export_records", []))
        if preserve_records
        else []
    )
    st.session_state["buffer_preview"] = None
    st.session_state["buffer_preview_attempted"] = False
    st.session_state["buffer_export_result"] = None
    st.session_state["buffer_export_records"] = records
    st.session_state["buffer_export_status"] = "idle"
    st.session_state["buffer_start_date"] = start
    st.session_state["buffer_end_date"] = start + timedelta(days=13)
    st.session_state["buffer_timezone"] = time_zone
    st.session_state["buffer_channels"] = list(BUFFER_CHANNEL_LABELS)
    st.session_state["buffer_selected_item_ids"] = (
        [item["itemId"] for item in plan.get("contentCalendar", [])]
        if plan
        else []
    )
    st.session_state["buffer_warnings_acknowledged"] = False
    clear_buffer_selection_widgets()


def invalidate_plan_outputs() -> None:
    st.session_state["export_artifacts"] = None
    st.session_state["export_status"] = "idle"
    st.session_state["buffer_preview"] = None
    st.session_state["buffer_preview_attempted"] = False
    st.session_state["buffer_export_result"] = None
    st.session_state["buffer_export_status"] = "idle"
    st.session_state["buffer_warnings_acknowledged"] = False
    clear_buffer_selection_widgets()


@st.cache_resource
def bridge_client() -> BridgeClient:
    return BridgeClient()


def reset_project_state(*, notice: str | None = None) -> None:
    upload_generation = int(st.session_state.get("upload_generation", 0)) + 1
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state["upload_generation"] = upload_generation
    if notice:
        st.session_state["_reset_notice"] = notice
    initialize_state()


def set_failure(failure: BridgeFailure, operation: str) -> None:
    st.session_state["last_error"] = {
        "operation": operation,
        "code": failure.code,
        "message": failure.message,
        "retryable": failure.retryable,
        "preserveProjectData": failure.preserve_project_data,
        "nextAction": failure.next_action,
    }
    st.session_state["last_success"] = None


def call_bridge(
    operation: str,
    payload: dict[str, Any],
    *,
    label: str,
    timeout_seconds: float = 45.0,
) -> dict[str, Any] | None:
    if st.session_state["operation_in_progress"]:
        set_failure(
            BridgeFailure(
                code="DUPLICATE_REQUEST",
                message="Another workflow step is already in progress.",
                retryable=True,
                preserve_project_data=True,
                next_action="Wait for the current step to finish, then try again.",
            ),
            operation,
        )
        return None

    st.session_state["operation_in_progress"] = True
    st.session_state["operation_name"] = operation
    st.session_state["last_error"] = None
    try:
        with st.spinner(label, show_time=True):
            result = bridge_client().call(
                operation,
                payload,
                timeout_seconds=timeout_seconds,
            )
        st.session_state["last_success"] = label
        return result
    except BridgeClientError as reason:
        set_failure(reason.failure, operation)
        return None
    finally:
        st.session_state["operation_in_progress"] = False
        st.session_state["operation_name"] = None


def assign_analysis(result: dict[str, Any], mode: str) -> None:
    st.session_state["analysis"] = result
    st.session_state["mode"] = mode
    st.session_state["plan"] = None
    st.session_state["plan_history"] = []
    st.session_state["export_artifacts"] = None
    st.session_state["export_status"] = "idle"
    reset_buffer_workspace(None, preserve_records=False)
    st.session_state["quality_acknowledged"] = False
    st.session_state["plan_generation_cancelled"] = False
    st.session_state["chat_history"] = [
        {
            "role": "assistant",
            "answer": {
                "status": "answered",
                "dataStatement": (
                    "Demonstration analysis is complete."
                    if mode == "mock"
                    else "Uploaded data has been processed for this session."
                ),
                "possibleMeaning": (
                    "This sample dataset is fictional and does not represent "
                    "actual company performance."
                    if mode == "mock"
                    else (
                        "Recommendations and plans use structured demonstration "
                        "rules. Review file recognition and data quality before "
                        "continuing."
                    )
                ),
                "suggestedValidation": (
                    "Use a suggested question to review the supporting evidence."
                ),
                "citations": [],
                "suggestedPlanChange": None,
            },
        }
    ]
    snapshot = result["snapshot"]
    st.session_state["_pending_active_stage"] = (
        "Performance Metrics" if snapshot["canEnterInsights"] else "Data Quality"
    )


def run_synthetic_demo() -> None:
    result = call_bridge(
        "analyze_synthetic",
        {"now": now_iso()},
        label="Loading the sample campaign",
    )
    if result is not None:
        st.session_state["_pending_project_id"] = "synthetic-linkedin-demo"
        assign_analysis(result, "mock")


def process_pending_actions() -> None:
    pending_project_id = st.session_state.pop("_pending_project_id", None)
    if pending_project_id:
        st.session_state["project_id"] = pending_project_id
    pending_active_stage = st.session_state.pop(
        "_pending_active_stage", None
    )
    if pending_active_stage:
        st.session_state["active_stage"] = pending_active_stage
    if st.session_state.pop("_pending_buffer_reset_ack", False):
        st.session_state["buffer_warnings_acknowledged"] = False

    if st.session_state.pop("_clear_requested", False):
        reset_project_state(
            notice=(
                "Project data has been removed from this session. The "
                "demonstration does not use persistent storage."
            )
        )
        st.rerun()

    if st.session_state.pop("_restart_demo_requested", False):
        reset_project_state()
        run_synthetic_demo()
        st.session_state["_reset_notice"] = "The demonstration project was restarted."
        st.rerun()


def analysis_data() -> dict[str, Any] | None:
    value = st.session_state.get("analysis")
    return value if isinstance(value, dict) else None


def snapshot_data() -> dict[str, Any] | None:
    analysis = analysis_data()
    snapshot = analysis.get("snapshot") if analysis else None
    return snapshot if isinstance(snapshot, dict) else None


def strategy_bundle() -> dict[str, Any] | None:
    analysis = analysis_data()
    bundle = analysis.get("strategyBundle") if analysis else None
    return bundle if isinstance(bundle, dict) else None


def warnings_are_acknowledged() -> bool:
    snapshot = snapshot_data()
    if not snapshot:
        return False
    quality = snapshot["quality"]
    return (
        not quality["requiresWarningAcknowledgement"]
        or st.session_state["quality_acknowledged"]
    )


def can_use_insights() -> bool:
    snapshot = snapshot_data()
    return bool(
        snapshot
        and snapshot["canEnterInsights"]
        and warnings_are_acknowledged()
    )


def render_agent_mode_notice() -> None:
    if st.session_state.get("mode") == "mock":
        st.info(
            "Demonstration mode uses fictional, structured sample data and "
            "predefined business rules."
        )
    elif st.session_state.get("mode") == "uploaded":
        st.info(
            "Uploaded metrics are processed for this session. Recommendations "
            "and plans use predefined demonstration rules."
        )


def metric_catalog(node: Any) -> dict[str, dict[str, Any]]:
    catalog: dict[str, dict[str, Any]] = {}

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            metric_id = value.get("metricId")
            if (
                isinstance(metric_id, str)
                and "formattedValue" in value
                and "reliability" in value
            ):
                catalog[metric_id] = value
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(node)
    return catalog


def period_text(period: dict[str, Any] | None) -> str:
    if not period:
        return "unavailable"
    return (
        f"{period['start']} to {period['end']} · "
        f"{period['granularity']} · {period['sampleSize']} records"
    )


def format_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def stage_status(stage: str) -> tuple[str, str]:
    analysis = analysis_data()
    snapshot = snapshot_data()
    plan = st.session_state.get("plan")
    if stage == "Data Intake":
        return ("completed", "Complete") if analysis else ("running", "Current")
    if not snapshot:
        return "pending", "Pending"
    if stage == "Data Quality":
        return (
            ("error", "Blocked")
            if snapshot["quality"]["hasBlockingIssues"]
            else ("completed", "Complete")
        )
    if stage == "Performance Metrics":
        return "completed", "Complete"
    if stage in {"Audience Insights", "Content Insights"}:
        if not snapshot["canEnterInsights"]:
            return "error", "Blocked"
        category = "audience" if stage == "Audience Insights" else "content"
        bundle = strategy_bundle() or {}
        matches = [
            item
            for item in bundle.get("insights", [])
            if item.get("category") == category
        ]
        if not matches:
            return "pending", "No evidence"
        if all(item.get("approvalStatus") != "draft" for item in matches):
            return "completed", "Reviewed"
        return "running", "Review required"
    if stage == "Campaign Strategy":
        bundle = strategy_bundle() or {}
        strategies = bundle.get("strategies", [])
        if not strategies:
            return (
                ("error", "Blocked")
                if not snapshot["canEnterInsights"]
                else ("pending", "Pending")
            )
        if all(item.get("approvalStatus") != "draft" for item in strategies):
            return "completed", "Reviewed"
        return "running", "Review required"
    if stage == "30-Day Campaign Plan":
        if plan:
            return (
                ("completed", "Approved")
                if plan.get("status") == "user_confirmed"
                else ("running", "Draft")
            )
        if st.session_state["plan_generation_cancelled"]:
            return "error", "Cancelled"
        return "pending", "Pending"
    if stage == "Buffer Handoff":
        if not plan:
            return "pending", "Awaiting plan"
        exported = sum(
            item.get("workflowStatus") == "exported_to_buffer"
            for item in plan.get("contentCalendar", [])
        )
        if exported:
            return "completed", f"{exported} handed off"
        approved = sum(
            item.get("status") == "confirmed"
            for item in plan.get("contentCalendar", [])
        )
        return (
            ("running", f"{approved} ready")
            if approved
            else ("pending", "Awaiting approval")
        )
    return "pending", "Pending"


def render_header() -> None:
    st.markdown(
        """
        <div class="demo-hero">
          <div class="demo-hero__eyebrow">Medical Device Marketing Operations</div>
          <h1>LinkedIn Campaign Workspace</h1>
          <p>Plan, review, and prepare evidence-informed LinkedIn campaigns for
          regulated medical device audiences.</p>
        </div>
        <div class="privacy-panel" role="note" aria-label="Data handling notice">
          <strong>Data handling:</strong>
          Uploaded files are processed within the current session and are not
          written to application storage. Do not upload patient data, protected
          health information, or non-public clinical data.
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.session_state.get("_reset_notice"):
        st.success(st.session_state.pop("_reset_notice"))


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("### Campaign Workspace")
        st.text_input(
            "Campaign ID",
            key="project_id",
            max_chars=100,
            help="Used in report titles and export names. Do not enter credentials.",
        )
        mode = st.session_state.get("mode")
        if mode == "mock":
            st.markdown(
                '<span class="mock-badge">SAMPLE DATA</span>',
                unsafe_allow_html=True,
            )
        elif mode == "uploaded":
            st.caption("Data mode: Uploaded dataset · Session-only processing")
            st.caption("Recommendation mode: Structured demonstration rules")
        else:
            st.caption("Status: Select a data intake path")

        st.divider()
        st.markdown("### Campaign Workflow")
        for stage in PIPELINE_STAGES:
            status, text = stage_status(stage)
            st.markdown(
                (
                    '<div class="status-row">'
                    f'<span class="status-label">{stage}</span>'
                    f'<span class="status-text status-text--{status}">{text}</span>'
                    "</div>"
                ),
                unsafe_allow_html=True,
            )

        st.divider()
        st.radio(
            "Workspace navigation",
            NAVIGATION,
            key="active_stage",
            help="Use the arrow keys to move between workflow pages.",
        )

        st.divider()
        if st.button(
            "Restart Sample Campaign",
            width="stretch",
            disabled=st.session_state["operation_in_progress"],
        ):
            st.session_state["_restart_demo_requested"] = True
            st.rerun()
        if st.button(
            "Clear Campaign Data",
            width="stretch",
            disabled=st.session_state["operation_in_progress"],
        ):
            st.session_state["_clear_requested"] = True
            st.rerun()
        st.caption(
            "Clearing removes analysis, plans, evidence history, Buffer handoff "
            "records, exports, and uploaded files from this session."
        )


def render_last_status() -> None:
    error = st.session_state.get("last_error")
    if error:
        retained = (
            "Processed data remains available; no upload is required."
            if error["preserveProjectData"]
            else "Current data was not retained."
        )
        st.error(
            f"{error['code']}: {error['message']} {retained}",
            icon=":material/error:",
        )
        st.caption(f"Next step: {error['nextAction']}")
    elif st.session_state.get("last_success"):
        st.success(
            st.session_state["last_success"],
            icon=":material/check_circle:",
        )


def render_parse_summaries() -> None:
    analysis = analysis_data()
    if not analysis:
        return
    st.markdown("### File Recognition Results")
    for summary in analysis["parseSummaries"]:
        slot = summary["slot"]
        detected = ", ".join(summary["detectedModules"]) or "Undetermined"
        title = (
            f"{MODULE_LABELS[slot]} · {summary['file']['name']} · "
            f"Recognized as {detected}"
        )
        with st.expander(title):
            cols = st.columns(4)
            cols[0].metric("Format", summary["file"]["format"].upper())
            cols[1].metric("Total Rows", summary["totalRows"])
            cols[2].metric("Valid Rows", summary["validRows"])
            cols[3].metric(
                "Status",
                "Ready" if summary["canProceed"] else "Review Required",
            )
            for sheet in summary["sheets"]:
                st.markdown(f"**Sheet: {sheet['sheetName']}**")
                st.caption(
                    f"Header row {sheet['headerRow'] or 'Not recognized'} · "
                    f"Detected module "
                    f"{sheet['detection']['detectedModule'] or 'Undetermined'} · "
                    f"Confidence {sheet['detection']['confidence']} · "
                    f"Date range {sheet['dateRange'] or 'Unavailable'}"
                )
                mappings = [
                    {
                        "Source Field": mapping["rawHeader"],
                        "Standard Field": mapping["standardField"] or "Unmapped",
                        "Status": mapping["status"],
                        "Confidence": mapping["confidence"],
                    }
                    for mapping in sheet["mappings"]
                ]
                if mappings:
                    st.dataframe(
                        mappings,
                        hide_index=True,
                        width="stretch",
                    )
                if sheet["missingCriticalFields"]:
                    st.warning(
                        "Missing required fields: "
                        + ", ".join(sheet["missingCriticalFields"])
                    )
                if sheet["standardizedPreview"]:
                    st.caption("Standardized preview (up to 5 rows)")
                    st.dataframe(
                        sheet["standardizedPreview"],
                        hide_index=True,
                        width="stretch",
                    )
                if sheet["issues"]:
                    st.caption(
                        "Quality notes: "
                        + "; ".join(
                            f"{item['code']}: {item['message']}"
                            for item in sheet["issues"][:8]
                        )
                    )


def render_ingestion() -> None:
    st.markdown('<span class="section-kicker">Data intake</span>', unsafe_allow_html=True)
    st.header("Select a Data Intake Path")
    st.write(
        "Use fictional sample data for a guided campaign workflow, or upload "
        "LinkedIn XLSX, XLS, or CSV exports up to 10 MB per file."
    )
    left, right = st.columns([1, 2], gap="large")
    with left:
        with st.container(border=True):
            st.subheader("Medical Device Sample Campaign")
            st.write(
                "A fictional campaign dataset with structured metrics, "
                "recommendations, and review-ready outputs."
            )
            if st.button(
                "Start with Sample Data",
                type="primary",
                width="stretch",
                disabled=st.session_state["operation_in_progress"],
            ):
                run_synthetic_demo()
                st.rerun()

    upload_generation = st.session_state["upload_generation"]
    uploaded_files: dict[str, Any] = {}
    with right:
        with st.container(border=True):
            st.subheader("Upload LinkedIn Exports")
            columns = st.columns(3)
            for column, module in zip(columns, MODULES):
                with column:
                    uploaded = st.file_uploader(
                        f"{MODULE_LABELS[module]} File",
                        type=("xlsx", "xls", "csv"),
                        key=f"upload-{module}-{upload_generation}",
                        help=(
                            "Drag and drop or browse for a file. The service "
                            "validates file type, signature, size, and encryption."
                        ),
                    )
                    if uploaded is not None:
                        uploaded_files[module] = uploaded
                        st.caption(
                            f"{uploaded.name} · {format_size(uploaded.size)}"
                        )
                    else:
                        st.caption(MODULE_IMPACTS[module])

            missing = [
                MODULE_LABELS[module]
                for module in MODULES
                if module not in uploaded_files
            ]
            if missing:
                st.warning(
                    "Missing "
                    + ", ".join(missing)
                    + ". Quality checks remain available, but campaign planning "
                    "requires all three modules."
                )
            analyze_clicked = st.button(
                "Process Data and Create Snapshot",
                width="stretch",
                disabled=(
                    not uploaded_files
                    or st.session_state["operation_in_progress"]
                ),
            )
            if analyze_clicked:
                payload_files: list[dict[str, Any]] = []
                try:
                    for module, uploaded in uploaded_files.items():
                        content = uploaded.getvalue()
                        try:
                            payload_files.append(
                                encode_upload(
                                    slot=module,
                                    name=uploaded.name,
                                    mime_type=uploaded.type or "",
                                    data=content,
                                )
                            )
                        finally:
                            content = b""
                    result = call_bridge(
                        "analyze_uploads",
                        {"now": now_iso(), "files": payload_files},
                        label="Validating files and calculating campaign metrics",
                        timeout_seconds=60,
                    )
                except BridgeClientError as reason:
                    set_failure(reason.failure, "analyze_uploads")
                    result = None
                finally:
                    payload_files.clear()
                if result is not None:
                    assign_analysis(result, "uploaded")
                    st.rerun()

    render_parse_summaries()


def render_quality() -> None:
    snapshot = snapshot_data()
    st.markdown('<span class="section-kicker">Data quality</span>', unsafe_allow_html=True)
    st.header("Data Quality Review")
    if not snapshot:
        st.info("Start with sample data or upload files in Data Intake.")
        return

    quality = snapshot["quality"]
    cols = st.columns(4)
    cols[0].metric("Blocking Issues", quality["blockingIssueCount"])
    cols[1].metric("Warnings", quality["warningCount"])
    cols[2].metric(
        "Overlapping Period",
        "Available" if quality["overlapPeriod"] else "Unavailable",
    )
    cols[3].metric(
        "Planning Readiness",
        "Ready" if snapshot["canEnterInsights"] else "Blocked",
    )
    if quality["hasBlockingIssues"]:
        st.error(
            "Blocking issues must be resolved before insights or campaign "
            "planning can continue. Unavailable metrics are never fabricated."
        )
    elif quality["requiresWarningAcknowledgement"]:
        st.warning(
            "Review and acknowledge the non-blocking warnings before continuing."
        )
        st.checkbox(
            "I have reviewed the data quality warnings and understand their impact",
            key="quality_acknowledged",
        )
    else:
        st.success("No blocking issues were found. Business coverage may still vary.")

    issues = quality["issues"]
    if issues:
        st.dataframe(
            [
                {
                    "severity": issue["severity"],
                    "code": issue["code"],
                    "module": issue["module"],
                    "field": issue["field"] or "-",
                    "message": issue["message"],
                    "blocks": issue["blocksAnalysis"],
                    "suggestedAction": issue["suggestedAction"],
                }
                for issue in issues
            ],
            hide_index=True,
            width="stretch",
        )
    else:
        st.info("No quality rules were triggered.")

    st.markdown("### Module Coverage")
    module_rows = []
    for module in MODULES:
        summary = quality["moduleSummaries"][module]
        module_rows.append(
            {
                "Module": MODULE_LABELS[module],
                "Present": "Yes" if summary["present"] else "No",
                "Records": summary["totalRecords"],
                "Duplicates": summary["duplicateRecords"],
                "Reporting Period": period_text(summary["period"]),
                "Error": summary["issueCount"]["error"],
                "Warning": summary["issueCount"]["warning"],
            }
        )
    st.dataframe(module_rows, hide_index=True, width="stretch")


def render_metric_detail(metric: dict[str, Any]) -> None:
    with st.expander(f"Calculation details · {metric['metricId']}"):
        st.write(f"**Formula:** {metric['formula']}")
        st.write(f"**Reporting period:** {period_text(metric['period'])}")
        st.write(f"**Reliability:** {metric['reliability']}")
        st.write(
            "**Reliability notes:** "
            + ("; ".join(metric["reliabilityReasons"]) or "No additional notes")
        )
        st.write(
            "**Source modules:** "
            + (", ".join(metric["sourceModules"]) or "Unavailable")
        )
        if metric.get("caveat"):
            st.warning(metric["caveat"])
        references = metric.get("sourceReferences", [])
        if references:
            st.dataframe(
                [
                    {
                        "Module": ref["module"],
                        "File": ref["fileName"],
                        "Sheet": ref["sheetName"],
                        "Rows": f"{ref['rowStart']}-{ref['rowEnd']}",
                        "Fields": ", ".join(ref["fields"]),
                    }
                    for ref in references[:20]
                ],
                hide_index=True,
                width="stretch",
            )


def render_series(
    title: str,
    series: dict[str, Any],
    *,
    source_text: str,
) -> None:
    st.markdown(f"#### {title}")
    points = [
        {"period": point["period"], "value": point["value"]}
        for point in series["points"]
        if point["value"] is not None
    ]
    if len(points) >= 2:
        st.line_chart(points, x="period", y="value", height=260)
        st.caption(
            f"Summary: {series['label']} · Unit: {series['unit']} · "
            f"Period: {period_text(series['period'])} · Source: {source_text}."
        )
    else:
        st.info(
            "There are not enough comparable time points to display a trend."
        )


def render_metrics() -> None:
    snapshot = snapshot_data()
    st.markdown('<span class="section-kicker">Deterministic metrics</span>', unsafe_allow_html=True)
    st.header("Performance Metrics")
    if not snapshot:
        st.info("No analysis snapshot is available.")
        return
    catalog = metric_catalog(snapshot["metrics"])
    key_metrics = (
        "followers.netGrowth",
        "followers.growthRate",
        "visitors.pageViewsTotal",
        "visitors.uniqueVisitorsTotal",
        "content.engagementRate",
        "content.ctr",
        "content.publishedCount",
        "cross.visitorToFollowerProxy",
    )
    visible = [catalog[item] for item in key_metrics if item in catalog]
    for start in range(0, len(visible), 4):
        columns = st.columns(4)
        for column, metric in zip(columns, visible[start : start + 4]):
            with column:
                st.metric(metric["label"], metric["formattedValue"])
                st.caption(
                    f"{metric['reliability']} · "
                    f"{period_text(metric['period'])}"
                )
                render_metric_detail(metric)

    follower_series = snapshot["metrics"]["followers"]["newFollowersTrend"]
    visitor_series = snapshot["metrics"]["visitors"]["pageViewsTrend"]
    left, right = st.columns(2)
    with left:
        render_series(
            "New Follower Trend",
            follower_series,
            source_text="Followers",
        )
    with right:
        render_series(
            "Company Page View Trend",
            visitor_series,
            source_text="Visitors",
        )

    st.markdown("### Performance by Content Format")
    groups = snapshot["metrics"]["content"]["byContentType"]
    if groups:
        rows = []
        for group in groups:
            row = {
                "Content Format": group["label"],
                "Sample Size": group["sampleSize"],
                "Reliability": group["reliability"],
            }
            for metric in group["metrics"]:
                row[metric["label"]] = metric["formattedValue"]
            rows.append(row)
        st.dataframe(rows, hide_index=True, width="stretch")
        st.caption(
            "All grouped values come from the analysis snapshot. Small samples "
            "are marked as directional."
        )
    else:
        st.info("Content format or post-level metrics are unavailable.")


def update_insight_status(insight_id: str, status: str) -> None:
    analysis = copy.deepcopy(analysis_data())
    if not analysis:
        return
    bundle = analysis["strategyBundle"]
    for insight in bundle["insights"]:
        if insight["insightId"] == insight_id:
            insight["approvalStatus"] = status
    if status != "approved":
        for strategy in bundle["strategies"]:
            if insight_id in strategy["insightIds"]:
                strategy["approvalStatus"] = "draft"
    st.session_state["analysis"] = analysis
    st.session_state["plan"] = None
    st.session_state["plan_history"] = []
    invalidate_plan_outputs()
    reset_buffer_workspace(None)


def approval_controls(
    *,
    item_id: str,
    status: str,
    on_change: Any,
    approve_disabled: bool = False,
) -> None:
    columns = st.columns(3)
    if columns[0].button(
        "Approve",
        key=f"approve-{item_id}",
        disabled=approve_disabled or status == "approved",
        width="stretch",
    ):
        on_change("approved")
        st.rerun()
    if columns[1].button(
        "Reject",
        key=f"reject-{item_id}",
        disabled=status == "rejected",
        width="stretch",
    ):
        on_change("rejected")
        st.rerun()
    if columns[2].button(
        "Return to Draft",
        key=f"draft-{item_id}",
        disabled=status == "draft",
        width="stretch",
    ):
        on_change("draft")
        st.rerun()


def render_insights(category: str, title: str) -> None:
    st.markdown('<span class="section-kicker">Evidence insights</span>', unsafe_allow_html=True)
    st.header(title)
    snapshot = snapshot_data()
    bundle = strategy_bundle()
    if not snapshot or not bundle:
        st.info("Complete the data analysis first.")
        return
    if not snapshot["canEnterInsights"]:
        st.error("Blocking data quality issues prevent insight review.")
        return
    if not warnings_are_acknowledged():
        st.warning("Acknowledge the warnings in Data Quality before continuing.")
        return

    insights = [
        item
        for item in bundle["insights"]
        if item["category"] == category
    ]
    if not insights:
        missing = (
            "Followers or Visitors profile and trend fields"
            if category == "audience"
            else "post-level Content performance fields"
        )
        st.info(f"Additional data is required: {missing}.")
        return

    render_agent_mode_notice()
    for insight in insights:
        with st.container(border=True):
            st.subheader(insight["title"])
            st.caption(
                f"{insight['approvalStatus']} · confidence "
                f"{insight['confidence']} · {insight['insightId']}"
            )
            st.write(f"**Finding:** {insight['statement']}")
            st.write(f"**Business implication:** {insight['possibleMeaning']}")
            st.write(f"**Recommended validation:** {insight['suggestedValidation']}")
            if insight["limitations"]:
                st.warning("; ".join(insight["limitations"]))
            with st.expander("Review Supporting Evidence"):
                for evidence in insight["evidence"]:
                    st.markdown(
                        f"`{evidence['metricId']}` · "
                        f"{evidence['label']} · {evidence['formattedValue']}"
                    )
                    st.caption(
                        f"{period_text(evidence['period'])} · "
                        f"Sources {', '.join(evidence['sourceModules'])} · "
                        f"Reliability {evidence['reliability']}"
                    )
            approval_controls(
                item_id=insight["insightId"],
                status=insight["approvalStatus"],
                on_change=lambda status, insight_id=insight[
                    "insightId"
                ]: update_insight_status(insight_id, status),
            )


def update_strategy_status(strategy_id: str, status: str) -> None:
    analysis = copy.deepcopy(analysis_data())
    if not analysis:
        return
    for strategy in analysis["strategyBundle"]["strategies"]:
        if strategy["strategyId"] == strategy_id:
            strategy["approvalStatus"] = status
    st.session_state["analysis"] = analysis
    st.session_state["plan"] = None
    st.session_state["plan_history"] = []
    invalidate_plan_outputs()
    reset_buffer_workspace(None)


def render_strategies() -> None:
    st.markdown('<span class="section-kicker">Approved strategy gate</span>', unsafe_allow_html=True)
    st.header("Campaign Strategy Review")
    snapshot = snapshot_data()
    bundle = strategy_bundle()
    if not snapshot or not bundle:
        st.info("Complete the analysis first.")
        return
    if not can_use_insights():
        st.warning("Resolve blocking issues or acknowledge warnings first.")
        return
    approved_insight_ids = {
        item["insightId"]
        for item in bundle["insights"]
        if item["approvalStatus"] == "approved"
    }
    if not bundle["strategies"]:
        st.info("No strategy recommendations have valid metric references.")
        return

    render_agent_mode_notice()
    for strategy in bundle["strategies"]:
        references_approved = all(
            item in approved_insight_ids for item in strategy["insightIds"]
        )
        with st.container(border=True):
            st.subheader(strategy["title"])
            st.caption(
                f"{strategy['approvalStatus']} · {strategy['strategyId']}"
            )
            st.write(f"**Objective:** {strategy['objective']}")
            st.write(f"**Rationale:** {strategy['rationale']}")
            for action in strategy["actions"]:
                st.write(f"- {action}")
            st.caption(
                "Source insights: "
                + ", ".join(strategy["insightIds"])
                + " · Metrics: "
                + ", ".join(strategy["metricIds"])
            )
            if not references_approved:
                st.warning("Approve all referenced insights before this strategy.")
            approval_controls(
                item_id=strategy["strategyId"],
                status=strategy["approvalStatus"],
                approve_disabled=not references_approved,
                on_change=lambda status, strategy_id=strategy[
                    "strategyId"
                ]: update_strategy_status(strategy_id, status),
            )


def approved_counts() -> tuple[int, int]:
    bundle = strategy_bundle() or {}
    insights = sum(
        item.get("approvalStatus") == "approved"
        for item in bundle.get("insights", [])
    )
    strategies = sum(
        item.get("approvalStatus") == "approved"
        for item in bundle.get("strategies", [])
    )
    return insights, strategies


def current_preferences() -> dict[str, Any]:
    team_size = int(st.session_state["team_size"])
    return {
        "startDate": st.session_state["plan_start_date"].isoformat(),
        "timeZone": st.session_state["plan_timezone"],
        "postsPerWeek": int(st.session_state["posts_per_week"]),
        "teamSize": team_size if team_size > 0 else None,
        "contentResources": list(st.session_state["content_resources"]),
        "targetMarket": st.session_state["target_market"].strip() or None,
        "focusAudience": st.session_state["focus_audience"].strip(),
    }


def push_plan_history() -> None:
    plan = st.session_state.get("plan")
    if plan:
        history = list(st.session_state["plan_history"])
        history.append(copy.deepcopy(plan))
        st.session_state["plan_history"] = history[-10:]


def create_or_revise_plan() -> None:
    analysis = analysis_data()
    snapshot = snapshot_data()
    bundle = strategy_bundle()
    if not analysis or not snapshot or not bundle:
        return
    plan = st.session_state.get("plan")
    if plan:
        result = call_bridge(
            "revise_schedule",
            {
                "now": now_iso(),
                "snapshot": snapshot,
                "strategyBundle": bundle,
                "plan": plan,
                "preferences": current_preferences(),
            },
            label="Updating the campaign schedule",
        )
        if result is not None:
            push_plan_history()
            st.session_state["plan"] = result
    else:
        result = call_bridge(
            "create_plan",
            {
                "now": now_iso(),
                "snapshot": snapshot,
                "strategyBundle": bundle,
                "businessGoal": {
                    "goalId": f"goal-{snapshot['snapshotId']}",
                    "statement": st.session_state["business_goal"].strip(),
                    "confirmed": st.session_state["business_goal_confirmed"],
                    "confirmedAt": now_iso(),
                },
                "preferences": current_preferences(),
            },
            label="Validating approvals and preparing the four-week campaign",
        )
        if result is not None:
            st.session_state["plan"] = result
            st.session_state["plan_history"] = []
            st.session_state["plan_generation_cancelled"] = False
    if result is not None:
        invalidate_plan_outputs()
        reset_buffer_workspace(result)


def render_plan_editor(plan: dict[str, Any]) -> None:
    st.markdown("### Campaign Content Editor")
    choices = {
        f"{item['date']} · {item['topic']}": item
        for item in plan["contentCalendar"]
    }
    selected_label = st.selectbox(
        "Select a calendar item",
        list(choices),
        key=f"calendar-item-{plan['planId']}",
    )
    item = choices[selected_label]
    item_key = item["itemId"]
    topic = st.text_input(
        "Topic",
        value=item["topic"],
        key=f"edit-topic-{plan['updatedAt']}-{item_key}",
    )
    audience = st.text_input(
        "Target Audience",
        value=item["targetAudience"],
        key=f"edit-audience-{plan['updatedAt']}-{item_key}",
    )
    cta = st.text_input(
        "CTA",
        value=item["callToAction"],
        key=f"edit-cta-{plan['updatedAt']}-{item_key}",
    )
    statuses = ("ai_draft", "confirmed", "rejected")
    status = st.selectbox(
        "Review Status",
        statuses,
        index=statuses.index(item["status"]),
        key=f"edit-status-{plan['updatedAt']}-{item_key}",
    )
    if st.button(
        "Save Item Changes",
        disabled=st.session_state["operation_in_progress"],
    ):
        result = call_bridge(
            "revise_calendar_item",
            {
                "now": now_iso(),
                "snapshot": snapshot_data(),
                "strategyBundle": strategy_bundle(),
                "plan": plan,
                "itemId": item_key,
                "patch": {
                    "topic": topic,
                    "targetAudience": audience,
                    "callToAction": cta,
                    "status": status,
                },
            },
            label="Saving campaign item changes",
        )
        if result is not None:
            push_plan_history()
            st.session_state["plan"] = result
            invalidate_plan_outputs()
            st.rerun()


def render_plan_report(plan: dict[str, Any]) -> None:
    st.divider()
    st.markdown('<span class="section-kicker">Management report</span>', unsafe_allow_html=True)
    st.header("30-Day Campaign Execution Report")
    metadata = (
        f"Created {plan['generatedAt']} · Updated {plan['updatedAt']} · "
        f"Analysis {period_text(plan['analysisPeriod'])} · "
        f"Prompt {plan['promptVersion']} · "
        f"Modules {', '.join(plan['sourceModules'])}"
    )
    st.caption(metadata)
    st.subheader("Risks and Data Limitations")
    for risk in plan["risksAndLimitations"]:
        st.warning(risk)
    st.subheader("Executive Summary")
    st.write(plan["executiveSummary"])
    with st.expander("Planning Assumptions", expanded=True):
        for assumption in plan["assumptions"]:
            st.write(f"- {assumption}")

    st.subheader("Approved Insights and Recommendations")
    bundle = strategy_bundle() or {}
    for insight in bundle.get("insights", []):
        if insight["approvalStatus"] == "approved":
            st.write(
                f"- **{insight['category']} · {insight['title']}:** "
                f"{insight['statement']} "
                f"(Evidence: "
                + ", ".join(
                    reference["metricId"] for reference in insight["evidence"]
                )
                + ")"
            )
    for strategy in bundle.get("strategies", []):
        if strategy["approvalStatus"] == "approved":
            st.write(
                f"- **Recommendation · {strategy['title']}:** "
                f"{strategy['objective']} ({strategy['strategyId']})"
            )

    view = st.radio(
        "Plan view",
        ("Weekly Plan", "Content Calendar"),
        horizontal=True,
        key=f"plan-view-{plan['planId']}",
    )
    if view == "Weekly Plan":
        for week in plan["fourWeekPlan"]:
            with st.expander(
                f"Week {week['weekNumber']} · "
                f"{week['dateRange']['start']} to {week['dateRange']['end']}",
                expanded=week["weekNumber"] == 1,
            ):
                st.write(f"**Objective:** {week['objective']}")
                st.write(f"**Target audience:** {week['targetAudience']}")
                st.write(f"**CTA:** {week['callToAction']}")
                st.write(
                    "**KPIs:** " + ", ".join(week["kpiMetricIds"])
                )
                for task in week["tasks"]:
                    st.write(
                        f"- {task['dueDate']} · {task['title']} · "
                        f"{task['ownerPlaceholder']} · {task['status']}"
                    )
    else:
        st.dataframe(
            [
                {
                    "Date": item["date"],
                    "Time / Time Zone": (
                        f"{item.get('scheduledTime', 'Not set')} / "
                        f"{item.get('timeZone', plan['preferences']['timeZone'])}"
                    ),
                    "Channel": BUFFER_CHANNEL_LABELS.get(
                        item.get("channel"), item.get("channel", "Not set")
                    ),
                    "Topic": item["topic"],
                    "Format": item["contentFormat"],
                    "Audience": item["targetAudience"],
                    "CTA": item["callToAction"],
                    "Strategy": item["strategyId"],
                    "KPIs": ", ".join(item["measurementMetricIds"]),
                    "Experiment": "Yes" if item["isExperiment"] else "No",
                    "Approval": BUFFER_APPROVAL_LABELS.get(
                        item["status"], item["status"]
                    ),
                    "Buffer Status": BUFFER_WORKFLOW_LABELS.get(
                        item.get("workflowStatus", "planning"),
                        item.get("workflowStatus", "planning"),
                    ),
                }
                for item in plan["contentCalendar"]
            ],
            hide_index=True,
            width="stretch",
        )

    experiments = [
        item for item in plan["contentCalendar"] if item["isExperiment"]
    ]
    if experiments:
        st.subheader("Campaign Experiments")
        for item in experiments:
            experiment = item["experiment"]
            with st.expander(f"{item['date']} · {item['topic']}"):
                st.write(f"**Hypothesis:** {experiment['hypothesis']}")
                st.write(
                    f"**Success criteria:** {experiment['successCriteria']}"
                )
                st.write(f"**Review date:** {experiment['reviewDate']}")
                st.write(
                    "**KPIs:** " + ", ".join(experiment["metricIds"])
                )

    st.subheader("KPI Review Plan")
    st.dataframe(
        [
            {
                "Review Date": review["reviewDate"],
                "KPIs": ", ".join(review["metricIds"]),
                "Action": review["action"],
                "Comparison Rule": review["comparisonRule"],
            }
            for review in plan["kpiReviewPlan"]
        ],
        hide_index=True,
        width="stretch",
    )
    with st.expander("Questions for the Next Reporting Cycle"):
        for question in plan["nextImportQuestions"]:
            st.write(f"- {question}")

    render_plan_editor(plan)
    controls = st.columns(3)
    if controls[0].button(
        "Undo Last Change",
        disabled=not st.session_state["plan_history"],
        width="stretch",
    ):
        history = list(st.session_state["plan_history"])
        st.session_state["plan"] = history.pop()
        st.session_state["plan_history"] = history
        invalidate_plan_outputs()
        st.rerun()

    if st.button(
        "Continue to Buffer Handoff",
        type="primary",
        width="stretch",
        disabled=not any(
            item.get("status") == "confirmed"
            for item in plan.get("contentCalendar", [])
        ),
        help=(
            "Approve at least one item. Handoff files do not indicate publication."
        ),
    ):
        st.session_state["active_stage"] = "Buffer Handoff"
        st.rerun()
    if controls[1].button(
        "Approve Current Plan",
        disabled=plan["status"] == "user_confirmed",
        width="stretch",
    ):
        result = call_bridge(
            "confirm_plan",
            {
                "now": now_iso(),
                "snapshot": snapshot_data(),
                "strategyBundle": strategy_bundle(),
                "plan": plan,
            },
            label="Approving the campaign plan",
        )
        if result is not None:
            push_plan_history()
            st.session_state["plan"] = result
            if not st.session_state["buffer_selected_item_ids"]:
                st.session_state["buffer_selected_item_ids"] = [
                    item["itemId"] for item in result["contentCalendar"]
                ]
            invalidate_plan_outputs()
            st.rerun()
    if controls[2].button(
        "Cancel Planning",
        width="stretch",
    ):
        push_plan_history()
        st.session_state["plan"] = None
        st.session_state["plan_generation_cancelled"] = True
        invalidate_plan_outputs()
        reset_buffer_workspace(None)
        st.session_state["last_success"] = (
            "Campaign planning was cancelled. Analysis and approvals were retained."
        )
        st.rerun()


def render_plan() -> None:
    st.markdown('<span class="section-kicker">Campaign planning</span>', unsafe_allow_html=True)
    st.header("Build a 30-Day Campaign from Approved Strategy")
    snapshot = snapshot_data()
    if not snapshot:
        st.info("Complete the analysis first.")
        return
    if not can_use_insights():
        st.warning("The data quality gate must pass before planning.")
        return
    insight_count, strategy_count = approved_counts()
    render_agent_mode_notice()
    st.caption(
        f"Approved insights {insight_count} · Approved strategies {strategy_count} · "
        f"Snapshot {snapshot['snapshotId']}"
    )
    if insight_count == 0 or strategy_count == 0:
        st.warning("Approve at least one insight and one related strategy.")

    plan = st.session_state.get("plan")
    if st.session_state["plan_generation_cancelled"] and not plan:
        st.warning(
            "Planning was cancelled. Data and approvals remain available."
        )
        if st.button("Resume Campaign Planning"):
            st.session_state["plan_generation_cancelled"] = False
            st.rerun()

    with st.form("plan-settings"):
        st.text_input(
            "Campaign Objective",
            key="business_goal",
            max_chars=500,
            disabled=bool(plan),
        )
        st.checkbox(
            "I confirm this campaign objective",
            key="business_goal_confirmed",
            disabled=bool(plan),
        )
        cols = st.columns(3)
        cols[0].selectbox("Campaign Time Zone", TIME_ZONES, key="plan_timezone")
        cols[1].date_input(
            "Campaign Start Date",
            key="plan_start_date",
            min_value=date.today(),
        )
        cols[2].slider(
            "Posts per Week",
            min_value=1,
            max_value=7,
            key="posts_per_week",
        )
        cols = st.columns(2)
        cols[0].number_input(
            "Campaign Team Size (0 if not provided)",
            min_value=0,
            max_value=100,
            step=1,
            key="team_size",
        )
        cols[1].text_input(
            "Target Market (Optional)",
            key="target_market",
            max_chars=120,
        )
        st.multiselect(
            "Available Content Resources",
            (
                "Copywriting",
                "Design",
                "Video",
                "Clinical Evidence",
                "Product Specialist",
            ),
            key="content_resources",
        )
        st.text_input(
            "Priority Audience",
            key="focus_audience",
            max_chars=200,
        )
        submitted = st.form_submit_button(
            "Apply Schedule Changes" if plan else "Create Campaign Draft",
            type="primary",
            width="stretch",
            disabled=(
                st.session_state["operation_in_progress"]
                or insight_count == 0
                or strategy_count == 0
                or st.session_state["plan_generation_cancelled"]
            ),
        )
    if submitted:
        create_or_revise_plan()
        st.rerun()
    if plan:
        render_plan_report(plan)


def buffer_handoff_payload() -> dict[str, Any]:
    start = st.session_state["buffer_start_date"]
    end = st.session_state["buffer_end_date"]
    return {
        "dateRange": {
            "start": start.isoformat() if isinstance(start, date) else str(start),
            "end": end.isoformat() if isinstance(end, date) else str(end),
        },
        "timeZone": st.session_state["buffer_timezone"],
        "channels": list(st.session_state["buffer_channels"]),
        "selectedItemIds": list(
            st.session_state["buffer_selected_item_ids"]
        ),
        "warningsAcknowledged": bool(
            st.session_state["buffer_warnings_acknowledged"]
        ),
        "previousExports": list(
            st.session_state["buffer_export_records"]
        ),
    }


def refresh_buffer_preview(
    label: str = "Validating Buffer handoff content",
) -> bool:
    plan = st.session_state.get("plan")
    snapshot = snapshot_data()
    bundle = strategy_bundle()
    if not plan or not snapshot or not bundle:
        return False
    st.session_state["buffer_preview_attempted"] = True
    result = call_bridge(
        "preview_buffer_handoff",
        {
            "now": now_iso(),
            "snapshot": snapshot,
            "strategyBundle": bundle,
            "plan": plan,
            "handoff": buffer_handoff_payload(),
        },
        label=label,
        timeout_seconds=25,
    )
    if result is None:
        st.session_state["buffer_export_status"] = "failed"
        return False
    st.session_state["plan"] = result["updatedPlan"]
    st.session_state["buffer_preview"] = result
    if not st.session_state.get("buffer_export_result"):
        st.session_state["buffer_export_status"] = "previewed"
    st.session_state["buffer_warnings_acknowledged"] = (
        not result["summary"]["requiresWarningAcknowledgement"]
    )
    return True


def render_buffer_filters(plan: dict[str, Any]) -> None:
    st.subheader("Handoff Schedule and Channels")
    st.caption(
        "The default handoff window covers 14 days. Items outside the window "
        "remain in the campaign plan."
    )
    with st.form("buffer-handoff-filters"):
        columns = st.columns(3)
        columns[0].date_input(
            "Start Date",
            key="buffer_start_date",
        )
        columns[1].date_input(
            "End Date",
            key="buffer_end_date",
        )
        columns[2].selectbox(
            "Publishing Time Zone",
            TIME_ZONES,
            key="buffer_timezone",
            help=(
                "Buffer CSV files do not include a time zone column. Confirm "
                "that each destination channel uses this time zone."
            ),
        )
        st.multiselect(
            "Destination Channels",
            tuple(BUFFER_CHANNEL_LABELS),
            key="buffer_channels",
            format_func=lambda value: BUFFER_CHANNEL_LABELS[value],
            help="A separate handoff file is created for each channel.",
        )
        apply_filters = st.form_submit_button(
            "Apply Schedule and Revalidate",
            type="primary",
            disabled=st.session_state["operation_in_progress"],
        )
    if apply_filters:
        if st.session_state["buffer_end_date"] < st.session_state[
            "buffer_start_date"
        ]:
            st.session_state["buffer_preview_attempted"] = True
            st.session_state["buffer_preview"] = None
            st.error("The end date cannot be earlier than the start date.")
        else:
            refresh_buffer_preview()
            st.rerun()

    if st.button(
        "Restore Next 14 Days",
        disabled=st.session_state["operation_in_progress"],
    ):
        try:
            start = local_today(st.session_state["buffer_timezone"])
        except (KeyError, ValueError):
            start = local_today(plan["preferences"]["timeZone"])
            st.session_state["buffer_timezone"] = plan["preferences"][
                "timeZone"
            ]
        st.session_state["buffer_start_date"] = start
        st.session_state["buffer_end_date"] = start + timedelta(days=13)
        st.session_state["buffer_selected_item_ids"] = [
            item["itemId"] for item in plan["contentCalendar"]
        ]
        st.session_state["buffer_warnings_acknowledged"] = False
        refresh_buffer_preview("Restoring the 14-day handoff window")
        st.rerun()


def buffer_review_rows(preview: dict[str, Any]) -> list[dict[str, Any]]:
    selected_ids = set(st.session_state["buffer_selected_item_ids"])
    rows: list[dict[str, Any]] = []
    for review in preview["reviews"]:
        item = review["contentItem"]
        error_count = sum(
            issue["severity"] == "error" for issue in review["issues"]
        )
        warning_count = sum(
            issue["severity"] == "warning" for issue in review["issues"]
        )
        if item["mediaUrls"]:
            media_status = f"{len(item['mediaUrls'])} links provided"
        elif item.get("mediaRequirement"):
            media_status = "Media required"
        else:
            media_status = "No media required"
        if item["itemId"] in selected_ids and review["canExport"]:
            inclusion = "Yes"
        elif item["itemId"] in selected_ids:
            inclusion = "Selected but excluded"
        else:
            inclusion = "No"
        rows.append(
            {
                "Date": item["date"],
                "Time / Time Zone": (
                    f"{item['scheduledTime']} / {item['timeZone']}"
                ),
                "Channel": BUFFER_CHANNEL_LABELS[item["channel"]],
                "Topic": item["topic"],
                "Copy Preview": (
                    item["postText"][:90]
                    + ("…" if len(item["postText"]) > 90 else "")
                ),
                "Media": media_status,
                "Approval": BUFFER_APPROVAL_LABELS[item["status"]],
                "Buffer Readiness": BUFFER_WORKFLOW_LABELS[
                    item["workflowStatus"]
                ],
                "Validation": f"Errors {error_count} / Warnings {warning_count}",
                "Included": inclusion,
            }
        )
    return rows


def render_buffer_selection(preview: dict[str, Any]) -> None:
    st.subheader("Content Review")
    st.dataframe(
        buffer_review_rows(preview),
        hide_index=True,
        width="stretch",
    )
    st.caption(
        "Review campaign items, approval status, media readiness, and validation."
    )
    selected_ids: list[str] = []
    with st.form("buffer-item-selection"):
        for review in preview["reviews"]:
            item = review["contentItem"]
            blocking = any(
                issue["blocksExport"] for issue in review["issues"]
            )
            selectable = (
                review["inDateRange"]
                and review["channelIncluded"]
                and not blocking
            )
            label = (
                f"{item['date']} {item['scheduledTime']} "
                f"({item['timeZone']}) · "
                f"{BUFFER_CHANNEL_LABELS[item['channel']]} · {item['topic']}"
            )
            checked = st.checkbox(
                label,
                value=(
                    item["itemId"]
                    in st.session_state["buffer_selected_item_ids"]
                    and selectable
                ),
                disabled=not selectable,
                key=f"buffer-include-{item['itemId']}",
                help=(
                    "Items with blocking errors, missing approval, excluded "
                    "channels, or out-of-range dates cannot be selected."
                    if not selectable
                    else "Include this item in the channel handoff file."
                ),
            )
            if checked and selectable:
                selected_ids.append(item["itemId"])
            visible_issues = [
                issue
                for issue in review["issues"]
                if issue["severity"] != "info"
            ]
            if visible_issues:
                with st.expander(
                    f"Validation · {item['topic']}",
                    expanded=blocking,
                ):
                    for issue in visible_issues:
                        message = (
                            f"{issue['code']}: {issue['message']} "
                            f"Next step: {issue['suggestedAction']}"
                        )
                        if issue["severity"] == "error":
                            st.error(message)
                        else:
                            st.warning(message)
        update_selection = st.form_submit_button(
            "Update Selection and Summary",
            disabled=st.session_state["operation_in_progress"],
        )
    if update_selection:
        st.session_state["buffer_selected_item_ids"] = selected_ids
        st.session_state["buffer_warnings_acknowledged"] = False
        refresh_buffer_preview("Updating the Buffer handoff selection")
        st.rerun()


def render_buffer_item_editor(plan: dict[str, Any]) -> None:
    st.subheader("Pre-Handoff Content Editor")
    generation = st.session_state["buffer_editor_generation"]
    choices = {
        (
            f"{item['date']} {item['scheduledTime']} · "
            f"{BUFFER_CHANNEL_LABELS[item['channel']]} · {item['topic']}"
        ): item
        for item in plan["contentCalendar"]
    }
    selected_label = st.selectbox(
        "Select content to review",
        list(choices),
        key=f"buffer-editor-item-{generation}",
    )
    item = choices[selected_label]
    item_id = item["itemId"]
    item_key = f"{generation}-{item_id}-{item['lastEditedAt']}"
    format_options = list(
        dict.fromkeys(
            [
                item["contentFormat"],
                "Text Post",
                "Image Post",
                "Document Carousel",
                "Short Video",
            ]
        )
    )
    try:
        scheduled_time = datetime.strptime(
            item["scheduledTime"], "%H:%M"
        ).time()
    except ValueError:
        scheduled_time = datetime.strptime("09:00", "%H:%M").time()

    with st.form(f"buffer-item-editor-{item_key}"):
        post_text = st.text_area(
            "Post Copy",
            value=item["postText"],
            height=180,
            max_chars=10_000,
            help="The export does not truncate or rewrite copy.",
        )
        columns = st.columns(3)
        channel = columns[0].selectbox(
            "Channel",
            tuple(BUFFER_CHANNEL_LABELS),
            index=tuple(BUFFER_CHANNEL_LABELS).index(item["channel"]),
            format_func=lambda value: BUFFER_CHANNEL_LABELS[value],
        )
        content_format = columns[1].selectbox(
            "Content Format",
            format_options,
            index=0,
        )
        approval_status = columns[2].selectbox(
            "Approval Status",
            tuple(BUFFER_APPROVAL_LABELS),
            index=tuple(BUFFER_APPROVAL_LABELS).index(item["status"]),
            format_func=lambda value: BUFFER_APPROVAL_LABELS[value],
        )
        columns = st.columns(3)
        scheduled_date = columns[0].date_input(
            "Publication Date",
            value=date.fromisoformat(item["date"]),
        )
        scheduled_clock = columns[1].time_input(
            "Publication Time",
            value=scheduled_time,
            step=timedelta(minutes=15),
        )
        time_zone = columns[2].selectbox(
            "Time Zone",
            TIME_ZONES,
            index=TIME_ZONES.index(item["timeZone"]),
        )
        media_urls = st.text_area(
            "Direct Media Links (One per Line)",
            value="\n".join(item["mediaUrls"]),
            help=(
                "Leave blank when a direct public URL is unavailable and add "
                "the asset manually during Buffer review."
            ),
        )
        link_url = st.text_input(
            "Link URL (Optional)",
            value=item.get("linkUrl") or "",
        )
        campaign_tag = st.text_input(
            "Buffer Tag (Optional)",
            value=item.get("campaignTag") or "",
            help="The tag must already exist in Buffer and is case-sensitive.",
        )
        buttons = st.columns(2)
        save = buttons[0].form_submit_button(
            "Save and Revalidate",
            type="primary",
            disabled=st.session_state["operation_in_progress"],
            width="stretch",
        )
        cancel = buttons[1].form_submit_button(
            "Cancel Editing",
            width="stretch",
        )

    if cancel:
        st.session_state["buffer_editor_generation"] += 1
        st.rerun()
    if save:
        result = call_bridge(
            "revise_calendar_item",
            {
                "now": now_iso(),
                "snapshot": snapshot_data(),
                "strategyBundle": strategy_bundle(),
                "plan": plan,
                "itemId": item_id,
                "patch": {
                    "postText": post_text,
                    "channel": channel,
                    "contentFormat": content_format,
                    "date": scheduled_date.isoformat(),
                    "scheduledTime": scheduled_clock.strftime("%H:%M"),
                    "timeZone": time_zone,
                    "mediaUrls": [
                        value.strip()
                        for value in media_urls.splitlines()
                        if value.strip()
                    ],
                    "linkUrl": link_url.strip() or None,
                    "campaignTag": campaign_tag.strip() or None,
                    "status": approval_status,
                },
            },
            label="Saving and validating the content calendar",
            timeout_seconds=25,
        )
        if result is not None:
            push_plan_history()
            st.session_state["plan"] = result
            st.session_state["buffer_editor_generation"] += 1
            invalidate_plan_outputs()
            st.rerun()


def render_buffer_summary(preview: dict[str, Any]) -> None:
    st.subheader("Handoff Summary")
    summary = preview["summary"]
    columns = st.columns(5)
    columns[0].metric("Selected", summary["selectedCount"])
    columns[1].metric("Ready", summary["exportableCount"])
    columns[2].metric("Excluded", summary["excludedCount"])
    columns[3].metric("Blocking Errors", summary["blockingErrorCount"])
    columns[4].metric("Warnings", summary["warningCount"])
    channel_counts = summary["channelCounts"]
    st.caption(
        f"Range {preview['dateRange']['start']} to {preview['dateRange']['end']} · "
        f"Time zone {preview['timeZone']} · "
        + " · ".join(
            f"{BUFFER_CHANNEL_LABELS[channel]} "
            f"{channel_counts.get(channel, 0)} items"
            for channel in preview["channels"]
        )
    )
    for issue in preview["globalIssues"]:
        message = f"{issue['code']}: {issue['message']} {issue['suggestedAction']}"
        if issue["severity"] == "error":
            st.error(message)
        elif issue["severity"] == "warning":
            st.warning(message)
        else:
            st.info(message)
    st.caption(
        "Current Buffer guidance lists a per-channel queue and upload limit of "
        f"{preview['guidance']['freePlan']['queueCapacityPerChannel']} items. "
        f"Guidance reviewed {preview['guidance']['reviewedAt']}; verify current "
        "Buffer plan limits before import."
    )


def export_buffer_handoff(plan: dict[str, Any]) -> None:
    st.session_state["buffer_export_status"] = "processing"
    result = call_bridge(
        "export_buffer_handoff",
        {
            "now": now_iso(),
            "projectId": st.session_state["project_id"],
            "snapshot": snapshot_data(),
            "strategyBundle": strategy_bundle(),
            "plan": plan,
            "handoff": buffer_handoff_payload(),
        },
        label="Creating channel-level Buffer handoff files",
        timeout_seconds=25,
    )
    if result is None:
        st.session_state["buffer_export_status"] = "failed"
        return
    push_plan_history()
    st.session_state["plan"] = result["updatedPlan"]
    records = list(st.session_state["buffer_export_records"])
    if not any(
        record["exportId"] == result["exportRecord"]["exportId"]
        for record in records
    ):
        records.append(result["exportRecord"])
    st.session_state["buffer_export_records"] = records[-20:]
    st.session_state["buffer_export_result"] = result
    st.session_state["buffer_export_status"] = "ready"
    st.session_state["buffer_preview"] = None
    st.session_state["buffer_preview_attempted"] = False
    st.session_state["_pending_buffer_reset_ack"] = True


def render_buffer_result() -> None:
    result = st.session_state.get("buffer_export_result")
    status = st.session_state["buffer_export_status"]
    if status == "processing":
        st.info("Handoff files are being prepared.")
    elif status == "failed":
        st.error("Buffer handoff failed. The plan and reviews were retained.")
    if not result:
        return

    record = result["exportRecord"]
    st.success(
        f"Created {len(result['artifacts'])} channel files for "
        f"{len(record['exportedItemIds'])} items; "
        f"{len(record['skippedItemIds'])} items were skipped."
    )
    st.warning(
        "Handoff files are ready for manual review. This does not indicate "
        "that content has been imported, scheduled, or published."
    )
    columns = st.columns(max(1, len(result["artifacts"])))
    for column, artifact in zip(columns, result["artifacts"]):
        clicked = column.download_button(
            f"Download {BUFFER_CHANNEL_LABELS[artifact['channel']]} CSV",
            data=artifact["content"],
            file_name=artifact["fileName"],
            mime=artifact["mimeType"],
            key=f"download-buffer-{record['exportId']}-{artifact['channel']}",
            width="stretch",
        )
        if clicked:
            st.session_state["buffer_export_status"] = "downloaded"
            st.session_state["last_success"] = (
                f"{artifact['fileName']} was downloaded. No content was published."
            )

    st.subheader("Buffer Import Checklist")
    steps = (
        "Sign in to the authorized Buffer account.",
        "Select the social channel that matches the file name.",
        "Download the latest Bulk Upload template and verify its columns.",
        "Upload the generated channel CSV.",
        "Review dates, times, time zone, copy, links, and media.",
        "Complete final approval in Buffer Review Content.",
        "Confirm the handoff record after queuing; handoff is not publication.",
    )
    for index, step in enumerate(steps, start=1):
        st.write(f"{index}. {step}")
    st.markdown(
        (
            f'<a href="{BUFFER_BULK_UPLOAD_URL}" target="_blank" '
            'rel="noopener noreferrer">Open Buffer bulk upload guidance</a>'
        ),
        unsafe_allow_html=True,
    )
    st.info(
        "This demonstration does not access Buffer accounts or store credentials. "
        "The designated campaign owner remains responsible for final scheduling "
        "and publication."
    )


def render_buffer_handoff() -> None:
    st.markdown(
        '<span class="section-kicker">Human-reviewed handoff</span>',
        unsafe_allow_html=True,
    )
    st.header("Buffer Handoff")
    st.write("Prepare approved campaign content for review and scheduling in Buffer.")
    st.warning(
        "The workflow creates CSV files for manual import and does not connect "
        "directly to Buffer. Validate the latest template before use."
    )
    plan = st.session_state.get("plan")
    if not plan:
        st.info("Create a 30-day campaign plan first.")
        return
    approved_count = sum(
        item.get("status") == "confirmed"
        for item in plan.get("contentCalendar", [])
    )
    if approved_count == 0:
        st.warning(
            "No content is approved. Review items below or return to the campaign plan."
        )

    render_buffer_filters(plan)
    preview = st.session_state.get("buffer_preview")
    if preview is None and not st.session_state["buffer_preview_attempted"]:
        if not st.session_state["buffer_selected_item_ids"]:
            st.session_state["buffer_selected_item_ids"] = [
                item["itemId"] for item in plan["contentCalendar"]
            ]
        if refresh_buffer_preview():
            st.rerun()
    preview = st.session_state.get("buffer_preview")
    if preview is None:
        st.info("No handoff preview is available. Update the range and revalidate.")
        if st.button(
            "Revalidate Buffer Handoff",
            disabled=st.session_state["operation_in_progress"],
        ):
            refresh_buffer_preview()
            st.rerun()
        render_buffer_item_editor(plan)
        render_buffer_result()
        return

    render_buffer_summary(preview)
    render_buffer_selection(preview)
    render_buffer_item_editor(st.session_state["plan"])
    controls = st.columns(2)
    if controls[0].button(
        "Undo Last Content Change",
        disabled=not st.session_state["plan_history"],
        width="stretch",
    ):
        history = list(st.session_state["plan_history"])
        st.session_state["plan"] = history.pop()
        st.session_state["plan_history"] = history
        invalidate_plan_outputs()
        st.rerun()
    if controls[1].button(
        "Revalidate",
        disabled=st.session_state["operation_in_progress"],
        width="stretch",
    ):
        refresh_buffer_preview()
        st.rerun()

    requires_warning = preview["summary"][
        "requiresWarningAcknowledgement"
    ]
    if requires_warning:
        st.checkbox(
            "I reviewed the warnings and will complete final checks in Buffer",
            key="buffer_warnings_acknowledged",
        )
    export_disabled = (
        st.session_state["operation_in_progress"]
        or preview["summary"]["exportableCount"] == 0
        or (
            requires_warning
            and not st.session_state["buffer_warnings_acknowledged"]
        )
    )
    if preview["summary"]["exportableCount"] == 0:
        st.caption("No items are ready. Resolve blocking errors and revalidate.")
    elif requires_warning and not st.session_state[
        "buffer_warnings_acknowledged"
    ]:
        st.caption("Handoff is unavailable until warnings are acknowledged.")
    if st.button(
        "Create Buffer Handoff Files",
        type="primary",
        disabled=export_disabled,
        width="stretch",
        help=(
            "Includes approved in-range content without blocking errors. "
            "File creation does not indicate publication."
        ),
    ):
        export_buffer_handoff(st.session_state["plan"])
        st.rerun()

    render_buffer_result()
    records = st.session_state["buffer_export_records"]
    if records:
        with st.expander("Session Handoff Records"):
            st.dataframe(
                [
                    {
                        "Export ID": record["exportId"],
                        "Created": record["generatedAt"],
                        "Range": (
                            f"{record['dateRange']['start']} to "
                            f"{record['dateRange']['end']}"
                        ),
                        "Time Zone": record["timeZone"],
                        "Channels": ", ".join(
                            BUFFER_CHANNEL_LABELS[channel]
                            for channel in record["channels"]
                        ),
                        "Handed Off": len(record["exportedItemIds"]),
                        "Skipped": len(record["skippedItemIds"]),
                        "Status": record["status"],
                    }
                    for record in records
                ],
                hide_index=True,
                width="stretch",
            )


def render_answer(answer: dict[str, Any], message_index: int) -> None:
    if answer["status"] == "refused":
        st.warning(answer["dataStatement"])
    elif answer["status"] == "unavailable":
        st.info(answer["dataStatement"])
    else:
        st.write(answer["dataStatement"])
    if answer.get("possibleMeaning"):
        st.write(f"**Business implication:** {answer['possibleMeaning']}")
    if answer.get("suggestedValidation"):
        st.write(f"**Recommended validation:** {answer['suggestedValidation']}")
    citations = answer.get("citations", [])
    if citations:
        with st.expander("Review Supporting Evidence"):
            for citation in citations:
                st.write(
                    f"- `{citation['citationId']}` · {citation['label']}"
                )
                metric = citation.get("metric")
                if metric:
                    st.caption(
                        f"{metric['metricId']} · "
                        f"{metric['formattedValue']} · "
                        f"{period_text(metric['period'])} · "
                        f"Sources {', '.join(metric['sourceModules'])}"
                    )
    change = answer.get("suggestedPlanChange")
    plan = st.session_state.get("plan")
    change_key = f"chat-change-{message_index}"
    if change and plan and change_key not in st.session_state["applied_chat_changes"]:
        if st.button("Review and Apply Plan Change", key=change_key):
            preferences = copy.deepcopy(plan["preferences"])
            if change["type"] == "posts_per_week":
                preferences["postsPerWeek"] = change["postsPerWeek"]
                st.session_state["posts_per_week"] = change["postsPerWeek"]
            elif change["type"] == "focus_audience":
                preferences["focusAudience"] = change["focusAudience"]
                st.session_state["focus_audience"] = change["focusAudience"]
            result = call_bridge(
                "revise_schedule",
                {
                    "now": now_iso(),
                    "snapshot": snapshot_data(),
                    "strategyBundle": strategy_bundle(),
                    "plan": plan,
                    "preferences": preferences,
                },
                label="Applying the approved plan change",
            )
            if result is not None:
                push_plan_history()
                st.session_state["plan"] = result
                applied = list(st.session_state["applied_chat_changes"])
                applied.append(change_key)
                st.session_state["applied_chat_changes"] = applied
                invalidate_plan_outputs()
                reset_buffer_workspace(result)
                st.rerun()


def submit_question(question: str) -> None:
    snapshot = snapshot_data()
    bundle = strategy_bundle()
    if not snapshot or not bundle:
        return
    st.session_state["chat_history"].append(
        {"role": "user", "content": question}
    )
    answer = call_bridge(
        "answer_question",
        {
            "now": now_iso(),
            "snapshot": snapshot,
            "strategyBundle": bundle,
            "plan": st.session_state.get("plan"),
            "question": question,
        },
        label="Retrieving current campaign evidence",
        timeout_seconds=20,
    )
    if answer is not None:
        st.session_state["chat_history"].append(
            {"role": "assistant", "answer": answer}
        )


def render_chat() -> None:
    st.markdown('<span class="section-kicker">Campaign evidence</span>', unsafe_allow_html=True)
    st.header("Campaign Evidence Review")
    if not snapshot_data():
        st.info("Complete the data analysis first.")
        return
    render_agent_mode_notice()
    quick_columns = st.columns(3)
    pending_question: str | None = None
    for index, question in enumerate(QUICK_QUESTIONS):
        if quick_columns[index % 3].button(
            question,
            key=f"quick-{index}",
            width="stretch",
            disabled=st.session_state["operation_in_progress"],
        ):
            pending_question = question

    for index, message in enumerate(st.session_state["chat_history"]):
        with st.chat_message(message["role"]):
            if message["role"] == "user":
                st.write(message["content"])
            else:
                render_answer(message["answer"], index)
    typed_question = st.chat_input(
        "Review a metric, trend, quality issue, or plan recommendation",
        disabled=st.session_state["operation_in_progress"],
    )
    question = typed_question or pending_question
    if question:
        submit_question(question)
        st.rerun()


def render_exports() -> None:
    st.markdown('<span class="section-kicker">Safe exports</span>', unsafe_allow_html=True)
    st.header("Reports and Exports")
    snapshot = snapshot_data()
    bundle = strategy_bundle()
    if not snapshot or not bundle:
        st.info("Complete the analysis first.")
        return
    plan = st.session_state.get("plan")
    st.write(
        "Exports include the analysis snapshot, approved evidence references, "
        "and campaign plan. Source files and raw cells are excluded."
    )
    if not plan:
        st.warning(
            "No campaign plan is available. Analysis reports can be exported, "
            "but the content calendar remains unavailable."
        )
    if st.button(
        "Prepare Campaign Reports",
        type="primary",
        disabled=st.session_state["operation_in_progress"],
    ):
        st.session_state["export_status"] = "processing"
        artifacts = call_bridge(
            "export_project",
            {
                "now": now_iso(),
                "projectId": st.session_state["project_id"],
                "snapshot": snapshot,
                "strategyBundle": bundle,
                "plan": plan,
            },
            label="Preparing campaign report files",
            timeout_seconds=25,
        )
        if artifacts is None:
            st.session_state["export_status"] = "failed"
        else:
            st.session_state["export_artifacts"] = artifacts
            st.session_state["export_status"] = "ready"
        st.rerun()

    status = st.session_state["export_status"]
    if status == "processing":
        st.info("Reports are being prepared.")
    elif status == "failed":
        st.error("Report preparation failed. The current analysis was retained.")
    elif status == "ready":
        st.success("Campaign reports are ready to download.")

    artifacts = st.session_state.get("export_artifacts")
    if not artifacts:
        return
    columns = st.columns(3)
    definitions = (
        ("markdown", "Download Campaign Report"),
        ("calendarCsv", "Download 30-Day Content Calendar"),
        ("structuredJson", "Download Structured Analysis"),
    )
    for column, (key, label) in zip(columns, definitions):
        artifact = artifacts[key]
        disabled = key == "calendarCsv" and not artifact["content"]
        clicked = column.download_button(
            label,
            data=artifact["content"],
            file_name=artifact["fileName"],
            mime=artifact["mimeType"],
            disabled=disabled,
            width="stretch",
            key=f"download-{key}-{artifact['fileName']}",
        )
        if clicked:
            st.session_state["export_status"] = "downloaded"
            st.session_state["last_success"] = (
                f"{artifact['fileName']} was downloaded."
            )


def render_current_stage() -> None:
    stage = st.session_state["active_stage"]
    if stage == "Data Intake":
        render_ingestion()
    elif stage == "Data Quality":
        render_quality()
    elif stage == "Performance Metrics":
        render_metrics()
    elif stage == "Audience Insights":
        render_insights("audience", "Audience Insights")
    elif stage == "Content Insights":
        render_insights("content", "Content Insights")
    elif stage == "Campaign Strategy":
        render_strategies()
    elif stage == "30-Day Campaign Plan":
        render_plan()
    elif stage == "Buffer Handoff":
        render_buffer_handoff()
    elif stage == "Campaign Evidence":
        render_chat()
    elif stage == "Reports & Exports":
        render_exports()


initialize_state()
process_pending_actions()
render_header()
render_sidebar()
render_last_status()
render_current_stage()

st.divider()
st.caption(
    "Demonstration scope: LinkedIn company-page aggregate analytics only. "
    "The workflow does not identify individual visitors or infer purchase intent. "
    "Correlation does not establish causation."
)
