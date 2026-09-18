"""岗位要求与个人证据的匹配领域模型。"""

from pydantic import BaseModel

from job_agent.domain.jobs import JobRequirement
from job_agent.domain.models import Evidence


class RequirementEvidence(BaseModel):
    """保存一条岗位要求及为它检索到的个人证据。"""

    requirement: JobRequirement
    evidence: list[Evidence]
