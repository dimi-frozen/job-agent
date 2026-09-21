"""岗位要求与个人证据的匹配领域模型。"""

from pydantic import BaseModel, Field

from typing import Literal

from job_agent.domain.jobs import JobRequirement
from job_agent.domain.models import Evidence


class RequirementEvidence(BaseModel):
    """保存一条岗位要求及为它检索到的个人证据。"""

    requirement: JobRequirement
    evidence: list[Evidence]

class CandidateEvidenceDraft(BaseModel):
    """保存根据用户回答整理出的、等待用户确认的候选证据。"""

    capability_name: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    source_quote: str = Field(min_length=1)
    status: Literal["candidate"] = "candidate"
