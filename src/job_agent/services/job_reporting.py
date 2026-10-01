"""根据岗位要求与证据匹配结果生成可追溯的事实报告。"""

from job_agent.domain.jobs import JobPosting, RequirementPriority
from job_agent.domain.matching import RequirementEvidence
from job_agent.domain.models import EvidenceStatus
from job_agent.domain.reports import (
    ApplicationRecommendation,
    JobAnalysisReport,
    RequirementAssessment,
    RequirementAssessmentStatus,
)


RELIABLE_EVIDENCE_STATUSES = {
    EvidenceStatus.CONFIRMED,
    EvidenceStatus.VERIFIED,
}


def build_job_analysis_report(
    job: JobPosting,
    matches: list[RequirementEvidence],
) -> JobAnalysisReport:
    """使用固定规则生成岗位要求的证据覆盖报告。"""

    if len(matches) != len(job.requirements) or any(
        match.requirement != requirement
        for match, requirement in zip(matches, job.requirements, strict=True)
    ):
        raise ValueError("岗位要求与证据匹配结果不完整或顺序不一致")

    assessments: list[RequirementAssessment] = []
    missing_required = []

    for match in matches:
        supporting_evidence = [
            evidence
            for evidence in match.evidence
            if evidence.status in RELIABLE_EVIDENCE_STATUSES
        ]
        candidate_evidence = [
            evidence
            for evidence in match.evidence
            if evidence.status is EvidenceStatus.CANDIDATE
        ]

        if supporting_evidence:
            status = RequirementAssessmentStatus.SUPPORTED
        elif candidate_evidence:
            status = RequirementAssessmentStatus.CANDIDATE_ONLY
        else:
            status = RequirementAssessmentStatus.MISSING

        assessment = RequirementAssessment(
            requirement=match.requirement,
            status=status,
            supporting_evidence=supporting_evidence,
            candidate_evidence=candidate_evidence,
        )
        assessments.append(assessment)

        if (
            match.requirement.priority is RequirementPriority.REQUIRED
            and status is not RequirementAssessmentStatus.SUPPORTED
        ):
            missing_required.append(match.requirement)

    recommendation = (
        ApplicationRecommendation.BUILD_EVIDENCE_FIRST
        if missing_required
        else ApplicationRecommendation.READY_TO_APPLY
    )

    return JobAnalysisReport(
        job=job,
        assessments=assessments,
        missing_required=missing_required,
        recommendation=recommendation,
    )
