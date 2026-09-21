"""把用户确认的候选草稿保存为可检索的正式证据。"""

import sqlite3
from uuid import NAMESPACE_URL, uuid5

from job_agent.domain.matching import CandidateEvidenceDraft
from job_agent.domain.models import Capability, Evidence, EvidenceStatus
from job_agent.rag.evidence_index import EvidenceIndex
from job_agent.storage.sqlite import (
    list_capabilities_by_profile,
    load_evidence,
    save_capability,
    save_evidence,
)


def _normalize_capability_name(name: str) -> str:
    """去掉首尾和重复空白，得到用于匹配与保存的能力名称。"""

    normalized = " ".join(name.split())
    if not normalized:
        raise ValueError("能力名称不能为空")
    return normalized


def _find_capability(
    connection: sqlite3.Connection,
    profile_id: str,
    capability_name: str,
) -> Capability | None:
    """在一份档案中按规范化名称查找已有能力。"""

    expected_name = capability_name.casefold()
    for capability in list_capabilities_by_profile(connection, profile_id):
        existing_name = _normalize_capability_name(capability.name).casefold()
        if existing_name == expected_name:
            return capability

    return None


def _confirmed_evidence_id(
    profile_id: str,
    draft: CandidateEvidenceDraft,
) -> str:
    """根据档案与草稿内容生成可重复计算的证据 ID。"""

    identity = "\n".join(
        [
            profile_id,
            _normalize_capability_name(draft.capability_name).casefold(),
            draft.summary.strip(),
            draft.source_quote.strip(),
        ]
    )
    return str(uuid5(NAMESPACE_URL, identity))


def persist_confirmed_evidence(
    profile_id: str,
    draft: CandidateEvidenceDraft,
    connection: sqlite3.Connection,
    index: EvidenceIndex,
) -> Evidence:
    """查找或创建能力，并把确认后的草稿保存为 confirmed 证据。"""

    capability_name = _normalize_capability_name(draft.capability_name)
    capability = _find_capability(
        connection,
        profile_id,
        capability_name,
    )
    if capability is None:
        capability = Capability(
            profile_id=profile_id,
            name=capability_name,
        )
        save_capability(connection, capability)

    evidence_id = _confirmed_evidence_id(profile_id, draft)
    existing_evidence = load_evidence(connection, evidence_id)
    if existing_evidence is not None:
        index.upsert(existing_evidence)
        return existing_evidence

    evidence = Evidence(
        id=evidence_id,
        capability_id=capability.id,
        source_type="conversation",
        source_ref=draft.source_quote,
        summary=draft.summary,
        status=EvidenceStatus.CONFIRMED,
    )
    save_evidence(connection, evidence)
    index.upsert(evidence)
    return evidence
