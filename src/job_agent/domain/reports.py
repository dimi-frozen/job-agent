"""岗位分析报告与候选简历建议的领域模型。"""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from job_agent.domain.jobs import JobPosting, JobRequirement
from job_agent.domain.models import Evidence


class RequirementAssessmentStatus(StrEnum):
    """表示一条岗位要求当前获得了什么程度的证据支持。"""

    SUPPORTED = "supported"  # 至少有一条 confirmed 或 verified 证据
    CANDIDATE_ONLY = "candidate_only"  # 只有 candidate，没有可靠证据
    MISSING = "missing"  # 没有任何可用证据


class ApplicationRecommendation(StrEnum):
    """表示当前证据是否足以支持投递。"""

    READY_TO_APPLY = "ready_to_apply"  # 所有硬性要求都有可靠证据
    BUILD_EVIDENCE_FIRST = "build_evidence_first"  # 仍有硬性证据缺口


class RequirementAssessment(BaseModel):
    """保存一条岗位要求的证据判断结果。"""

    requirement: JobRequirement  # 当前被评估的岗位要求
    status: RequirementAssessmentStatus  # 这条要求的证据覆盖状态
    supporting_evidence: list[Evidence]  # confirmed、verified 证据
    candidate_evidence: list[Evidence]  # 尚不能支撑结论的 candidate 证据


class ResumeSuggestionDraft(BaseModel):
    """保存等待用户审核的候选简历表述。"""

    text: str = Field(min_length=1)  # 等待用户审核的简历表述
    evidence_ids: list[str] = Field(min_length=1)  # 该表述引用的证据 ID
    status: Literal["candidate"] = "candidate"  # 不能自动成为正式内容


class JobAnalysisReport(BaseModel):
    """保存一份岗位的完整事实报告与候选简历建议。"""

    job: JobPosting  # 当前分析的结构化岗位
    assessments: list[RequirementAssessment]  # 每条要求的证据判断结果
    missing_required: list[JobRequirement]  # 没有可靠证据的硬性要求
    recommendation: ApplicationRecommendation  # 基于证据覆盖的投递建议
    resume_suggestions: list[ResumeSuggestionDraft] = Field(
        default_factory=list
    )  # 尚未确认的候选简历建议
