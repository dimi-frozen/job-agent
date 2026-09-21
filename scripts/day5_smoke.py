"""离线验收 Day 5 的两次暂停、人工审核、持久化与重新分析。"""

from functools import partial
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from langgraph.types import Command

from day2_smoke import TestEmbeddingFunction
from job_agent.agent.graph import build_interactive_job_analysis_graph
from job_agent.domain.jobs import JobPosting, JobRequirement
from job_agent.domain.matching import CandidateEvidenceDraft
from job_agent.domain.models import EvidenceStatus, Profile
from job_agent.rag.evidence_index import EvidenceIndex
from job_agent.services.evidence_matching import match_job_requirements
from job_agent.services.evidence_persistence import persist_confirmed_evidence
from job_agent.storage.sqlite import (
    connect,
    initialize_schema,
    list_capabilities_by_profile,
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
    """创建两个验收场景共用的岗位要求、岗位和候选草稿。"""

    requirement = JobRequirement(
        text="熟悉 LangGraph",
        priority="required",
        source_quote="熟悉 LangGraph",
        evidence_query="LangGraph 工作流和条件路由经验",
    )
    job = JobPosting(requirements=[requirement])
    draft = CandidateEvidenceDraft(
        capability_name="LangGraph",
        summary="使用 LangGraph 实现证据检查与条件路由",
        source_quote=USER_ANSWER,
    )
    return requirement, job, draft


def check_approved_flow() -> None:
    """确认草稿后保存证据、更新索引并重新分析。"""

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
            draft_candidate = Mock(return_value=draft)
            match_requirements = partial(
                match_job_requirements,
                index=index,
                connection=connection,
            )
            persist_evidence = partial(
                persist_confirmed_evidence,
                connection=connection,
                index=index,
            )
            graph = build_interactive_job_analysis_graph(
                extract_job,
                match_requirements,
                draft_candidate,
                persist_evidence,
            )
            config = {
                "configurable": {
                    "thread_id": "day5-approved-flow",
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

            wrong_thread_state = graph.get_state(
                {
                    "configurable": {
                        "thread_id": "wrong-thread-id",
                    }
                }
            )
            assert wrong_thread_state.values == {}
            assert wrong_thread_state.next == ()

            second_result = graph.invoke(
                Command(resume=USER_ANSWER),
                config=config,
            )
            second_payload = second_result["__interrupt__"][0].value
            assert second_payload["kind"] == "candidate_evidence_review"
            assert second_payload["candidate_draft"] == draft.model_dump(
                mode="json"
            )

            final_state = graph.invoke(
                Command(resume=True),
                config=config,
            )
            assert final_state["candidate_approved"] is True
            assert final_state["status"] == "ready_for_analysis"
            draft_candidate.assert_called_once_with(requirement, USER_ANSWER)

            saved_evidence = load_evidence(
                connection,
                final_state["saved_evidence_id"],
            )
            assert saved_evidence is not None
            assert saved_evidence.status is EvidenceStatus.CONFIRMED
            assert index.query_evidence_ids(requirement.evidence_query)[0] == (
                saved_evidence.id
            )
            assert len(list_capabilities_by_profile(connection, profile.id)) == 1
            assert len(list_evidence_by_profile(connection, profile.id)) == 1

            repeated_evidence = persist_confirmed_evidence(
                profile.id,
                draft,
                connection,
                index,
            )
            assert repeated_evidence.id == saved_evidence.id
            assert len(list_capabilities_by_profile(connection, profile.id)) == 1
            assert len(list_evidence_by_profile(connection, profile.id)) == 1
        finally:
            if index is not None:
                index.close()
            connection.close()


def check_rejected_flow() -> None:
    """拒绝草稿后不创建能力、证据或索引记录。"""

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
            persist_evidence = Mock()
            graph = build_interactive_job_analysis_graph(
                Mock(return_value=job),
                partial(
                    match_job_requirements,
                    index=index,
                    connection=connection,
                ),
                Mock(return_value=draft),
                persist_evidence,
            )
            config = {
                "configurable": {
                    "thread_id": "day5-rejected-flow",
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
            final_state = graph.invoke(Command(resume=False), config=config)

            assert final_state["candidate_approved"] is False
            assert final_state["status"] == "needs_clarification"
            assert "saved_evidence_id" not in final_state
            persist_evidence.assert_not_called()
            assert list_capabilities_by_profile(connection, profile.id) == []
            assert list_evidence_by_profile(connection, profile.id) == []
            assert index.query_evidence_ids(requirement.evidence_query) == []
        finally:
            if index is not None:
                index.close()
            connection.close()


if __name__ == "__main__":
    check_approved_flow()
    check_rejected_flow()
    print("Day 5 human confirmation workflow passed.")
