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


APP_TITLE = "LinkedIn Marketing AI Agent"
MODULES = ("followers", "visitors", "content")
MODULE_LABELS = {
    "followers": "Followers",
    "visitors": "Visitors",
    "content": "Content",
}
MODULE_IMPACTS = {
    "followers": "缺少 Followers 将阻断关注者增长、受众画像和跨模块代理比率。",
    "visitors": "缺少 Visitors 将阻断主页访问趋势、访客画像和跨模块代理比率。",
    "content": "缺少 Content 将阻断内容表现、内容实验和 30 天内容日历。",
}
NAVIGATION = (
    "数据接入",
    "数据质量",
    "指标计算",
    "受众洞察",
    "内容洞察",
    "策略建议",
    "30 天计划",
    "交付 Buffer",
    "证据问答",
    "报告导出",
)
PIPELINE_STAGES = (
    "数据接入",
    "数据质量",
    "指标计算",
    "受众洞察",
    "内容洞察",
    "策略建议",
    "30 天计划",
    "交付 Buffer",
)
EXECUTIVE_WORKFLOW = (
    "历史数据",
    "AI 洞察报告",
    "营销策略",
    "人工批准",
    "30 天内容计划",
    "人工批准",
    "LinkedIn 草稿",
    "Buffer 队列",
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
    "最近关注者增长怎么样？",
    "访客趋势怎么样？",
    "哪类内容表现最好？",
    "下个月应该发布什么？",
    "当前数据质量有什么限制？",
)
BUFFER_CHANNEL_LABELS = {
    "linkedin_page": "LinkedIn Page",
    "linkedin_profile": "LinkedIn Profile",
}
BUFFER_APPROVAL_LABELS = {
    "ai_draft": "AI 初稿 / 待审核",
    "confirmed": "用户已批准",
    "rejected": "用户已拒绝",
}
BUFFER_WORKFLOW_LABELS = {
    "planning": "计划中",
    "ready_for_buffer": "可交付 Buffer",
    "exported_to_buffer": "已生成 Buffer 交接文件",
    "published": "用户已确认发布",
    "failed": "交接失败",
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
        "active_stage": "数据接入",
        "analysis": None,
        "plan": None,
        "plan_history": [],
        "chat_history": [
            {
                "role": "assistant",
                "answer": {
                    "status": "answered",
                    "dataStatement": (
                        "完成数据分析后，可询问指标、趋势、质量、洞察证据或计划修改。"
                    ),
                    "possibleMeaning": None,
                    "suggestedValidation": (
                        "数字回答会包含 metricId、时间范围和来源模块。"
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
        "business_goal": "建立可复盘的 LinkedIn 内容运营节奏",
        "business_goal_confirmed": False,
        "plan_timezone": "Asia/Shanghai",
        "plan_start_date": default_start_date(),
        "posts_per_week": 2,
        "team_size": 0,
        "content_resources": ["文案", "设计"],
        "target_market": "APAC",
        "focus_audience": "目标行业决策者",
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
                message="已有阶段正在处理，未重复提交。",
                retryable=True,
                preserve_project_data=True,
                next_action="请等待当前阶段结束后再试。",
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
                    "示例分析已完成。"
                    if mode == "mock"
                    else "上传数据已完成本地解析与确定性计算。"
                ),
                "possibleMeaning": (
                    "这是 Synthetic Mock 数据，不代表真实公司表现。"
                    if mode == "mock"
                    else (
                        "后续洞察、计划和聊天仍由确定性 Mock Agent 生成；"
                        "当前未接入真实模型。请先检查识别结果和数据质量。"
                    )
                ),
                "suggestedValidation": (
                    "可从快捷问题开始，并展开每个回答的 evidence。"
                ),
                "citations": [],
                "suggestedPlanChange": None,
            },
        }
    ]
    snapshot = result["snapshot"]
    st.session_state["_pending_active_stage"] = (
        "指标计算" if snapshot["canEnterInsights"] else "数据质量"
    )


def run_synthetic_demo() -> None:
    result = call_bridge(
        "analyze_synthetic",
        {"now": now_iso()},
        label="正在载入稳定 Synthetic 项目",
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
                "当前项目数据已从 Streamlit 会话移除；本 Demo 没有数据库或"
                "持久化上传目录，短生命周期 Bridge 已结束。"
            )
        )
        st.rerun()

    if st.session_state.pop("_restart_demo_requested", False):
        reset_project_state()
        run_synthetic_demo()
        st.session_state["_reset_notice"] = "Synthetic Demo 已从头重新载入。"
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
        st.warning("当前为 Synthetic 示例数据和规则式 Mock Agent，不会调用外部 AI。")
    elif st.session_state.get("mode") == "uploaded":
        st.warning(
            "当前仅数据解析与指标计算使用上传数据；洞察、策略、计划和聊天仍由"
            "确定性 Mock Agent 生成。尚未接入真实 LLM，也不会读取或要求 API Key。"
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
        f"{period['start']} 至 {period['end']} · "
        f"{period['granularity']} · 样本 {period['sampleSize']}"
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
    if stage == "数据接入":
        return ("completed", "完成") if analysis else ("running", "当前")
    if not snapshot:
        return "pending", "待处理"
    if stage == "数据质量":
        return (
            ("error", "阻断")
            if snapshot["quality"]["hasBlockingIssues"]
            else ("completed", "完成")
        )
    if stage == "指标计算":
        return "completed", "完成"
    if stage in {"受众洞察", "内容洞察"}:
        if not snapshot["canEnterInsights"]:
            return "error", "已阻断"
        category = "audience" if stage == "受众洞察" else "content"
        bundle = strategy_bundle() or {}
        matches = [
            item
            for item in bundle.get("insights", [])
            if item.get("category") == category
        ]
        if not matches:
            return "pending", "无可用证据"
        if all(item.get("approvalStatus") != "draft" for item in matches):
            return "completed", "已审阅"
        return "running", "待审批"
    if stage == "策略建议":
        bundle = strategy_bundle() or {}
        strategies = bundle.get("strategies", [])
        if not strategies:
            return (
                ("error", "已阻断")
                if not snapshot["canEnterInsights"]
                else ("pending", "待处理")
            )
        if all(item.get("approvalStatus") != "draft" for item in strategies):
            return "completed", "已审阅"
        return "running", "待审批"
    if stage == "30 天计划":
        if plan:
            return (
                ("completed", "用户已确认")
                if plan.get("status") == "user_confirmed"
                else ("running", "Mock 初稿")
            )
        if st.session_state["plan_generation_cancelled"]:
            return "error", "已取消"
        return "pending", "待生成"
    if stage == "交付 Buffer":
        if not plan:
            return "pending", "等待计划"
        exported = sum(
            item.get("workflowStatus") == "exported_to_buffer"
            for item in plan.get("contentCalendar", [])
        )
        if exported:
            return "completed", f"已交接 {exported} 项"
        approved = sum(
            item.get("status") == "confirmed"
            for item in plan.get("contentCalendar", [])
        )
        return (
            ("running", f"可审核 {approved} 项")
            if approved
            else ("pending", "等待内容批准")
        )
    return "pending", "待处理"


def render_header() -> None:
    st.markdown(
        """
        <div class="demo-hero">
          <div class="demo-hero__eyebrow">LinkedIn growth advisory workspace</div>
          <h1>LinkedIn Marketing AI Agent</h1>
          <p>从数据审阅到执行交接的增长咨询工作台：所有数字由本地程序计算，建议均可回溯至证据并由团队审批。</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    analysis = analysis_data()
    snapshot = snapshot_data()
    plan = st.session_state.get("plan")
    if not analysis:
        data_status, decision_status = "等待数据", "尚未开始"
        next_step = "选择示例或上传"
    elif not snapshot or snapshot["quality"]["hasBlockingIssues"]:
        data_status, decision_status = "需要处理", "数据质量待解决"
        next_step = "审阅数据质量"
    elif can_use_insights():
        data_status, decision_status = "已验证", "可进入决策"
        next_step = "审阅洞察与策略"
    else:
        data_status, decision_status = "已载入", "等待风险确认"
        next_step = "确认质量提示"
    delivery_status = (
        "计划已确认"
        if plan and plan.get("status") == "user_confirmed"
        else "计划待生成"
    )
    context = st.columns(4)
    context[0].metric("当前工作阶段", st.session_state["active_stage"])
    context[1].metric("数据状态", data_status)
    context[2].metric("决策就绪度", decision_status)
    context[3].metric("下一项交付", delivery_status)
    st.caption(
        "演示路径："
        + " → ".join(EXECUTIVE_WORKFLOW)
        + f"。建议下一步：{next_step}。"
    )
    st.caption("AI 加速分析与规划；所有关键判断、内容与交付均由团队确认。")
    if st.session_state.get("_reset_notice"):
        st.success(st.session_state.pop("_reset_notice"))


def render_sidebar() -> None:
    with st.sidebar:
        st.subheader("项目控制")
        st.caption("定义本次增长咨询项目的工作范围。")
        st.text_input(
            "项目标识",
            key="project_id",
            max_chars=100,
            help="仅用于报告标题和导出文件名，请勿填写密钥。",
        )
        mode = st.session_state.get("mode")
        if mode == "mock":
            st.markdown(
                '<span class="mock-badge">SYNTHETIC 示例数据</span>',
                unsafe_allow_html=True,
            )
        elif mode == "uploaded":
            st.caption("数据模式：用户上传 · 仅当前内存会话")
            st.caption("Agent 模式：确定性 Mock · 未接入真实 LLM")
        else:
            st.caption("状态：等待选择演示路径")

        st.divider()
        st.subheader("决策路径")
        st.caption("按顺序完成数据、判断、计划与交付。")
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
        st.subheader("工作区")
        st.radio(
            "选择工作区",
            NAVIGATION,
            key="active_stage",
            help="可使用方向键切换页面。",
        )

        st.divider()
        st.subheader("会话管理")
        if st.button(
            "重新开始 Synthetic Demo",
            width="stretch",
            disabled=st.session_state["operation_in_progress"],
        ):
            st.session_state["_restart_demo_requested"] = True
            st.rerun()
        if st.button(
            "清除当前项目数据",
            width="stretch",
            disabled=st.session_state["operation_in_progress"],
        ):
            st.session_state["_clear_requested"] = True
            st.rerun()
        st.caption(
            "清除会移除当前会话中的分析、计划、聊天、Buffer 交接记录、"
            "导出缓存和上传控件。"
            "刷新可能重置内存会话。"
        )


def render_last_status() -> None:
    error = st.session_state.get("last_error")
    if error:
        retained = (
            "当前已解析数据仍保留，无需重新上传。"
            if error["preserveProjectData"]
            else "当前数据未保留。"
        )
        st.error(
            f"{error['code']}：{error['message']} {retained}",
            icon=":material/error:",
        )
        st.caption(f"下一步：{error['nextAction']}")
    elif st.session_state.get("last_success"):
        st.success(
            st.session_state["last_success"],
            icon=":material/check_circle:",
        )


def render_next_action(label: str, stage: str, *, disabled: bool = False) -> None:
    if st.button(
        label,
        type="primary",
        width="stretch",
        disabled=disabled,
        key=f"next-{stage}",
    ):
        st.session_state["active_stage"] = stage
        st.rerun()


def render_parse_summaries() -> None:
    analysis = analysis_data()
    if not analysis:
        return
    with st.expander("文件识别结果与数据证据"):
        for summary in analysis["parseSummaries"]:
            slot = summary["slot"]
            detected = "、".join(summary["detectedModules"]) or "无法确定"
            title = (
                f"{MODULE_LABELS[slot]} · {summary['file']['name']} · "
                f"识别为 {detected}"
            )
            with st.expander(title):
                cols = st.columns(4)
                cols[0].metric("格式", summary["file"]["format"].upper())
                cols[1].metric("总行数", summary["totalRows"])
                cols[2].metric("有效行", summary["validRows"])
                cols[3].metric(
                    "可继续",
                    "是" if summary["canProceed"] else "需处理",
                )
                for sheet in summary["sheets"]:
                    st.markdown(f"**Sheet：{sheet['sheetName']}**")
                    mappings = [
                        {
                            "原字段": mapping["rawHeader"],
                            "标准字段": mapping["standardField"] or "unmapped",
                            "状态": mapping["status"],
                            "置信度": mapping["confidence"],
                        }
                        for mapping in sheet["mappings"]
                    ]
                    if mappings:
                        st.dataframe(mappings, hide_index=True, width="stretch")
                    if sheet["missingCriticalFields"]:
                        st.warning("缺失关键字段：" + "、".join(sheet["missingCriticalFields"]))


def render_ingestion() -> None:
    st.header("1 · 历史数据")
    st.write("从已验证的历史表现开始，让 AI 将分散数据转化为管理层可用的决策依据。")
    left, right = st.columns([1, 2], gap="large")
    with left:
        with st.container(border=True):
            st.subheader("Synthetic Mock Demo")
            st.write("三个模块、固定数值、固定回答，不依赖 AI API Key。")
            if st.button(
                "使用示例数据开始",
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
            st.subheader("上传 LinkedIn 导出")
            columns = st.columns(3)
            for column, module in zip(columns, MODULES):
                with column:
                    uploaded = st.file_uploader(
                        f"{MODULE_LABELS[module]} 文件",
                        type=("xlsx", "xls", "csv"),
                        key=f"upload-{module}-{upload_generation}",
                        help=(
                            "支持拖拽或文件选择。浏览器校验后，Bridge 仍会校验 "
                            "MIME、签名、大小和加密状态。"
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
                    "缺少 "
                    + "、".join(missing)
                    + "。仍可执行质量检查，但缺失模块会阻止 AI 洞察和计划。"
                )
            analyze_clicked = st.button(
                "解析并计算 Analysis Snapshot",
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
                        label="正在校验、解析并计算确定性指标",
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
    if analysis_data():
        render_next_action("查看数据健康度", "数据质量")


def render_quality() -> None:
    snapshot = snapshot_data()
    st.header("数据健康度")
    if not snapshot:
        st.info("请先在“数据接入”中载入 Synthetic 项目或上传文件。")
        return

    quality = snapshot["quality"]
    cols = st.columns(4)
    cols[0].metric("阻断问题", quality["blockingIssueCount"])
    cols[1].metric("Warning", quality["warningCount"])
    cols[2].metric(
        "时间重叠",
        "可用" if quality["overlapPeriod"] else "unavailable",
    )
    cols[3].metric(
        "洞察入口",
        "可进入" if snapshot["canEnterInsights"] else "已阻断",
    )
    if quality["hasBlockingIssues"]:
        st.error(
            "存在阻断问题。系统不会生成 AI 洞察或 30 天计划；已计算的"
            " unavailable 指标不会被填充假数据。"
        )
    elif quality["requiresWarningAcknowledgement"]:
        st.warning(
            "存在非阻断 Warning。阅读后确认，才可进入洞察审批。"
        )
        st.checkbox(
            "我已阅读数据质量 Warning，并理解其对精确决策的限制",
            key="quality_acknowledged",
        )
    else:
        st.success("当前没有阻断问题；这不代表数据可回答所有业务问题。")

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
        st.info("没有质量规则命中。")

    with st.expander("查看模块覆盖与质量细节"):
        module_rows = []
        for module in MODULES:
            summary = quality["moduleSummaries"][module]
            module_rows.append(
                {
                    "模块": MODULE_LABELS[module],
                    "是否存在": "是" if summary["present"] else "否",
                    "记录数": summary["totalRecords"],
                    "重复记录": summary["duplicateRecords"],
                    "时间范围": period_text(summary["period"]),
                    "Error": summary["issueCount"]["error"],
                    "Warning": summary["issueCount"]["warning"],
                }
            )
        st.dataframe(module_rows, hide_index=True, width="stretch")
    render_next_action(
        "生成 AI 洞察报告",
        "指标计算",
        disabled=quality["hasBlockingIssues"]
        or (
            quality["requiresWarningAcknowledgement"]
            and not st.session_state["quality_acknowledged"]
        ),
    )


def render_metric_detail(metric: dict[str, Any]) -> None:
    with st.expander(f"这个数字如何计算 · {metric['metricId']}"):
        st.write(f"**公式：** {metric['formula']}")
        st.write(f"**时间范围：** {period_text(metric['period'])}")
        st.write(f"**可靠性：** {metric['reliability']}")
        st.write(
            "**可靠性原因：** "
            + ("；".join(metric["reliabilityReasons"]) or "无额外说明")
        )
        st.write(
            "**来源模块：** "
            + ("、".join(metric["sourceModules"]) or "unavailable")
        )
        if metric.get("caveat"):
            st.warning(metric["caveat"])
        references = metric.get("sourceReferences", [])
        if references:
            st.dataframe(
                [
                    {
                        "模块": ref["module"],
                        "文件": ref["fileName"],
                        "Sheet": ref["sheetName"],
                        "行范围": f"{ref['rowStart']}-{ref['rowEnd']}",
                        "字段": "、".join(ref["fields"]),
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
            f"文本摘要：{series['label']}，单位 {series['unit']}；"
            f"范围 {period_text(series['period'])}；来源 {source_text}。"
        )
    else:
        st.info(
            "没有足够的可比较时间点。请补充日期与对应数值字段；不会显示假图表。"
        )


def render_metrics() -> None:
    snapshot = snapshot_data()
    st.header("2 · AI 洞察报告")
    st.write("系统先统一计算关键增长指标，再生成可追溯、可供管理层审阅的洞察。")
    if not snapshot:
        st.info("尚无 Analysis Snapshot。")
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

    with st.expander("查看趋势、内容表现与计算口径"):
        follower_series = snapshot["metrics"]["followers"]["newFollowersTrend"]
        visitor_series = snapshot["metrics"]["visitors"]["pageViewsTrend"]
        left, right = st.columns(2)
        with left:
            render_series("Followers 新增趋势", follower_series, source_text="Followers")
        with right:
            render_series("Visitors Page Views 趋势", visitor_series, source_text="Visitors")
        groups = snapshot["metrics"]["content"]["byContentType"]
        if groups:
            rows = []
            for group in groups:
                row = {"内容类型": group["label"], "样本量": group["sampleSize"], "可靠性": group["reliability"]}
                for metric in group["metrics"]:
                    row[metric["label"]] = metric["formattedValue"]
                rows.append(row)
            st.dataframe(rows, hide_index=True, width="stretch")
    render_next_action("审阅 AI 洞察", "受众洞察")


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
        "批准",
        key=f"approve-{item_id}",
        disabled=approve_disabled or status == "approved",
        width="stretch",
    ):
        on_change("approved")
        st.rerun()
    if columns[1].button(
        "拒绝",
        key=f"reject-{item_id}",
        disabled=status == "rejected",
        width="stretch",
    ):
        on_change("rejected")
        st.rerun()
    if columns[2].button(
        "退回草稿",
        key=f"draft-{item_id}",
        disabled=status == "draft",
        width="stretch",
    ):
        on_change("draft")
        st.rerun()


def render_insights(category: str, title: str) -> None:
    report_section = "受众机会" if category == "audience" else "内容机会"
    st.header(f"2 · AI 洞察报告：{report_section}")
    st.write("AI 将历史表现转化为可行动的判断；管理团队决定哪些判断进入策略。")
    snapshot = snapshot_data()
    bundle = strategy_bundle()
    if not snapshot or not bundle:
        st.info("请先完成数据分析。")
        return
    if not snapshot["canEnterInsights"]:
        st.error("数据质量存在阻断问题，未生成洞察。")
        return
    if not warnings_are_acknowledged():
        st.warning("请先在“数据质量”页面确认非阻断 Warning。")
        return

    insights = [
        item
        for item in bundle["insights"]
        if item["category"] == category
    ]
    if not insights:
        missing = (
            "Followers/Visitors 画像或趋势字段"
            if category == "audience"
            else "Content 逐帖表现字段"
        )
        st.info(f"当前数据不足以生成该类洞察；建议补充 {missing}。")
        return

    render_agent_mode_notice()
    for insight in insights:
        with st.container(border=True):
            st.subheader(insight["title"])
            st.caption(
                f"{insight['approvalStatus']} · confidence "
                f"{insight['confidence']} · {insight['insightId']}"
            )
            st.write(f"**数据显示：** {insight['statement']}")
            st.write(f"**可能意味着：** {insight['possibleMeaning']}")
            st.write(f"**建议验证：** {insight['suggestedValidation']}")
            if insight["limitations"]:
                st.warning("；".join(insight["limitations"]))
            with st.expander("查看 Evidence"):
                for evidence in insight["evidence"]:
                    st.markdown(
                        f"`{evidence['metricId']}` · "
                        f"{evidence['label']} · {evidence['formattedValue']}"
                    )
                    st.caption(
                        f"{period_text(evidence['period'])} · "
                        f"来源 {'、'.join(evidence['sourceModules'])} · "
                        f"可靠性 {evidence['reliability']}"
                    )
            approval_controls(
                item_id=insight["insightId"],
                status=insight["approvalStatus"],
                on_change=lambda status, insight_id=insight[
                    "insightId"
                ]: update_insight_status(insight_id, status),
            )
    next_stage = "内容洞察" if category == "audience" else "策略建议"
    next_label = "继续审阅内容洞察" if category == "audience" else "进入营销策略"
    render_next_action(next_label, next_stage)


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
    st.header("3 · 营销策略与人工批准")
    st.write("AI 将已批准的洞察转化为优先行动；策略必须由业务负责人批准后才会进入执行计划。")
    snapshot = snapshot_data()
    bundle = strategy_bundle()
    if not snapshot or not bundle:
        st.info("请先完成分析。")
        return
    if not can_use_insights():
        st.warning("请先修复阻断问题或确认非阻断 Warning。")
        return
    approved_insight_ids = {
        item["insightId"]
        for item in bundle["insights"]
        if item["approvalStatus"] == "approved"
    }
    if not bundle["strategies"]:
        st.info("没有具备有效 Metric 引用的策略建议。")
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
            st.write(f"**目标：** {strategy['objective']}")
            st.write(f"**依据：** {strategy['rationale']}")
            for action in strategy["actions"]:
                st.write(f"- {action}")
            st.caption(
                "来源洞察："
                + "、".join(strategy["insightIds"])
                + " · Metric："
                + "、".join(strategy["metricIds"])
            )
            if not references_approved:
                st.warning("必须先批准该策略引用的全部洞察。")
            approval_controls(
                item_id=strategy["strategyId"],
                status=strategy["approvalStatus"],
                approve_disabled=not references_approved,
                on_change=lambda status, strategy_id=strategy[
                    "strategyId"
                ]: update_strategy_status(strategy_id, status),
            )
    _, strategy_count = approved_counts()
    render_next_action(
        "用已批准策略生成 30 天计划",
        "30 天计划",
        disabled=strategy_count == 0,
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
            label="正在局部重排计划，不重算 Snapshot 或洞察",
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
            label="正在校验引用并生成四周计划",
        )
        if result is not None:
            st.session_state["plan"] = result
            st.session_state["plan_history"] = []
            st.session_state["plan_generation_cancelled"] = False
    if result is not None:
        invalidate_plan_outputs()
        reset_buffer_workspace(result)


def render_plan_editor(plan: dict[str, Any]) -> None:
    st.markdown("### 单项建议编辑")
    choices = {
        f"{item['date']} · {item['topic']}": item
        for item in plan["contentCalendar"]
    }
    selected_label = st.selectbox(
        "选择内容日历项",
        list(choices),
        key=f"calendar-item-{plan['planId']}",
    )
    item = choices[selected_label]
    item_key = item["itemId"]
    topic = st.text_input(
        "主题",
        value=item["topic"],
        key=f"edit-topic-{plan['updatedAt']}-{item_key}",
    )
    audience = st.text_input(
        "目标受众",
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
        "建议状态",
        statuses,
        index=statuses.index(item["status"]),
        key=f"edit-status-{plan['updatedAt']}-{item_key}",
    )
    if st.button(
        "保存单项修改",
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
            label="正在保存单项修改",
        )
        if result is not None:
            push_plan_history()
            st.session_state["plan"] = result
            invalidate_plan_outputs()
            st.rerun()


def render_plan_report(plan: dict[str, Any]) -> None:
    st.divider()
    st.header("5 · 人工批准与 LinkedIn 草稿")
    st.write("逐项审阅 AI 生成的 LinkedIn 草稿。只有批准内容才会进入 Buffer Queue。")
    metadata = (
        f"生成 {plan['generatedAt']} · 更新 {plan['updatedAt']} · "
        f"分析 {period_text(plan['analysisPeriod'])} · "
        f"Prompt {plan['promptVersion']} · "
        f"模块 {'、'.join(plan['sourceModules'])}"
    )
    st.caption(metadata)
    st.subheader("管理层摘要")
    st.write(plan["executiveSummary"])
    with st.expander("查看风险、假设与证据"):
        for risk in plan["risksAndLimitations"]:
            st.warning(risk)
        for assumption in plan["assumptions"]:
            st.write(f"- {assumption}")

    view = st.radio(
        "计划视图",
        ("列表", "日历"),
        horizontal=True,
        key=f"plan-view-{plan['planId']}",
    )
    if view == "列表":
        for week in plan["fourWeekPlan"]:
            with st.expander(
                f"第 {week['weekNumber']} 周 · "
                f"{week['dateRange']['start']} 至 {week['dateRange']['end']}",
                expanded=week["weekNumber"] == 1,
            ):
                st.write(f"**目标：** {week['objective']}")
                st.write(f"**目标受众：** {week['targetAudience']}")
                st.write(f"**CTA：** {week['callToAction']}")
                st.write(
                    "**KPI：** " + "、".join(week["kpiMetricIds"])
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
                    "日期": item["date"],
                    "时间 / 时区": (
                        f"{item.get('scheduledTime', '未设置')} / "
                        f"{item.get('timeZone', plan['preferences']['timeZone'])}"
                    ),
                    "渠道": BUFFER_CHANNEL_LABELS.get(
                        item.get("channel"), item.get("channel", "未设置")
                    ),
                    "主题": item["topic"],
                    "形式": item["contentFormat"],
                    "受众": item["targetAudience"],
                    "CTA": item["callToAction"],
                    "策略": item["strategyId"],
                    "KPI": "、".join(item["measurementMetricIds"]),
                    "实验": "是" if item["isExperiment"] else "否",
                    "审批": BUFFER_APPROVAL_LABELS.get(
                        item["status"], item["status"]
                    ),
                    "Buffer 状态": BUFFER_WORKFLOW_LABELS.get(
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
        st.subheader("实验")
        for item in experiments:
            experiment = item["experiment"]
            with st.expander(f"{item['date']} · {item['topic']}"):
                st.write(f"**假设：** {experiment['hypothesis']}")
                st.write(
                    f"**成功标准：** {experiment['successCriteria']}"
                )
                st.write(f"**复盘时间：** {experiment['reviewDate']}")
                st.write(
                    "**KPI：** " + "、".join(experiment["metricIds"])
                )

    st.subheader("KPI Review Plan")
    st.dataframe(
        [
            {
                "复盘日期": review["reviewDate"],
                "KPI": "、".join(review["metricIds"]),
                "动作": review["action"],
                "比较规则": review["comparisonRule"],
            }
            for review in plan["kpiReviewPlan"]
        ],
        hide_index=True,
        width="stretch",
    )
    with st.expander("下一次导入需要回答的问题"):
        for question in plan["nextImportQuestions"]:
            st.write(f"- {question}")

    render_plan_editor(plan)
    controls = st.columns(3)
    if controls[0].button(
        "撤销最近一次修改",
        disabled=not st.session_state["plan_history"],
        width="stretch",
    ):
        history = list(st.session_state["plan_history"])
        st.session_state["plan"] = history.pop()
        st.session_state["plan_history"] = history
        invalidate_plan_outputs()
        st.rerun()

    if st.button(
        "批准完成，进入 Buffer Queue",
        type="primary",
        width="stretch",
        disabled=not any(
            item.get("status") == "confirmed"
            for item in plan.get("contentCalendar", [])
        ),
        help=(
            "先批准至少一条内容。导出只生成交接文件，不代表 Buffer 已导入或发布。"
        ),
    ):
        st.session_state["active_stage"] = "交付 Buffer"
        st.rerun()
    if controls[1].button(
        "确认当前计划",
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
            label="正在确认计划状态",
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
        "取消当前阶段",
        width="stretch",
    ):
        push_plan_history()
        st.session_state["plan"] = None
        st.session_state["plan_generation_cancelled"] = True
        invalidate_plan_outputs()
        reset_buffer_workspace(None)
        st.session_state["last_success"] = (
            "计划生成阶段已取消；Snapshot、审批和上传选择仍保留。"
        )
        st.rerun()


def render_plan() -> None:
    st.header("4 · 30 天内容计划")
    st.write("AI 将批准策略编排为可执行的内容节奏，团队保留对目标、资源与每条内容的最终控制。")
    snapshot = snapshot_data()
    if not snapshot:
        st.info("请先完成分析。")
        return
    if not can_use_insights():
        st.warning("当前质量门禁未通过，不能生成计划。")
        return
    insight_count, strategy_count = approved_counts()
    st.caption(f"已批准洞察 {insight_count} 条 · 已批准策略 {strategy_count} 条")
    if insight_count == 0 or strategy_count == 0:
        st.warning("至少批准一条洞察和一条引用该洞察的策略。")

    plan = st.session_state.get("plan")
    if st.session_state["plan_generation_cancelled"] and not plan:
        st.warning(
            "计划生成阶段已取消；数据和审批仍保留。修改设置后可直接重试。"
        )
        if st.button("重试计划生成"):
            st.session_state["plan_generation_cancelled"] = False
            st.rerun()

    with st.form("plan-settings"):
        st.text_input(
            "已确认业务目标",
            key="business_goal",
            max_chars=500,
            disabled=bool(plan),
        )
        st.checkbox(
            "我确认以上业务目标",
            key="business_goal_confirmed",
            disabled=bool(plan),
        )
        with st.expander("调整计划参数（可选）"):
            cols = st.columns(3)
            cols[0].selectbox("用户时区", TIME_ZONES, key="plan_timezone")
            cols[1].date_input("计划开始日期", key="plan_start_date", min_value=date.today())
            cols[2].slider("每周内容数量", min_value=1, max_value=7, key="posts_per_week")
            cols = st.columns(2)
            cols[0].number_input("团队规模（0 表示未提供）", min_value=0, max_value=100, step=1, key="team_size")
            cols[1].text_input("目标市场（可选）", key="target_market", max_chars=120)
            st.multiselect("可用内容资源", ("文案", "设计", "视频", "客户案例", "产品专家"), key="content_resources")
            st.text_input("重点受众", key="focus_audience", max_chars=200)
        submitted = st.form_submit_button(
            "应用局部调整" if plan else "生成 Mock 初稿",
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
    label: str = "正在校验 Buffer 交接内容",
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
    st.subheader("导出范围与渠道")
    st.caption(
        "默认窗口为项目时区中的今天起连续 14 天；范围外内容仍保留在原 30 天计划。"
    )
    with st.form("buffer-handoff-filters"):
        columns = st.columns(3)
        columns[0].date_input(
            "开始日期",
            key="buffer_start_date",
        )
        columns[1].date_input(
            "结束日期",
            key="buffer_end_date",
        )
        columns[2].selectbox(
            "最终使用的时区",
            TIME_ZONES,
            key="buffer_timezone",
            help=(
                "Buffer CSV 不包含时区列；Lucy 必须确保目标渠道在 Buffer 中"
                "配置为同一时区。"
            ),
        )
        st.multiselect(
            "目标渠道",
            tuple(BUFFER_CHANNEL_LABELS),
            key="buffer_channels",
            format_func=lambda value: BUFFER_CHANNEL_LABELS[value],
            help="每个渠道生成独立文件，渠道内部 enum 不使用界面文案作为业务键。",
        )
        apply_filters = st.form_submit_button(
            "应用范围并重新校验",
            type="primary",
            disabled=st.session_state["operation_in_progress"],
        )
    if apply_filters:
        if st.session_state["buffer_end_date"] < st.session_state[
            "buffer_start_date"
        ]:
            st.session_state["buffer_preview_attempted"] = True
            st.session_state["buffer_preview"] = None
            st.error("结束日期不能早于开始日期。")
        else:
            refresh_buffer_preview()
            st.rerun()

    if st.button(
        "恢复“未来 14 天”",
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
        refresh_buffer_preview("正在恢复未来 14 天交接范围")
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
            media_status = f"已提供 {len(item['mediaUrls'])} 个链接"
        elif item.get("mediaRequirement"):
            media_status = "待补素材"
        else:
            media_status = "无需媒体"
        if item["itemId"] in selected_ids and review["canExport"]:
            inclusion = "是"
        elif item["itemId"] in selected_ids:
            inclusion = "已选但将跳过"
        else:
            inclusion = "否"
        rows.append(
            {
                "日期": item["date"],
                "时间 / 时区": (
                    f"{item['scheduledTime']} / {item['timeZone']}"
                ),
                "渠道": BUFFER_CHANNEL_LABELS[item["channel"]],
                "标题": item["topic"],
                "文案预览": (
                    item["postText"][:90]
                    + ("…" if len(item["postText"]) > 90 else "")
                ),
                "媒体": media_status,
                "批准状态": BUFFER_APPROVAL_LABELS[item["status"]],
                "Buffer 准备状态": BUFFER_WORKFLOW_LABELS[
                    item["workflowStatus"]
                ],
                "校验": f"Error {error_count} / Warning {warning_count}",
                "纳入本次": inclusion,
            }
        )
    return rows


def render_buffer_selection(preview: dict[str, Any]) -> None:
    st.subheader("内容审核表")
    st.dataframe(
        buffer_review_rows(preview),
        hide_index=True,
        width="stretch",
    )
    st.caption(
        "表格可使用键盘浏览；移动端可在下方逐项展开错误并完成选择。"
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
                    "存在阻断错误、未获批准、渠道未选或超出日期范围时不可选择。"
                    if not selectable
                    else "勾选后纳入本次渠道级 CSV。"
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
                    f"问题 · {item['topic']}",
                    expanded=blocking,
                ):
                    for issue in visible_issues:
                        message = (
                            f"{issue['code']}：{issue['message']} "
                            f"建议：{issue['suggestedAction']}"
                        )
                        if issue["severity"] == "error":
                            st.error(message)
                        else:
                            st.warning(message)
        update_selection = st.form_submit_button(
            "更新选择与摘要",
            disabled=st.session_state["operation_in_progress"],
        )
    if update_selection:
        st.session_state["buffer_selected_item_ids"] = selected_ids
        st.session_state["buffer_warnings_acknowledged"] = False
        refresh_buffer_preview("正在更新 Buffer 导出选择")
        st.rerun()


def render_buffer_item_editor(plan: dict[str, Any]) -> None:
    st.subheader("导出前编辑")
    generation = st.session_state["buffer_editor_generation"]
    choices = {
        (
            f"{item['date']} {item['scheduledTime']} · "
            f"{BUFFER_CHANNEL_LABELS[item['channel']]} · {item['topic']}"
        ): item
        for item in plan["contentCalendar"]
    }
    selected_label = st.selectbox(
        "选择要审核或修复的内容",
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
                "文字短帖",
                "图文",
                "文档轮播",
                "短视频",
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
            "发布文案",
            value=item["postText"],
            height=180,
            max_chars=10_000,
            help="导出器不会截断或重写文案；空文案会被校验阻断。",
        )
        columns = st.columns(3)
        channel = columns[0].selectbox(
            "渠道",
            tuple(BUFFER_CHANNEL_LABELS),
            index=tuple(BUFFER_CHANNEL_LABELS).index(item["channel"]),
            format_func=lambda value: BUFFER_CHANNEL_LABELS[value],
        )
        content_format = columns[1].selectbox(
            "内容形式",
            format_options,
            index=0,
        )
        approval_status = columns[2].selectbox(
            "批准状态",
            tuple(BUFFER_APPROVAL_LABELS),
            index=tuple(BUFFER_APPROVAL_LABELS).index(item["status"]),
            format_func=lambda value: BUFFER_APPROVAL_LABELS[value],
        )
        columns = st.columns(3)
        scheduled_date = columns[0].date_input(
            "发布日期",
            value=date.fromisoformat(item["date"]),
        )
        scheduled_clock = columns[1].time_input(
            "发布时间",
            value=scheduled_time,
            step=timedelta(minutes=15),
        )
        time_zone = columns[2].selectbox(
            "时区",
            TIME_ZONES,
            index=TIME_ZONES.index(item["timeZone"]),
        )
        media_urls = st.text_area(
            "媒体直接链接（每行一个）",
            value="\n".join(item["mediaUrls"]),
            help=(
                "官方 CSV 当前只支持单图。无法提供公开直接 URL 时请留空，"
                "由 Lucy 在 Buffer 中手动添加素材。"
            ),
        )
        link_url = st.text_input(
            "链接 URL（可选）",
            value=item.get("linkUrl") or "",
        )
        campaign_tag = st.text_input(
            "Buffer Tag（可选）",
            value=item.get("campaignTag") or "",
            help="Tag 必须已存在于 Buffer 账户，且名称区分大小写。",
        )
        buttons = st.columns(2)
        save = buttons[0].form_submit_button(
            "保存并重新校验",
            type="primary",
            disabled=st.session_state["operation_in_progress"],
            width="stretch",
        )
        cancel = buttons[1].form_submit_button(
            "取消编辑",
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
            label="正在保存统一内容日历并重新校验",
            timeout_seconds=25,
        )
        if result is not None:
            push_plan_history()
            st.session_state["plan"] = result
            st.session_state["buffer_editor_generation"] += 1
            invalidate_plan_outputs()
            st.rerun()


def render_buffer_summary(preview: dict[str, Any]) -> None:
    st.subheader("导出摘要")
    summary = preview["summary"]
    columns = st.columns(5)
    columns[0].metric("选中内容", summary["selectedCount"])
    columns[1].metric("可导出", summary["exportableCount"])
    columns[2].metric("被排除", summary["excludedCount"])
    columns[3].metric("阻断错误", summary["blockingErrorCount"])
    columns[4].metric("Warning", summary["warningCount"])
    channel_counts = summary["channelCounts"]
    st.caption(
        f"范围 {preview['dateRange']['start']} 至 {preview['dateRange']['end']} · "
        f"时区 {preview['timeZone']} · "
        + " · ".join(
            f"{BUFFER_CHANNEL_LABELS[channel]} "
            f"{channel_counts.get(channel, 0)} 条"
            for channel in preview["channels"]
        )
    )
    for issue in preview["globalIssues"]:
        message = f"{issue['code']}：{issue['message']} {issue['suggestedAction']}"
        if issue["severity"] == "error":
            st.error(message)
        elif issue["severity"] == "warning":
            st.warning(message)
        else:
            st.info(message)
    st.caption(
        "Buffer Free 当前官方资料显示每渠道队列容量与单次上传上限均为 "
        f"{preview['guidance']['freePlan']['queueCapacityPerChannel']} 条；"
        f"资料检查日期 {preview['guidance']['reviewedAt']}。"
        "套餐与功能可能变化，请以 Buffer 当前页面为准。"
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
        label="正在生成渠道级 Buffer 交接文件",
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
        st.info("正在生成交接文件，请勿重复点击。")
    elif status == "failed":
        st.error("Buffer 交接文件生成失败；计划和审核结果仍保留，可直接重试。")
    if not result:
        return

    record = result["exportRecord"]
    st.success(
        f"已生成 {len(result['artifacts'])} 个渠道文件，"
        f"交接 {len(record['exportedItemIds'])} 项，"
        f"跳过 {len(record['skippedItemIds'])} 项。"
    )
    st.warning(
        "状态仅为 exported_to_buffer：文件生成成功不代表 Buffer 已导入、"
        "已排期或已发布。"
    )
    columns = st.columns(max(1, len(result["artifacts"])))
    for column, artifact in zip(columns, result["artifacts"]):
        clicked = column.download_button(
            f"下载 {BUFFER_CHANNEL_LABELS[artifact['channel']]} CSV",
            data=artifact["content"],
            file_name=artifact["fileName"],
            mime=artifact["mimeType"],
            key=f"download-buffer-{record['exportId']}-{artifact['channel']}",
            width="stretch",
        )
        if clicked:
            st.session_state["buffer_export_status"] = "downloaded"
            st.session_state["last_success"] = (
                f"{artifact['fileName']} 已交给浏览器下载；尚未发布。"
            )

    st.subheader("Lucy 的 Buffer 人工导入步骤")
    steps = (
        "登录 Lucy 有权限使用的 Buffer 账户。",
        "选择与文件名一致的社媒渠道。",
        "从该渠道设置的 Bulk Upload 下载最新模板并确认列名。",
        "上传生成的渠道级 CSV。",
        "检查日期、时间、渠道时区、文案、链接和媒体。",
        "在 Buffer 的 Review Content 页面完成最终确认。",
        "进入队列后返回 Demo 核对交接记录；不要把交接状态当作已发布。",
    )
    for index, step in enumerate(steps, start=1):
        st.write(f"{index}. {step}")
    st.markdown(
        (
            f'<a href="{BUFFER_BULK_UPLOAD_URL}" target="_blank" '
            'rel="noopener noreferrer">查看 Buffer 官方批量上传帮助</a>'
        ),
        unsafe_allow_html=True,
    )
    st.info(
        "Demo 没有访问 Buffer 账户，不保存账号、密码、Token 或 API Key。"
        "若媒体 URL 无法导入，请在 Buffer 中手动添加。Lucy 对最终排期和发布负责。"
    )


def render_buffer_handoff() -> None:
    st.header("6 · Buffer Queue")
    st.write("将已批准的 LinkedIn 草稿交接至 Buffer，供内容团队进行最终排期与发布。")
    st.info("企业控制点：本系统只准备队列文件，不会自动发布。", icon=":material/verified_user:")
    plan = st.session_state.get("plan")
    if not plan:
        st.info("请先生成 30 天计划。")
        return
    approved_count = sum(
        item.get("status") == "confirmed"
        for item in plan.get("contentCalendar", [])
    )
    if approved_count == 0:
        st.warning(
            "当前没有已批准内容。可在下方编辑器逐项批准，或先回到 30 天计划确认计划。"
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
        st.info("尚无交接预览。修正范围后点击“重新校验”。")
        if st.button(
            "重新校验 Buffer 交接",
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
        "撤销最近一次内容修改",
        disabled=not st.session_state["plan_history"],
        width="stretch",
    ):
        history = list(st.session_state["plan_history"])
        st.session_state["plan"] = history.pop()
        st.session_state["plan_history"] = history
        invalidate_plan_outputs()
        st.rerun()
    if controls[1].button(
        "重新校验",
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
            "我已审阅 Warning，并确认由 Lucy 在 Buffer 中完成最终检查",
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
        st.caption("没有可执行内容：请先修复阻断错误并重新校验。")
    elif requires_warning and not st.session_state[
        "buffer_warnings_acknowledged"
    ]:
        st.caption("导出暂不可用：请先确认已审阅 Warning。")
    if st.button(
        "生成 Buffer 导入准备文件",
        type="primary",
        disabled=export_disabled,
        width="stretch",
        help=(
            "只导出已批准、范围内且无阻断错误的内容；"
            "导出成功不代表 Buffer 已导入或发布。"
        ),
    ):
        export_buffer_handoff(st.session_state["plan"])
        st.rerun()

    render_buffer_result()
    records = st.session_state["buffer_export_records"]
    if records:
        with st.expander("当前会话导出记录"):
            st.dataframe(
                [
                    {
                        "Export ID": record["exportId"],
                        "生成时间": record["generatedAt"],
                        "范围": (
                            f"{record['dateRange']['start']} 至 "
                            f"{record['dateRange']['end']}"
                        ),
                        "时区": record["timeZone"],
                        "渠道": "、".join(
                            BUFFER_CHANNEL_LABELS[channel]
                            for channel in record["channels"]
                        ),
                        "已交接": len(record["exportedItemIds"]),
                        "跳过": len(record["skippedItemIds"]),
                        "状态": record["status"],
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
        st.write(f"**可能意味着：** {answer['possibleMeaning']}")
    if answer.get("suggestedValidation"):
        st.write(f"**建议验证：** {answer['suggestedValidation']}")
    citations = answer.get("citations", [])
    if citations:
        with st.expander("展开 evidence"):
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
                        f"来源 {'、'.join(metric['sourceModules'])}"
                    )
    change = answer.get("suggestedPlanChange")
    plan = st.session_state.get("plan")
    change_key = f"chat-change-{message_index}"
    if change and plan and change_key not in st.session_state["applied_chat_changes"]:
        if st.button("审阅并应用计划修改", key=change_key):
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
                label="正在应用经用户确认的计划修改",
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
        label="Mock Agent 正在检索当前项目证据",
        timeout_seconds=20,
    )
    if answer is not None:
        st.session_state["chat_history"].append(
            {"role": "assistant", "answer": answer}
        )


def render_chat() -> None:
    st.markdown('<span class="section-kicker">Evidence chat</span>', unsafe_allow_html=True)
    st.header("基于当前项目的问答")
    if not snapshot_data():
        st.info("请先完成数据分析。")
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
        "询问指标、趋势、质量、证据或计划修改",
        disabled=st.session_state["operation_in_progress"],
    )
    question = typed_question or pending_question
    if question:
        submit_question(question)
        st.rerun()


def render_exports() -> None:
    st.markdown('<span class="section-kicker">Safe exports</span>', unsafe_allow_html=True)
    st.header("报告导出")
    snapshot = snapshot_data()
    bundle = strategy_bundle()
    if not snapshot or not bundle:
        st.info("请先完成分析。")
        return
    plan = st.session_state.get("plan")
    st.write(
        "导出只包含确定性 Snapshot、洞察/策略引用和计划；"
        "不包含 API Key、内部 Prompt、原始文件或原始单元格。"
    )
    if not plan:
        st.warning(
            "尚未生成计划：Markdown 和 JSON 可导出当前分析，"
            "内容日历 CSV 将保持不可用。"
        )
    if st.button(
        "准备三种安全导出",
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
            label="正在清洗并生成导出文件",
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
        st.info("导出处理中，请勿重复点击。")
    elif status == "failed":
        st.error("导出失败；当前分析仍保留，可直接重试。")
    elif status == "ready":
        st.success("导出已准备完成。点击文件按钮下载。")

    artifacts = st.session_state.get("export_artifacts")
    if not artifacts:
        return
    columns = st.columns(3)
    definitions = (
        ("markdown", "下载完整 Markdown 报告"),
        ("calendarCsv", "下载 30 天日历 CSV"),
        ("structuredJson", "下载结构化分析 JSON"),
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
                f"{artifact['fileName']} 已交给浏览器下载。"
            )


def render_current_stage() -> None:
    stage = st.session_state["active_stage"]
    if stage == "数据接入":
        render_ingestion()
    elif stage == "数据质量":
        render_quality()
    elif stage == "指标计算":
        render_metrics()
    elif stage == "受众洞察":
        render_insights("audience", "Audience Insights")
    elif stage == "内容洞察":
        render_insights("content", "Content Insights")
    elif stage == "策略建议":
        render_strategies()
    elif stage == "30 天计划":
        render_plan()
    elif stage == "交付 Buffer":
        render_buffer_handoff()
    elif stage == "证据问答":
        render_chat()
    elif stage == "报告导出":
        render_exports()


initialize_state()
process_pending_actions()
render_header()
render_sidebar()
render_last_status()
render_current_stage()

st.divider()
st.caption(
    "Demo 边界：仅处理 LinkedIn 聚合分析导出；不识别匿名访客、具体关注者或个人购买意向。"
    "相关性不代表因果，Proxy Ratio 不是真实转化率。"
)
