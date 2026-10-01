"""离线检查 Day 6 报告领域模型的基本约束。"""

from pydantic import ValidationError

from job_agent.domain.jobs import JobPosting, JobRequirement
from job_agent.domain.models import Evidence, EvidenceStatus
from job_agent.domain.reports import (
    ApplicationRecommendation,
    JobAnalysisReport,
    RequirementAssessment,
    RequirementAssessmentStatus,
    ResumeSuggestionDraft,
)


requirement = JobRequirement(
    text="熟悉 LangGraph",
    priority="required",
    source_quote="熟悉 LangGraph",
    evidence_query="LangGraph 项目经验",
)
job = JobPosting(requirements=[requirement])
evidence = Evidence(
    capability_id="capability-1",
    source_type="code",
    source_ref="src/job_agent/agent/graph.py",
    summary="使用 LangGraph 实现证据检查与条件路由",
    status=EvidenceStatus.VERIFIED,
)
assessment = RequirementAssessment(
    requirement=requirement,
    status=RequirementAssessmentStatus.SUPPORTED,
    supporting_evidence=[evidence],
    candidate_evidence=[],
)
report = JobAnalysisReport(
    job=job,
    assessments=[assessment],
    missing_required=[],
    recommendation=ApplicationRecommendation.READY_TO_APPLY,
)

assert report.resume_suggestions == []
assert report.assessments[0].supporting_evidence == [evidence]

try:
    ResumeSuggestionDraft(
        text="使用 LangGraph 构建证据驱动工作流",
        evidence_ids=[],
    )
except ValidationError:
    pass
else:
    raise AssertionError("没有引用证据的简历建议不应通过校验")

try:
    ResumeSuggestionDraft(
        text="使用 LangGraph 构建证据驱动工作流",
        evidence_ids=[evidence.id],
        status="confirmed",
    )
except ValidationError:
    pass
else:
    raise AssertionError("简历建议不能跳过用户审核直接变成 confirmed")

suggestion = ResumeSuggestionDraft(
    text="使用 LangGraph 构建证据驱动工作流",
    evidence_ids=[evidence.id],
)
report.resume_suggestions.append(suggestion)

another_report = JobAnalysisReport(
    job=job,
    assessments=[assessment],
    missing_required=[],
    recommendation=ApplicationRecommendation.READY_TO_APPLY,
)
assert report.resume_suggestions == [suggestion]
assert another_report.resume_suggestions == []

print("Day 6 report models passed.")
