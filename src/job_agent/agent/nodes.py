"""岗位分析图中的工作节点。"""

from collections.abc import Callable

from langgraph.types import interrupt

from job_agent.agent.state import JobAnalysisState
from job_agent.domain.jobs import (
    JobPosting,
    JobRequirement,
    RequirementPriority,
)
from job_agent.domain.matching import (
    CandidateEvidenceDraft,
    RequirementEvidence,
)
from job_agent.domain.models import Evidence, EvidenceStatus
from job_agent.domain.reports import JobAnalysisReport, ResumeSuggestionDraft


ExtractJob = Callable[[str], JobPosting]
MatchRequirements = Callable[[JobPosting], list[RequirementEvidence]]
DraftCandidate = Callable[
    [JobRequirement, str],
    CandidateEvidenceDraft,
]
PersistEvidence = Callable[[str, CandidateEvidenceDraft], Evidence]
BuildReport = Callable[
    [JobPosting, list[RequirementEvidence]],
    JobAnalysisReport,
]
GenerateSuggestions = Callable[
    [JobAnalysisReport],
    list[ResumeSuggestionDraft],
]
RefineEvidence = Callable[
    [list[RequirementEvidence]],
    list[RequirementEvidence],
]

RELIABLE_EVIDENCE_STATUSES = {
    EvidenceStatus.CONFIRMED,
    EvidenceStatus.VERIFIED,
}


def _next_unclarified_requirement(
    state: JobAnalysisState,
) -> JobRequirement:
    """返回本轮尚未补充过证据的第一条硬性要求。"""

    clarified_requirements = set(state.get("clarified_requirements", []))
    for requirement in state["missing_required"]:
        if requirement.text not in clarified_requirements:
            return requirement

    raise ValueError("没有尚未补充证据的岗位要求")


def extract_job_node(
    state: JobAnalysisState,
    extract_job: ExtractJob,
) -> dict[str, JobPosting]:
    """从原始 JD 提取岗位对象。"""

    return {"job": extract_job(state["jd_text"])}


def retrieve_evidence_node(
    state: JobAnalysisState,
    match_requirements: MatchRequirements,
) -> dict[str, list[RequirementEvidence]]:
    """为岗位中的每条要求检索个人证据。"""

    return {
        "requirement_evidence": match_requirements(state["job"]),
    }


def check_evidence_node(
    state: JobAnalysisState,
) -> dict[str, list[JobRequirement]]:
    """找出没有 confirmed 或 verified 证据的硬性要求。"""

    missing_required = []

    for match in state["requirement_evidence"]:
        if match.requirement.priority is RequirementPriority.PREFERRED:
            continue

        has_reliable_evidence = any(
            evidence.status in RELIABLE_EVIDENCE_STATUSES
            for evidence in match.evidence
        )
        if not has_reliable_evidence:
            missing_required.append(match.requirement)

    return {"missing_required": missing_required}


def refine_evidence_node(
    state: JobAnalysisState,
    refine_evidence: RefineEvidence,
) -> dict[str, list[RequirementEvidence]]:
    """严格筛选能够直接支撑每条岗位要求的证据。"""

    return {
        "requirement_evidence": refine_evidence(
            state["requirement_evidence"]
        )
    }


def ask_for_evidence_node(
    state: JobAnalysisState,
) -> dict[str, str]:
    """暂停工作流，请用户补充与第一条证据缺口相关的经历。"""

    requirement = _next_unclarified_requirement(state)

    answer = interrupt(
        {
            "kind": "evidence_clarification",
            "question": "请描述你与这项岗位要求有关的真实经历。",
            "requirement": requirement.text,
        }
    )

    return {"clarification_answer": answer}


def draft_candidate_node(
    state: JobAnalysisState,
    draft_candidate: DraftCandidate,
) -> dict[str, CandidateEvidenceDraft]:
    """把用户回答整理成等待确认的候选证据草稿。"""

    requirement = _next_unclarified_requirement(state)
    draft = draft_candidate(
        requirement,
        state["clarification_answer"],
    )

    return {"candidate_draft": draft}


def review_candidate_node(
    state: JobAnalysisState,
) -> dict[str, bool]:
    """暂停工作流，请用户确认或拒绝候选证据草稿。"""

    approved = interrupt(
        {
            "kind": "candidate_evidence_review",
            "question": "是否确认把这段内容保存为个人能力证据？",
            "candidate_draft": state["candidate_draft"].model_dump(
                mode="json"
            ),
        }
    )

    if not isinstance(approved, bool):
        raise ValueError("候选证据审核结果必须是布尔值")

    return {"candidate_approved": approved}


def persist_evidence_node(
    state: JobAnalysisState,
    persist_evidence: PersistEvidence,
) -> dict[str, str | list[str]]:
    """把用户确认的候选草稿保存为正式证据。"""

    evidence = persist_evidence(
        state["profile_id"],
        state["candidate_draft"],
    )
    requirement = _next_unclarified_requirement(state)
    clarified_requirements = [
        *state.get("clarified_requirements", []),
        requirement.text,
    ]
    return {
        "saved_evidence_id": evidence.id,
        "clarified_requirements": clarified_requirements,
    }


def mark_ready_node(
    state: JobAnalysisState,
) -> dict[str, str]:
    """标记当前岗位已有足够的硬性要求证据。"""

    return {"status": "ready_for_analysis"}


def mark_needs_clarification_node(
    state: JobAnalysisState,
) -> dict[str, str]:
    """标记当前岗位仍有需要追问的硬性要求。"""

    return {"status": "needs_clarification"}


def build_report_node(
    state: JobAnalysisState,
    build_report: BuildReport,
) -> dict[str, JobAnalysisReport]:
    """根据结构化岗位和匹配证据生成事实报告。"""

    report = build_report(
        state["job"],
        state["requirement_evidence"],
    )
    return {"analysis_report": report}


def generate_suggestions_node(
    state: JobAnalysisState,
    generate_suggestions: GenerateSuggestions,
) -> dict[str, JobAnalysisReport]:
    """生成候选简历建议并写回报告副本。"""

    report = state["analysis_report"]
    suggestions = generate_suggestions(report)
    updated_report = report.model_copy(
        update={"resume_suggestions": suggestions}
    )
    return {"analysis_report": updated_report}
