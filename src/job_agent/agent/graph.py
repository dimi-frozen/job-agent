"""构建岗位分析 LangGraph。"""

from functools import partial
from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from job_agent.agent.nodes import (
    ExtractJob,
    MatchRequirements,
    check_evidence_node,
    extract_job_node,
    mark_needs_clarification_node,
    mark_ready_node,
    retrieve_evidence_node,
)
from job_agent.agent.state import JobAnalysisState


def route_after_evidence_check(
    state: JobAnalysisState,
) -> Literal["mark_ready", "mark_needs_clarification"]:
    """根据是否缺少硬性要求证据选择下一个节点。"""

    if state["missing_required"]:
        return "mark_needs_clarification"

    return "mark_ready"


def build_job_analysis_graph(
    extract_job: ExtractJob,
    match_requirements: MatchRequirements,
) -> CompiledStateGraph:
    """使用外部依赖构建并编译岗位分析图。"""

    builder = StateGraph(JobAnalysisState)
    builder.add_node(
        "extract_job",
        partial(extract_job_node, extract_job=extract_job),
    )
    builder.add_node(
        "retrieve_evidence",
        partial(
            retrieve_evidence_node,
            match_requirements=match_requirements,
        ),
    )
    builder.add_node("check_evidence", check_evidence_node)
    builder.add_node("mark_ready", mark_ready_node)
    builder.add_node(
        "mark_needs_clarification",
        mark_needs_clarification_node,
    )

    builder.add_edge(START, "extract_job")
    builder.add_edge("extract_job", "retrieve_evidence")
    builder.add_edge("retrieve_evidence", "check_evidence")
    builder.add_conditional_edges(
        "check_evidence",
        route_after_evidence_check,
        {
            "mark_ready": "mark_ready",
            "mark_needs_clarification": "mark_needs_clarification",
        },
    )
    builder.add_edge("mark_ready", END)
    builder.add_edge("mark_needs_clarification", END)

    return builder.compile(name="job_analysis")
