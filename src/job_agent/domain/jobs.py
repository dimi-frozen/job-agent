"""岗位信息及岗位要求的领域模型。"""

from enum import StrEnum

from pydantic import BaseModel, Field


class RequirementPriority(StrEnum):
    """表示一项岗位要求是硬性要求还是加分项。"""

    REQUIRED = "required"  # 必须项
    PREFERRED = "preferred"  # 加分项


class JobRequirement(BaseModel):
    """保存一项从招聘原文中提取出的岗位要求。"""

    text: str = Field(min_length=1)  # 规范化后的岗位要求
    priority: RequirementPriority
    source_quote: str = Field(min_length=1)  # 能在原始 JD 中找到的原文依据
    evidence_query: str = Field(min_length=1)  # 用于检索个人能力证据的查询语句


class JobPosting(BaseModel):
    """保存一份岗位及其结构化要求。"""

    title: str | None = None
    company: str | None = None
    requirements: list[JobRequirement] = Field(min_length=1)
