"""离线验收 Day 7 的完整岗位分析工作流。"""

from functools import partial
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from langgraph.types import Command

from day2_smoke import TestEmbeddingFunction
from job_agent.agent.graph import build_complete_job_analysis_graph
from job_agent.domain.jobs import JobPosting, JobRequirement
from job_agent.domain.matching import CandidateEvidenceDraft, RequirementEvidence
from job_agent.domain.models import Evidence, EvidenceStatus, Profile
from job_agent.domain.reports import (
    ApplicationRecommendation,
    RequirementAssessmentStatus,
    ResumeSuggestionDraft,
)
from job_agent.rag.evidence_index import EvidenceIndex
from job_agent.services.evidence_matching import match_job_requirements
from job_agent.services.evidence_persistence import persist_confirmed_evidence
from job_agent.services.job_reporting import build_job_analysis_report
from job_agent.storage.sqlite import (
    connect,
    initialize_schema,
    list_evidence_by_profile,
    load_evidence,
    save_profile,
)


USER_ANSWER = "我使用 LangGraph 实现了证据检查与条件路由"


def build_test_data() -> tuple[
    JobRequirement,
    JobPosting,
    CandidateEvidenceDraft,
]:
    """创建三条验收路线共用的岗位和候选证据草稿。"""

    requirement = JobRequirement(
        text="熟悉 LangGraph",
        priority="required",
        source_quote="熟悉 LangGraph",
        evidence_query="LangGraph 工作流和条件路由经验",
    )
    job = JobPosting(
        title="AI 应用开发工程师",
        company="测试公司",
        requirements=[requirement],
    )
    draft = CandidateEvidenceDraft(
        capability_name="LangGraph",
        summary="使用 LangGraph 实现证据检查与条件路由",
        source_quote=USER_ANSWER,
    )
    return requirement, job, draft


def suggestion_from_report(report):
    """根据报告中的第一条可靠证据生成固定候选建议。"""

    evidence = report.assessments[0].supporting_evidence[0]
    return [
        ResumeSuggestionDraft(
            text="使用 LangGraph 实现证据检查与条件路由",
            evidence_ids=[evidence.id],
        )
    ]


def check_ready_flow() -> None:
    """已有可靠证据时直接生成报告和候选简历建议。"""

    with TemporaryDirectory() as temporary_directory:
        temporary_path = Path(temporary_directory)
        connection = connect(temporary_path / "ready.db")
        index: EvidenceIndex | None = None

        try:
            initialize_schema(connection)
            profile = Profile(name="张先生")
            save_profile(connection, profile)
            requirement, job, draft = build_test_data()

            index = EvidenceIndex(
                temporary_path / "ready-chroma",
                embedding_function=TestEmbeddingFunction(),
            )
            existing_evidence = persist_confirmed_evidence(
                profile.id,
                draft,
                connection,
                index,
            )

            extract_job = Mock(return_value=job)
            match_requirements = Mock(
                side_effect=partial(
                    match_job_requirements,
                    index=index,
                    connection=connection,
                )
            )
            draft_candidate = Mock()
            persist_evidence = Mock()
            refine_evidence = Mock(side_effect=lambda matches: matches)
            build_report = Mock(wraps=build_job_analysis_report)
            generate_suggestions = Mock(side_effect=suggestion_from_report)
            graph = build_complete_job_analysis_graph(
                extract_job,
                match_requirements,
                refine_evidence,
                draft_candidate,
                persist_evidence,
                build_report,
                generate_suggestions,
            )

            final_state = graph.invoke(
                {
                    "profile_id": profile.id,
                    "jd_text": "要求熟悉 LangGraph",
                },
                config={"configurable": {"thread_id": "day7-ready"}},
            )

            report = final_state["analysis_report"]
            assert "__interrupt__" not in final_state
            assert final_state["status"] == "ready_for_analysis"
            assert report.recommendation is ApplicationRecommendation.READY_TO_APPLY
            assert report.assessments[0].status is (
                RequirementAssessmentStatus.SUPPORTED
            )
            assert report.assessments[0].supporting_evidence == [
                existing_evidence
            ]
            assert report.resume_suggestions[0].evidence_ids == [
                existing_evidence.id
            ]
            extract_job.assert_called_once_with("要求熟悉 LangGraph")
            match_requirements.assert_called_once_with(job)
            refine_evidence.assert_called_once()
            draft_candidate.assert_not_called()
            persist_evidence.assert_not_called()
            build_report.assert_called_once()
            generate_suggestions.assert_called_once()
        finally:
            if index is not None:
                index.close()
            connection.close()


