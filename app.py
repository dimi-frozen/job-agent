"""Career Evidence Agent 的最小 Streamlit 演示页面。"""

import sqlite3
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any
from uuid import uuid4

import streamlit as st
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from job_agent.agent.graph import build_complete_job_analysis_graph
from job_agent.domain.models import Profile
from job_agent.domain.reports import (
    ApplicationRecommendation,
    JobAnalysisReport,
    RequirementAssessmentStatus,
)
from job_agent.llm.client import DeepSeekClient
from job_agent.rag.evidence_index import EvidenceIndex
from job_agent.services.candidate_drafting import draft_candidate_evidence
from job_agent.services.evidence_matching import match_job_requirements
from job_agent.services.evidence_persistence import persist_confirmed_evidence
from job_agent.services.evidence_refinement import refine_requirement_evidence
from job_agent.services.job_extraction import extract_job_posting
from job_agent.services.job_reporting import build_job_analysis_report
from job_agent.services.resume_suggestions import generate_resume_suggestions
from job_agent.storage.sqlite import (
    connect,
    initialize_schema,
    load_profile,
    save_profile,
)


PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIRECTORY = PROJECT_ROOT / "data"
DEFAULT_PROFILE_ID = "local-demo-profile"
RUNTIME_VERSION = "evidence-refinement-v2"


@dataclass
class AppRuntime:
    """保存一次页面会话需要复用的本地资源。"""

    profile: Profile
    graph: CompiledStateGraph
    connection: sqlite3.Connection
    index: EvidenceIndex


def build_runtime() -> AppRuntime:
    """组装真实业务依赖，并构建完整岗位分析图。"""

    client = DeepSeekClient()
    connection = connect(
        DATA_DIRECTORY / "job_agent.db",
        check_same_thread=False,
    )
    index: EvidenceIndex | None = None

    try:
        initialize_schema(connection)
        profile = load_profile(connection, DEFAULT_PROFILE_ID)
        if profile is None:
            profile = Profile(
                id=DEFAULT_PROFILE_ID,
                name="本地演示档案",
            )
            save_profile(connection, profile)

        index = EvidenceIndex(DATA_DIRECTORY / "chroma")
        graph = build_complete_job_analysis_graph(
            extract_job=partial(extract_job_posting, client=client),
            match_requirements=partial(
                match_job_requirements,
                index=index,
                connection=connection,
            ),
            refine_evidence=partial(
                refine_requirement_evidence,
                client=client,
            ),
            draft_candidate=partial(
                draft_candidate_evidence,
                client=client,
            ),
            persist_evidence=partial(
                persist_confirmed_evidence,
                connection=connection,
                index=index,
            ),
            build_report=build_job_analysis_report,
            generate_suggestions=partial(
                generate_resume_suggestions,
                client=client,
            ),
        )
        return AppRuntime(
            profile=profile,
            graph=graph,
            connection=connection,
            index=index,
        )
    except Exception:
        if index is not None:
            index.close()
        connection.close()
        raise


def initialize_page_state() -> None:
    """初始化只属于当前浏览器会话的页面状态。"""

    if st.session_state.get("runtime_version") != RUNTIME_VERSION:
        previous_runtime = st.session_state.get("runtime")
        if previous_runtime is not None:
            previous_runtime.index.close()
            previous_runtime.connection.close()
        st.session_state.runtime = build_runtime()
        st.session_state.runtime_version = RUNTIME_VERSION
        st.session_state.thread_id = str(uuid4())
        st.session_state.graph_result = None
        st.session_state.jd_text = ""
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = str(uuid4())
    if "graph_result" not in st.session_state:
        st.session_state.graph_result = None
    if "jd_text" not in st.session_state:
        st.session_state.jd_text = ""


def graph_config() -> dict[str, dict[str, str]]:
    """返回当前分析使用的 LangGraph 线程配置。"""

    return {
        "configurable": {
            "thread_id": st.session_state.thread_id,
        }
    }


def invoke_graph(input_value: dict[str, str] | Command) -> None:
    """执行或恢复 Graph，并保存最新结果。"""

    runtime: AppRuntime = st.session_state.runtime
    try:
        with st.spinner("正在分析，请稍候……"):
            result = runtime.graph.invoke(
                input_value,
                config=graph_config(),
            )
    except Exception as error:
        st.error(f"执行失败：{error}")
        return

    st.session_state.graph_result = result
    st.rerun()


def reset_analysis() -> None:
    """使用新的 thread_id 开始另一份 JD 分析。"""

    st.session_state.thread_id = str(uuid4())
    st.session_state.graph_result = None
    st.session_state.jd_text = ""


def render_initial_form() -> None:
    """显示首次提交 JD 的表单。"""

    with st.form("job_description_form"):
        jd_text = st.text_area(
            "招聘信息原文",
            value=st.session_state.jd_text,
            height=260,
            placeholder="请粘贴完整的岗位描述……",
        )
        submitted = st.form_submit_button(
            "开始分析",
            type="primary",
        )

    if submitted:
        if not jd_text.strip():
            st.warning("请先粘贴招聘信息。")
            return

        st.session_state.jd_text = jd_text
        runtime: AppRuntime = st.session_state.runtime
        invoke_graph(
            {
                "profile_id": runtime.profile.id,
                "jd_text": jd_text,
            }
        )


