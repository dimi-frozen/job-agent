"""LangGraph 岗位分析流程共享的业务状态。"""

from typing import Literal, TypedDict

from job_agent.domain.jobs import JobPosting, JobRequirement
from job_agent.domain.matching import RequirementEvidence


class JobAnalysisState(TypedDict, total=False):
    """保存一次岗位分析在各节点之间传递的数据。"""

    profile_id: str
    jd_text: str
    job: JobPosting
    requirement_evidence: list[RequirementEvidence]
    missing_required: list[JobRequirement]
    status: Literal["ready_for_analysis", "needs_clarification"]
