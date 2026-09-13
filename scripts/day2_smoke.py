"""检查完整档案读取与 Chroma 可追溯检索链路。"""

import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from chromadb.api.types import Documents, Embeddings, EmbeddingFunction

from job_agent.domain.models import (
    Capability,
    CapabilityLevel,
    Evidence,
    EvidenceStatus,
    Profile,
)
from job_agent.rag.evidence_index import EvidenceIndex
from job_agent.storage.sqlite import (
    connect,
    initialize_schema,
    list_capabilities_by_profile,
    list_evidence_by_profile,
    load_evidence,
    save_capability,
    save_evidence,
    save_profile,
)


class TestEmbeddingFunction(EmbeddingFunction[Documents]):
    """只为 smoke test 提供可预测的三维测试向量。"""

    def __init__(self) -> None:
        pass

    def __call__(self, input: Documents) -> Embeddings:
        embeddings = []

        for text in input:
            normalized_text = text.lower()
            if any(
                keyword in normalized_text
                for keyword in ["agent", "langgraph", "工作流", "状态图", "条件路由"]
            ):
                vector = [1.0, 0.0, 0.0]
            elif any(
                keyword in normalized_text
                for keyword in ["rag", "切块", "向量", "检索", "重排"]
            ):
                vector = [0.0, 1.0, 0.0]
            else:
                vector = [0.0, 0.0, 1.0]

            embeddings.append(np.array(vector, dtype=np.float32))

        return embeddings


def check_day2_flow() -> None:
    with TemporaryDirectory() as temporary_directory:
        temporary_path = Path(temporary_directory)
        index_directory = temporary_path / "chroma"
        connection = connect(temporary_path / "day2.db")
        index: EvidenceIndex | None = None

        try:
            initialize_schema(connection)

            profile = Profile(
                name="张先生",
                target_roles=["AI 应用开发"],
            )
            rag = Capability(
                profile_id=profile.id,
                name="RAG",
                level=CapabilityLevel.PROJECT_VERIFIED,
            )
            langgraph = Capability(
                profile_id=profile.id,
                name="LangGraph",
                level=CapabilityLevel.INDEPENDENT,
            )
            evidence_items = [
                Evidence(
                    capability_id=rag.id,
                    source_type="code",
                    source_ref="rag/documents.py",
                    summary="实现文档切块与向量检索",
                    status=EvidenceStatus.VERIFIED,
                ),
                Evidence(
                    capability_id=rag.id,
                    source_type="conversation",
                    summary="学习重排模型",
                    status=EvidenceStatus.CANDIDATE,
                ),
                Evidence(
                    capability_id=langgraph.id,
                    source_type="code",
                    source_ref="agent/chat_graph.py",
                    summary="实现状态图和条件路由",
                    status=EvidenceStatus.CONFIRMED,
                ),
            ]

            save_profile(connection, profile)
            save_capability(connection, rag)
            save_capability(connection, langgraph)
            for evidence in evidence_items:
                save_evidence(connection, evidence)

            assert len(list_capabilities_by_profile(connection, profile.id)) == 2
            assert len(list_evidence_by_profile(connection, profile.id)) == 3

            index = EvidenceIndex(
                index_directory,
                embedding_function=TestEmbeddingFunction(),
            )
            for evidence in evidence_items:
                index.upsert(evidence)

            result_ids = index.query_evidence_ids("是否做过 Agent 工作流？")
            assert result_ids[0] == evidence_items[2].id

            retrieved_evidence = load_evidence(connection, result_ids[0])
            assert retrieved_evidence == evidence_items[2]
            assert retrieved_evidence.status is EvidenceStatus.CONFIRMED

            rejected_evidence = Evidence(
                capability_id=rag.id,
                source_type="conversation",
                summary="一条已经被用户拒绝的候选经历",
                status=EvidenceStatus.REJECTED,
            )
            index.upsert(rejected_evidence)

            indexed_ids = index.query_evidence_ids("任意查询", limit=10)
            expected_ids = {evidence.id for evidence in evidence_items}
            assert rejected_evidence.id not in indexed_ids
            assert set(indexed_ids).issubset(expected_ids)
            candidate_evidence = evidence_items[1]
            assert candidate_evidence.status is EvidenceStatus.CANDIDATE
            assert candidate_evidence.id in indexed_ids

            unrelated_ids = index.query_evidence_ids("烹饪与摄影", limit=10)
            assert set(unrelated_ids).issubset(expected_ids)
            assert all(
                load_evidence(connection, evidence_id) is not None
                for evidence_id in unrelated_ids
            )

            index.close()
            index = None
            shutil.rmtree(index_directory)
            assert not index_directory.exists()

            index = EvidenceIndex(
                index_directory,
                embedding_function=TestEmbeddingFunction(),
            )
            for evidence in list_evidence_by_profile(connection, profile.id):
                index.upsert(evidence)

            rebuilt_result_ids = index.query_evidence_ids(
                "是否做过 Agent 工作流？"
            )
            assert rebuilt_result_ids[0] == evidence_items[2].id
        finally:
            if index is not None:
                index.close()
            connection.close()


if __name__ == "__main__":
    check_day2_flow()
    print("Day 2 traceable evidence retrieval passed.")