def check_approved_flow() -> None:
    """补充并确认后，保存证据、重新检索并生成最终报告。"""

    with TemporaryDirectory() as temporary_directory:
        temporary_path = Path(temporary_directory)
        connection = connect(temporary_path / "approved.db")
        index: EvidenceIndex | None = None

        try:
            initialize_schema(connection)
            profile = Profile(name="张先生")
            save_profile(connection, profile)
            requirement, job, draft = build_test_data()

            index = EvidenceIndex(
                temporary_path / "approved-chroma",
                embedding_function=TestEmbeddingFunction(),
            )
            extract_job = Mock(return_value=job)
            match_requirements = Mock(
                side_effect=partial(
                    match_job_requirements,
                    index=index,
                    connection=connection,
                )
            )
            draft_candidate = Mock(return_value=draft)
            refine_evidence = Mock(side_effect=lambda matches: matches)
            persist_evidence = Mock(
                side_effect=partial(
                    persist_confirmed_evidence,
                    connection=connection,
                    index=index,
                )
            )
            build_report = Mock(wraps=build_job_analysis_report)
            generate_suggestions = Mock(side_effect=suggestion_from_report)
            graph = build_complete_job_analysis_graph(
                extract_job,
                match_requirements,
                refine_evidence,
                draft_candidate,
                persist_evidence,
                build_report,
                generate_suggestions,
            )
            config = {
                "configurable": {
                    "thread_id": "day7-approved",
                }
            }

            first_result = graph.invoke(
                {
                    "profile_id": profile.id,
                    "jd_text": "要求熟悉 LangGraph",
                },
                config=config,
            )
            first_payload = first_result["__interrupt__"][0].value
            assert first_payload["kind"] == "evidence_clarification"
            assert first_payload["requirement"] == requirement.text

            second_result = graph.invoke(
                Command(resume=USER_ANSWER),
                config=config,
            )
            second_payload = second_result["__interrupt__"][0].value
            assert second_payload["kind"] == "candidate_evidence_review"

            final_state = graph.invoke(
                Command(resume=True),
                config=config,
            )

            saved_evidence = load_evidence(
                connection,
                final_state["saved_evidence_id"],
            )
            report = final_state["analysis_report"]
            report_evidence = report.assessments[0].supporting_evidence[0]

            assert saved_evidence is not None
            assert saved_evidence.status is EvidenceStatus.CONFIRMED
            assert final_state["status"] == "ready_for_analysis"
            assert report_evidence == saved_evidence
            assert report.resume_suggestions[0].evidence_ids == [
                saved_evidence.id
            ]
            assert match_requirements.call_count == 2
            assert refine_evidence.call_count == 2
            draft_candidate.assert_called_once_with(requirement, USER_ANSWER)
            persist_evidence.assert_called_once_with(profile.id, draft)
            build_report.assert_called_once()
            generate_suggestions.assert_called_once()
            assert len(list_evidence_by_profile(connection, profile.id)) == 1
        finally:
            if index is not None:
                index.close()
            connection.close()


