"""把岗位要求与 SQLite 中的个人证据关联起来。"""

import sqlite3

from job_agent.domain.jobs import JobPosting
from job_agent.domain.matching import RequirementEvidence
from job_agent.domain.models import EvidenceStatus
from job_agent.rag.evidence_index import EvidenceIndex
from job_agent.storage.sqlite import load_evidence


def match_job_requirements(
    job: JobPosting,
    index: EvidenceIndex,
    connection: sqlite3.Connection,
    limit: int = 3,
) -> list[RequirementEvidence]:
    """为岗位中的每条要求检索并加载个人证据。"""

    matches: list[RequirementEvidence] = []

    for requirement in job.requirements:
        evidence_ids = index.query_evidence_ids(
            requirement.evidence_query,
            limit=limit,
        )
        evidence_items = []

        for evidence_id in evidence_ids:
            evidence = load_evidence(connection, evidence_id)
            if evidence is None or evidence.status is EvidenceStatus.REJECTED:
                continue

            evidence_items.append(evidence)

        matches.append(
            RequirementEvidence(
                requirement=requirement,
                evidence=evidence_items,
            )
        )

    return matches
