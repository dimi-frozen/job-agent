"""使用 Chroma 建立可重建的证据检索索引。"""

from pathlib import Path

import chromadb
from chromadb.api.types import Documents, EmbeddingFunction

from job_agent.domain.models import Evidence, EvidenceStatus


COLLECTION_NAME = "evidence"


class EvidenceIndex:
    """写入证据索引，并根据查询返回相关的 evidence_id。"""

    def __init__(
        self,
        directory: Path,
        embedding_function: EmbeddingFunction[Documents] | None = None,
    ) -> None:
        self._client = chromadb.PersistentClient(path=str(directory))

        if embedding_function is None:
            self._collection = self._client.get_or_create_collection(
                name=COLLECTION_NAME,
            )
        else:
            self._collection = self._client.get_or_create_collection(
                name=COLLECTION_NAME,
                embedding_function=embedding_function,
            )

    @staticmethod
    def _document(evidence: Evidence) -> str:
        return f"来源类型：{evidence.source_type}\n证据：{evidence.summary}"

    def upsert(self, evidence: Evidence) -> None:
        """新增或更新一条证据；被拒绝的证据不进入索引。"""

        if evidence.status is EvidenceStatus.REJECTED:
            self._collection.delete(ids=[evidence.id])
            return

        self._collection.upsert(
            ids=[evidence.id],
            documents=[self._document(evidence)],
            metadatas=[
                {
                    "evidence_id": evidence.id,
                    "capability_id": evidence.capability_id,
                    "source_type": evidence.source_type,
                    "source_ref": evidence.source_ref or "",
                    "status": evidence.status.value,
                }
            ],
        )

    def query_evidence_ids(
        self,
        query: str,
        limit: int = 3,
    ) -> list[str]:
        """根据自然语言查询返回最相关的证据 ID。"""

        if not query.strip() or limit <= 0 or self._collection.count() == 0:
            return []

        result = self._collection.query(
            query_texts=[query],
            n_results=limit,
            include=[],
        )
        result_ids = result["ids"]
        return result_ids[0] if result_ids else []

    def close(self) -> None:
        """释放 Chroma 持有的本地文件资源。"""

        self._client.close()
