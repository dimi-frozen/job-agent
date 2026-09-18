"""离线检查岗位要求与个人证据的关联流程。"""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, call

from job_agent.agent.graph import build_job_analysis_graph
from job_agent.agent.nodes import (
    check_evidence_node,
    extract_job_node,
    retrieve_evidence_node,
)
from job_agent.agent.state import JobAnalysisState
from job_agent.domain.jobs import JobPosting, JobRequirement
from job_agent.domain.matching import RequirementEvidence
from job_agent.domain.models import (
    Capability,
    Evidence,
    EvidenceStatus,
    Profile,
)
from job_agent.rag.evidence_index import EvidenceIndex
from job_agent.services.evidence_matching import match_job_requirements
from job_agent.storage.sqlite import (
    connect,
    initialize_schema,
    save_capability,
    save_evidence,
    save_profile,
)


def check_evidence_matching() -> None:
    """检查每条岗位要求都能得到独立、可追溯的证据列表。"""

    with TemporaryDirectory() as temporary_directory:
        connection = connect(Path(temporary_directory) / "day4.db")

        try:
            initialize_schema(connection)
            profile = Profile(name="张先生")
            capability = Capability(
                profile_id=profile.id,
                name="AI 应用开发",
            )
            verified = Evidence(
                capability_id=capability.id,
                source_type="code",
                summary="实现 Python 项目",
                status=EvidenceStatus.VERIFIED,
            )
            candidate = Evidence(
                capability_id=capability.id,
                source_type="conversation",
                summary="正在学习 RAG",
                status=EvidenceStatus.CANDIDATE,
            )
            rejected = Evidence(
                capability_id=capability.id,
                source_type="conversation",
                summary="已经拒绝的旧证据",
                status=EvidenceStatus.REJECTED,
            )

            save_profile(connection, profile)
            save_capability(connection, capability)
            for evidence in [verified, candidate, rejected]:
                save_evidence(connection, evidence)

            requirements = [
                JobRequirement(
                    text="熟悉 Python",
                    priority="required",
                    source_quote="熟悉 Python",
                    evidence_query="Python 项目经验",
                ),
                JobRequirement(
                    text="具有 RAG 经验",
                    priority="required",
                    source_quote="具有 RAG 经验",
                    evidence_query="RAG 项目经验",
                ),
            ]
            job = JobPosting(requirements=requirements)
            index = Mock(spec=EvidenceIndex)
            index.query_evidence_ids.side_effect = [
                [verified.id, "missing-id", rejected.id],
                [candidate.id],
            ]

            matches = match_job_requirements(job, index, connection)

            assert len(matches) == 2
            assert matches[0].requirement == requirements[0]
            assert matches[0].evidence == [verified]
            assert matches[1].requirement == requirements[1]
            assert matches[1].evidence == [candidate]
            assert index.query_evidence_ids.call_args_list == [
                call("Python 项目经验", limit=3),
                call("RAG 项目经验", limit=3),
            ]
        finally:
            connection.close()


def check_nodes() -> None:
    """检查三个节点只读取所需字段并返回部分 State 更新。"""

    requirements = [
        JobRequirement(
            text="熟悉 Python",
            priority="required",
            source_quote="熟悉 Python",
            evidence_query="Python 项目经验",
        ),
        JobRequirement(
            text="具有 RAG 经验",
            priority="required",
            source_quote="具有 RAG 经验",
            evidence_query="RAG 项目经验",
        ),
        JobRequirement(
            text="了解 LangGraph",
            priority="preferred",
            source_quote="了解 LangGraph",
            evidence_query="LangGraph 使用经验",
        ),
    ]
    job = JobPosting(requirements=requirements)
    verified = Evidence(
        capability_id="cap-1",
        source_type="code",
        summary="完成 Python 项目",
        status=EvidenceStatus.VERIFIED,
    )
    candidate = Evidence(
        capability_id="cap-2",
        source_type="conversation",
        summary="正在学习 RAG",
        status=EvidenceStatus.CANDIDATE,
    )
    matches = [
        RequirementEvidence(requirement=requirements[0], evidence=[verified]),
        RequirementEvidence(requirement=requirements[1], evidence=[candidate]),
        RequirementEvidence(requirement=requirements[2], evidence=[]),
    ]

    extract_job = Mock(return_value=job)
    initial_state: JobAnalysisState = {
        "profile_id": "profile-1",
        "jd_text": "一段测试 JD",
    }
    extract_update = extract_job_node(initial_state, extract_job)
    assert extract_update == {"job": job}
    assert "job" not in initial_state
    extract_job.assert_called_once_with("一段测试 JD")

    match_requirements = Mock(return_value=matches)
    retrieve_update = retrieve_evidence_node(
        {**initial_state, **extract_update},
        match_requirements,
    )
    assert retrieve_update == {"requirement_evidence": matches}
    match_requirements.assert_called_once_with(job)

    check_update = check_evidence_node(
        {**initial_state, **extract_update, **retrieve_update}
    )
    assert check_update == {"missing_required": [requirements[1]]}


def run_graph_scenario(
    requirement: JobRequirement,
    evidence: list[Evidence],
    expected_status: str,
    expected_missing: list[JobRequirement],
) -> None:
    """使用假的提取和检索依赖执行一个完整图场景。"""

    job = JobPosting(requirements=[requirement])
    matches = [
        RequirementEvidence(
            requirement=requirement,
            evidence=evidence,
        )
    ]
    extract_job = Mock(return_value=job)
    match_requirements = Mock(return_value=matches)
    graph = build_job_analysis_graph(extract_job, match_requirements)

    result = graph.invoke(
        {
            "profile_id": "profile-1",
            "jd_text": "一段测试 JD",
        }
    )

    assert result["job"] == job
    assert result["requirement_evidence"] == matches
    assert result["missing_required"] == expected_missing
    assert result["status"] == expected_status
    extract_job.assert_called_once_with("一段测试 JD")
    match_requirements.assert_called_once_with(job)


def check_graph_routes() -> None:
    """检查可靠、候选和加分项三种证据分支。"""

    required = JobRequirement(
        text="熟悉 Python",
        priority="required",
        source_quote="熟悉 Python",
        evidence_query="Python 项目经验",
    )
    preferred = JobRequirement(
        text="了解 LangGraph",
        priority="preferred",
        source_quote="了解 LangGraph",
        evidence_query="LangGraph 使用经验",
    )
    verified = Evidence(
        capability_id="cap-1",
        source_type="code",
        summary="完成 Python 项目",
        status=EvidenceStatus.VERIFIED,
    )
    candidate = Evidence(
        capability_id="cap-1",
        source_type="conversation",
        summary="正在学习 Python",
        status=EvidenceStatus.CANDIDATE,
    )

    run_graph_scenario(
        required,
        [verified],
        "ready_for_analysis",
        [],
    )
    run_graph_scenario(
        required,
        [candidate],
        "needs_clarification",
        [required],
    )
    run_graph_scenario(
        preferred,
        [],
        "ready_for_analysis",
        [],
    )


if __name__ == "__main__":
    check_evidence_matching()
    check_nodes()
    check_graph_routes()
    print("Day 4 evidence matching, nodes, and graph routes passed.")
