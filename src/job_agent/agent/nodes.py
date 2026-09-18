"""岗位分析图中的工作节点。"""

from collections.abc import Callable

from job_agent.agent.state import JobAnalysisState
from job_agent.domain.jobs import (
    JobPosting,
    JobRequirement,
    RequirementPriority,
)
from job_agent.domain.matching import RequirementEvidence
from job_agent.domain.models import EvidenceStatus


ExtractJob = Callable[[str], JobPosting]
MatchRequirements = Callable[[JobPosting], list[RequirementEvidence]]

RELIABLE_EVIDENCE_STATUSES = {
    EvidenceStatus.CONFIRMED,
    EvidenceStatus.VERIFIED,
}


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
