"""使用真实 DeepSeek 调用人工检查 Day 6 候选简历建议。"""

from job_agent.domain.jobs import JobPosting, JobRequirement
from job_agent.domain.matching import RequirementEvidence
from job_agent.domain.models import Evidence, EvidenceStatus
from job_agent.llm.client import DeepSeekClient
from job_agent.services.job_reporting import build_job_analysis_report
from job_agent.services.resume_suggestions import generate_resume_suggestions


def main() -> None:
    """根据一条真实项目证据生成候选简历表述。"""

    requirement = JobRequirement(
        text="具备 LangGraph 工作流开发经验",
        priority="required",
        source_quote="具备 LangGraph 工作流开发经验",
        evidence_query="LangGraph 工作流开发项目经验",
    )
    job = JobPosting(
        title="AI 应用开发工程师",
        requirements=[requirement],
    )
    evidence = Evidence(
        capability_id="live-check-langgraph",
        source_type="code",
        source_ref="scripts/day5_smoke.py",
        summary=(
            "使用 LangGraph 实现了两次人工中断、候选证据确认、"
            "SQLite 持久化、Chroma 索引更新和重新分析闭环"
        ),
        status=EvidenceStatus.VERIFIED,
    )
    report = build_job_analysis_report(
        job,
        [
            RequirementEvidence(
                requirement=requirement,
                evidence=[evidence],
            )
        ],
    )
    suggestions = generate_resume_suggestions(report, DeepSeekClient())

    print(f"允许引用的 evidence_id：{evidence.id}")
    for index, suggestion in enumerate(suggestions, start=1):
        print(f"候选建议 {index}：{suggestion.text}")
        print(f"引用证据：{suggestion.evidence_ids}")
        print(f"状态：{suggestion.status}")


if __name__ == "__main__":
    main()
