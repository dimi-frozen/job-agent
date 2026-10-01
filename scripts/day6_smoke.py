"""离线验收 Day 6 事实报告与候选简历建议。"""

import json
from unittest.mock import Mock

from job_agent.domain.jobs import JobPosting, JobRequirement
from job_agent.domain.matching import RequirementEvidence
from job_agent.domain.models import Evidence, EvidenceStatus
from job_agent.domain.reports import (
    ApplicationRecommendation,
    RequirementAssessmentStatus,
)
from job_agent.services.job_reporting import build_job_analysis_report
from job_agent.services.resume_suggestions import (
    generate_resume_suggestions,
    parse_resume_suggestions,
)


def make_requirement(
    text: str,
    priority: str = "required",
) -> JobRequirement:
    """创建 smoke 场景使用的岗位要求。"""

    return JobRequirement(
        text=text,
        priority=priority,
        source_quote=text,
        evidence_query=f"{text}相关项目经验",
    )


def make_evidence(status: EvidenceStatus) -> Evidence:
    """创建指定验证状态的测试证据。"""

    return Evidence(
        capability_id="capability-1",
        source_type="code",
        source_ref="src/job_agent/agent/graph.py",
        summary="使用 LangGraph 实现证据检查与条件路由",
        status=status,
    )


def check_supported_required() -> None:
    """硬性要求有 verified 证据时允许投递。"""

    requirement = make_requirement("熟悉 LangGraph")
    evidence = make_evidence(EvidenceStatus.VERIFIED)
    job = JobPosting(requirements=[requirement])
    report = build_job_analysis_report(
        job,
        [RequirementEvidence(requirement=requirement, evidence=[evidence])],
    )

    assessment = report.assessments[0]
    assert assessment.status is RequirementAssessmentStatus.SUPPORTED
    assert assessment.supporting_evidence == [evidence]
    assert assessment.candidate_evidence == []
    assert report.missing_required == []
    assert report.recommendation is ApplicationRecommendation.READY_TO_APPLY


def check_candidate_only_required() -> None:
    """硬性要求只有 candidate 时先补充可靠证据。"""

    requirement = make_requirement("熟悉 LangGraph")
    evidence = make_evidence(EvidenceStatus.CANDIDATE)
    job = JobPosting(requirements=[requirement])
    report = build_job_analysis_report(
        job,
        [RequirementEvidence(requirement=requirement, evidence=[evidence])],
    )

    assessment = report.assessments[0]
    assert assessment.status is RequirementAssessmentStatus.CANDIDATE_ONLY
    assert assessment.supporting_evidence == []
    assert assessment.candidate_evidence == [evidence]
    assert report.missing_required == [requirement]
    assert (
        report.recommendation
        is ApplicationRecommendation.BUILD_EVIDENCE_FIRST
    )


def check_missing_preferred() -> None:
    """加分项没有证据时展示缺口，但不阻塞投递。"""

    requirement = make_requirement("了解 Docker", priority="preferred")
    rejected = make_evidence(EvidenceStatus.REJECTED)
    job = JobPosting(requirements=[requirement])
    report = build_job_analysis_report(
        job,
        [RequirementEvidence(requirement=requirement, evidence=[rejected])],
    )

    assessment = report.assessments[0]
    assert assessment.status is RequirementAssessmentStatus.MISSING
    assert assessment.supporting_evidence == []
    assert assessment.candidate_evidence == []
    assert report.missing_required == []
    assert report.recommendation is ApplicationRecommendation.READY_TO_APPLY


def check_incomplete_matches_rejected() -> None:
    """缺少要求匹配结果时不能错误地生成可投递结论。"""

    requirement = make_requirement("熟悉 Python")
    job = JobPosting(requirements=[requirement])

    try:
        build_job_analysis_report(job, [])
    except ValueError:
        pass
    else:
        raise AssertionError("匹配结果不完整时不应生成岗位报告")


def check_resume_suggestion_evidence_allowlist() -> None:
    """简历建议只能引用报告中的 confirmed 或 verified 证据。"""

    requirement = make_requirement("熟悉 LangGraph")
    verified = make_evidence(EvidenceStatus.VERIFIED)
    candidate = make_evidence(EvidenceStatus.CANDIDATE)
    job = JobPosting(
        title="AI 应用开发工程师",
        requirements=[requirement],
    )
    report = build_job_analysis_report(
        job,
        [
            RequirementEvidence(
                requirement=requirement,
                evidence=[verified, candidate],
            )
        ],
    )
    valid_payload = {
        "suggestions": [
            {
                "text": "使用 LangGraph 实现证据检查与条件路由",
                "evidence_ids": [verified.id],
                "status": "candidate",
            }
        ]
    }
    raw_json = json.dumps(valid_payload, ensure_ascii=False)
    client = Mock()
    client.generate_json.return_value = raw_json

    suggestions = generate_resume_suggestions(report, client)
    assert suggestions[0].evidence_ids == [verified.id]
    user_prompt = client.generate_json.call_args.kwargs["user_prompt"]
    assert verified.id in user_prompt
    assert candidate.id not in user_prompt

    invalid_payloads = [
        {
            "suggestions": [
                {
                    "text": "引用候选证据",
                    "evidence_ids": [candidate.id],
                    "status": "candidate",
                }
            ]
        },
        {
            "suggestions": [
                {
                    "text": "引用不存在的证据",
                    "evidence_ids": ["unknown-evidence-id"],
                    "status": "candidate",
                }
            ]
        },
    ]
    for invalid_payload in invalid_payloads:
        try:
            parse_resume_suggestions(
                json.dumps(invalid_payload, ensure_ascii=False),
                report,
            )
        except ValueError:
            pass
        else:
            raise AssertionError("非法 evidence_id 不应通过简历建议校验")


def check_no_reliable_evidence_skips_llm() -> None:
    """没有可靠证据时不调用模型生成简历建议。"""

    requirement = make_requirement("熟悉 LangGraph")
    candidate = make_evidence(EvidenceStatus.CANDIDATE)
    report = build_job_analysis_report(
        JobPosting(requirements=[requirement]),
        [RequirementEvidence(requirement=requirement, evidence=[candidate])],
    )
    client = Mock()

    assert generate_resume_suggestions(report, client) == []
    client.generate_json.assert_not_called()


if __name__ == "__main__":
    check_supported_required()
    check_candidate_only_required()
    check_missing_preferred()
    check_incomplete_matches_rejected()
    check_resume_suggestion_evidence_allowlist()
    check_no_reliable_evidence_skips_llm()
    print("Day 6 evidence-grounded report and resume suggestions passed.")