def check_rejected_flow() -> None:
    """拒绝候选证据后只生成缺口报告。"""

    with TemporaryDirectory() as temporary_directory:
        temporary_path = Path(temporary_directory)
        connection = connect(temporary_path / "rejected.db")
        index: EvidenceIndex | None = None

        try:
            initialize_schema(connection)
            profile = Profile(name="张先生")
            save_profile(connection, profile)
            requirement, job, draft = build_test_data()

            index = EvidenceIndex(
                temporary_path / "rejected-chroma",
                embedding_function=TestEmbeddingFunction(),
            )
            match_requirements = Mock(
                side_effect=partial(
                    match_job_requirements,
                    index=index,
                    connection=connection,
                )
            )
            draft_candidate = Mock(return_value=draft)
            refine_evidence = Mock(side_effect=lambda matches: matches)
            persist_evidence = Mock()
            build_report = Mock(wraps=build_job_analysis_report)
            generate_suggestions = Mock(side_effect=suggestion_from_report)
            graph = build_complete_job_analysis_graph(
                Mock(return_value=job),
                match_requirements,
                refine_evidence,
                draft_candidate,
                persist_evidence,
                build_report,
                generate_suggestions,
            )
            config = {
                "configurable": {
                    "thread_id": "day7-rejected",
                }
            }

            graph.invoke(
                {
                    "profile_id": profile.id,
                    "jd_text": "要求熟悉 LangGraph",
                },
                config=config,
            )
            graph.invoke(Command(resume=USER_ANSWER), config=config)
            final_state = graph.invoke(
                Command(resume=False),
                config=config,
            )

            report = final_state["analysis_report"]
            assert final_state["status"] == "needs_clarification"
            assert report.recommendation is (
                ApplicationRecommendation.BUILD_EVIDENCE_FIRST
            )
            assert report.missing_required == [requirement]
            assert report.resume_suggestions == []
            assert match_requirements.call_count == 1
            assert refine_evidence.call_count == 1
            draft_candidate.assert_called_once_with(requirement, USER_ANSWER)
            persist_evidence.assert_not_called()
            build_report.assert_called_once()
            generate_suggestions.assert_not_called()
            assert list_evidence_by_profile(connection, profile.id) == []
        finally:
            if index is not None:
                index.close()
            connection.close()


def check_confirmed_but_insufficient_flow() -> None:
    """确认后的经历仍不满足要求时生成缺口报告，不重复追问。"""

    requirement, job, draft = build_test_data()
    saved_evidence = Evidence(
        capability_id="capability-1",
        source_type="conversation",
        source_ref=USER_ANSWER,
        summary=draft.summary,
        status=EvidenceStatus.CONFIRMED,
    )
    match_requirements = Mock(
        side_effect=[
            [RequirementEvidence(requirement=requirement, evidence=[])],
            [
                RequirementEvidence(
                    requirement=requirement,
                    evidence=[saved_evidence],
                )
            ],
        ]
    )
    refine_evidence = Mock(
        side_effect=lambda matches: [
            RequirementEvidence(
                requirement=match.requirement,
                evidence=[],
            )
            for match in matches
        ]
    )
    persist_evidence = Mock(return_value=saved_evidence)
    generate_suggestions = Mock()
    graph = build_complete_job_analysis_graph(
        Mock(return_value=job),
        match_requirements,
        refine_evidence,
        Mock(return_value=draft),
        persist_evidence,
        build_job_analysis_report,
        generate_suggestions,
    )
    config = {
        "configurable": {
            "thread_id": "day7-confirmed-but-insufficient",
        }
    }

    graph.invoke(
        {
            "profile_id": "profile-1",
            "jd_text": "要求熟悉 LangGraph",
        },
        config=config,
    )
    graph.invoke(Command(resume=USER_ANSWER), config=config)
    final_state = graph.invoke(Command(resume=True), config=config)

    report = final_state["analysis_report"]
    assert "__interrupt__" not in final_state
    assert final_state["status"] == "needs_clarification"
    assert final_state["clarified_requirements"] == [requirement.text]
    assert report.missing_required == [requirement]
    assert match_requirements.call_count == 2
    assert refine_evidence.call_count == 2
    persist_evidence.assert_called_once()
    generate_suggestions.assert_not_called()


if __name__ == "__main__":
    check_ready_flow()
    check_approved_flow()
    check_rejected_flow()
    check_confirmed_but_insufficient_flow()
    print("Day 7 complete workflow passed.")