def render_clarification_form(payload: dict[str, Any]) -> None:
    """显示证据缺口和经历补充表单。"""

    st.warning("这项硬性要求暂时没有可靠证据。")
    st.write(f"岗位要求：{payload['requirement']}")

    with st.form("clarification_form"):
        answer = st.text_area(
            "请描述一段与该要求有关的真实经历",
            height=180,
        )
        submitted = st.form_submit_button(
            "整理为候选证据",
            type="primary",
        )

    if submitted:
        if not answer.strip():
            st.warning("补充内容不能为空。")
            return
        invoke_graph(Command(resume=answer))


def render_candidate_review(payload: dict[str, Any]) -> None:
    """显示候选证据草稿和人工审核表单。"""

    st.subheader("确认候选证据")
    st.json(payload["candidate_draft"])

    with st.form("candidate_review_form"):
        approved = st.radio(
            "是否把这条草稿保存为个人能力证据？",
            options=[True, False],
            format_func=lambda value: "确认保存" if value else "拒绝",
        )
        submitted = st.form_submit_button(
            "提交审核结果",
            type="primary",
        )

    if submitted:
        invoke_graph(Command(resume=approved))


def render_evidence(title: str, evidence_items: list) -> None:
    """显示一组能够追溯来源的证据。"""

    if not evidence_items:
        return

    st.markdown(f"**{title}**")
    for evidence in evidence_items:
        st.write(f"- {evidence.summary}")
        st.caption(
            f"状态：{evidence.status.value}｜来源："
            f"{evidence.source_type}｜引用：{evidence.source_ref or '无'}"
        )


def render_report(report: JobAnalysisReport) -> None:
    """显示事实报告和候选简历建议。"""

    st.success("岗位分析已完成。")
    st.subheader(report.job.title or "未识别岗位名称")
    if report.job.company:
        st.caption(report.job.company)

    recommendation_text = {
        ApplicationRecommendation.READY_TO_APPLY: "当前证据支持投递",
        ApplicationRecommendation.BUILD_EVIDENCE_FIRST: "建议先补充硬性证据",
    }
    st.metric(
        "投递建议",
        recommendation_text[report.recommendation],
    )

    st.subheader("岗位要求与证据")
    status_text = {
        RequirementAssessmentStatus.SUPPORTED: "已有可靠证据",
        RequirementAssessmentStatus.CANDIDATE_ONLY: "只有候选证据",
        RequirementAssessmentStatus.MISSING: "缺少证据",
    }
    for assessment in report.assessments:
        requirement = assessment.requirement
        with st.expander(
            f"{requirement.text}｜{status_text[assessment.status]}",
            expanded=True,
        ):
            st.caption(
                f"优先级：{requirement.priority.value}｜"
                f"JD 原文：{requirement.source_quote}"
            )
            render_evidence(
                "可靠证据",
                assessment.supporting_evidence,
            )
            render_evidence(
                "候选证据",
                assessment.candidate_evidence,
            )

    if report.missing_required:
        st.subheader("仍缺少证据的硬性要求")
        for requirement in report.missing_required:
            st.write(f"- {requirement.text}")

    st.subheader("候选简历建议")
    if not report.resume_suggestions:
        st.info("当前没有生成候选简历建议。")
    for suggestion in report.resume_suggestions:
        st.write(f"- {suggestion.text}")
        st.caption(
            "引用证据：" + ", ".join(suggestion.evidence_ids)
        )


def render_current_stage() -> None:
    """根据 Graph 结果显示当前交互阶段。"""

    result = st.session_state.graph_result
    if result is None:
        render_initial_form()
        return

    interrupts = result.get("__interrupt__", ())
    if interrupts:
        payload = interrupts[0].value
        if payload["kind"] == "evidence_clarification":
            render_clarification_form(payload)
            return
        if payload["kind"] == "candidate_evidence_review":
            render_candidate_review(payload)
            return
        st.error(f"无法识别的中断类型：{payload['kind']}")
        return

    report = result.get("analysis_report")
    if report is None:
        st.error("工作流已经结束，但没有返回岗位分析报告。")
        return
    render_report(report)


st.set_page_config(
    page_title="Career Evidence Agent",
    page_icon="🧭",
    layout="centered",
)
st.title("Career Evidence Agent")
st.caption("根据真实能力证据分析岗位，并生成可追溯的候选简历建议。")

try:
    initialize_page_state()
except Exception as error:
    st.error(f"初始化失败：{error}")
    st.info("请根据 .env.example 配置 DEEPSEEK_API_KEY 后重新运行。")
    st.stop()

runtime: AppRuntime = st.session_state.runtime
with st.sidebar:
    st.subheader("当前档案")
    st.write(runtime.profile.name)
    st.code(runtime.profile.id)
    st.caption(f"会话线程：{st.session_state.thread_id}")
    if st.button("分析另一份 JD"):
        reset_analysis()
        st.rerun()

render_current_stage()
