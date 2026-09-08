"""核心领域模型。

Day 1 练习：实现 ``docs/day-01.md`` 中说明的枚举和 Pydantic 模型。
这个模块只负责描述数据，不依赖 SQLite 或 LangGraph。
"""

from enum import StrEnum

from pydantic import BaseModel, Field

from uuid import uuid4

from datetime import datetime, timezone


class CapabilityLevel(StrEnum):
    """表示现有证据能够在多大程度上证明一项能力。"""

    AWARE = "aware" #了解过，但还不会实际完成
    ASSISTED = "assisted" #帮助完成，在 AI、教程或他人帮助下能完成
    INDEPENDENT = "independent" #可以独立完成
    PROJECT_VERIFIED = "project_verified" #已经在实际项目中得到验证


class EvidenceStatus(StrEnum):
    """表示一条证据目前处于哪个验证阶段。"""

    CANDIDATE = "candidate" #系统刚发现的候选证据
    CONFIRMED = "confirmed" #已经由你确认
    VERIFIED = "verified" #经过代码、运行结果等进一步验证
    REJECTED = "rejected" #被拒绝确认不能作为证据


class Profile(BaseModel):
    """保存用户的基本身份信息和目标岗位。"""

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(min_length=1) # 用户名
    target_roles: list[str] = Field(default_factory=list) # 目标岗位
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc)) # 创建时间
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc)) # 更新时间


class Capability(BaseModel):
    """保存某份用户档案中一项能力的当前等级。"""

    id: str = Field(default_factory=lambda: str(uuid4())) # 能力 ID
    profile_id: str # 用户档案 ID
    name: str = Field(min_length=1) # 能力名称
    level: CapabilityLevel = Field(default=CapabilityLevel.AWARE)# 当前等级
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc)) # 更新时间


class Evidence(BaseModel):
    """保存一条有来源、可以用来证明某项能力的陈述。"""

    id: str = Field(default_factory=lambda: str(uuid4())) # 证据 ID
    capability_id: str # 能力 ID
    source_type: str # 来源类型
    source_ref: str | None = None # 来源引用
    summary: str = Field(min_length=1) # 概要
    status: EvidenceStatus = Field(default=EvidenceStatus.CANDIDATE) # 当前状态
    created_at: datetime = Field(default_factory= lambda: datetime.now(timezone.utc)) # 创建时间

