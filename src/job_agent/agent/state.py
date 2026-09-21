"""LangGraph 岗位分析流程共享的业务状态。"""

from typing import Literal, TypedDict

from job_agent.domain.jobs import JobPosting, JobRequirement

from job_agent.domain.matching import (
    CandidateEvidenceDraft,
    RequirementEvidence,
)


class JobAnalysisState(TypedDict, total=False):
    """保存一次岗位分析在各节点之间传递的数据。"""

    profile_id: str  # 用户档案 ID
    jd_text: str  # 原始 JD 文本
    job: JobPosting  # 结构化岗位信息
    requirement_evidence: list[RequirementEvidence]  # 岗位要求及其匹配证据
    missing_required: list[JobRequirement]  # 缺少有效证据的必需要求
    status: Literal["ready_for_analysis", "needs_clarification"]  # 分析路由状态
    clarification_answer: str  # 用户补充的原始回答
    candidate_draft: CandidateEvidenceDraft  # 待确认的候选证据草稿
    candidate_approved: bool  # 用户是否批准候选草稿
    saved_evidence_id: str  # 已保存证据的 ID
