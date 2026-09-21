"""构建岗位分析 LangGraph。"""

from functools import partial
from typing import Literal

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from job_agent.agent.nodes import (
    DraftCandidate,
    ExtractJob,
    MatchRequirements,
    PersistEvidence,
    ask_for_evidence_node,
    check_evidence_node,
    draft_candidate_node,
    extract_job_node,
    mark_needs_clarification_node,
    mark_ready_node,
    persist_evidence_node,
    review_candidate_node,
    retrieve_evidence_node,
)
from job_agent.agent.state import JobAnalysisState
from job_agent.domain.jobs import JobPosting, JobRequirement, RequirementPriority
from job_agent.domain.matching import CandidateEvidenceDraft, RequirementEvidence
from job_agent.domain.models import Evidence, EvidenceStatus


CHECKPOINT_ALLOWED_TYPES = (
    JobPosting,
    JobRequirement,
    RequirementPriority,
    RequirementEvidence,
    CandidateEvidenceDraft,
    Evidence,
    EvidenceStatus,
)


def route_after_evidence_check(
    state: JobAnalysisState,
) -> Literal["mark_ready", "mark_needs_clarification"]:
    """根据是否缺少硬性要求证据选择下一个节点。"""

    if state["missing_required"]:
        return "mark_needs_clarification"

    return "mark_ready"


def route_after_interactive_evidence_check(
    state: JobAnalysisState,
) -> Literal["mark_ready", "ask_for_evidence"]:
    """交互模式下，有证据缺口时进入人工追问节点。"""

    if state["missing_required"]:
        return "ask_for_evidence"

    return "mark_ready"


def route_after_candidate_review(
    state: JobAnalysisState,
) -> Literal["persist_evidence", "mark_needs_clarification"]:
    """根据用户是否确认候选草稿决定是否保存证据。"""

    if state["candidate_approved"]:
        return "persist_evidence"

    return "mark_needs_clarification"


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


def build_interactive_job_analysis_graph(
    extract_job: ExtractJob,
    match_requirements: MatchRequirements,
    draft_candidate: DraftCandidate,
    persist_evidence: PersistEvidence,
) -> CompiledStateGraph:
    """构建能够暂停并等待用户补充证据的岗位分析图。"""

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
    builder.add_node("ask_for_evidence", ask_for_evidence_node)
    builder.add_node(
        "draft_candidate",
        partial(
            draft_candidate_node,
            draft_candidate=draft_candidate,
        ),
    )
    builder.add_node("review_candidate", review_candidate_node)
    builder.add_node(
        "persist_evidence",
        partial(
            persist_evidence_node,
            persist_evidence=persist_evidence,
        ),
    )
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
        route_after_interactive_evidence_check,
        {
            "mark_ready": "mark_ready",
            "ask_for_evidence": "ask_for_evidence",
        },
    )
    builder.add_edge("mark_ready", END)
    builder.add_edge("ask_for_evidence", "draft_candidate")
    builder.add_edge("draft_candidate", "review_candidate")
    builder.add_conditional_edges(
        "review_candidate",
        route_after_candidate_review,
        {
            "persist_evidence": "persist_evidence",
            "mark_needs_clarification": "mark_needs_clarification",
        },
    )
    builder.add_edge("persist_evidence", "retrieve_evidence")
    builder.add_edge("mark_needs_clarification", END)

    return builder.compile(
        checkpointer=InMemorySaver(
            serde=JsonPlusSerializer(
                allowed_msgpack_modules=CHECKPOINT_ALLOWED_TYPES,
            )
        ),
        name="interactive_job_analysis",
    )
