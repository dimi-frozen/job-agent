"""离线验收岗位要求与候选证据的严格核对服务。"""

import json
from unittest.mock import Mock

from job_agent.domain.jobs import JobRequirement
from job_agent.domain.matching import RequirementEvidence
from job_agent.domain.models import Evidence, EvidenceStatus
from job_agent.services.evidence_refinement import (
    parse_evidence_refinement,
    refine_requirement_evidence,
)


def build_matches() -> tuple[list[RequirementEvidence], Evidence]:
    """创建一条只支持 Agent 经历、不支持精通语言的证据。"""

    programming_requirement = JobRequirement(
        text="精通至少一门主流编程语言",
        priority="required",
        source_quote="精通至少一门主流编程语言",
        evidence_query="主流编程语言项目经验",
    )
    agent_requirement = JobRequirement(
        text="使用过 Agent 或 LLM 相关技术",
        priority="preferred",
        source_quote="使用过 Agent 或 LLM 相关技术",
        evidence_query="Agent LLM 项目经验",
    )
    evidence = Evidence(
        capability_id="capability-1",
        source_type="conversation",
        source_ref=(
            "做过 Java 后端开发，也用 Python 编写过 Agent 项目，"
            "但两种语言都不算精通。"
        ),
        summary="做过 Java 后端开发和 Python Agent 项目",
        status=EvidenceStatus.CONFIRMED,
    )
    return (
        [
            RequirementEvidence(
                requirement=programming_requirement,
                evidence=[evidence],
            ),
            RequirementEvidence(
                requirement=agent_requirement,
                evidence=[evidence],
            ),
        ],
        evidence,
    )


def check_strict_selection() -> None:
    """同一条证据只能进入它能够直接支撑的岗位要求。"""

    matches, evidence = build_matches()
    client = Mock()
    client.generate_json.return_value = json.dumps(
        {
            "selections": [
                {
                    "requirement_index": 0,
                    "evidence_ids": [evidence.id],
                },
                {
                    "requirement_index": 1,
                    "evidence_ids": [evidence.id],
                },
            ]
        }
    )

    refined = refine_requirement_evidence(matches, client)

    # 即使模型选中，confirmed 证据也不能支撑“精通”这类强程度要求。
    assert refined[0].evidence == []
    assert refined[1].evidence == [evidence]
    call = client.generate_json.call_args
    assert evidence.id in call.kwargs["user_prompt"]
    assert evidence.source_ref in call.kwargs["user_prompt"]


def check_invalid_id_rejected() -> None:
    """模型不能返回 Chroma 未检索到的证据 ID。"""

    matches, _ = build_matches()
    raw_json = json.dumps(
        {
            "selections": [
                {
                    "requirement_index": 0,
                    "evidence_ids": ["invented-id"],
                },
                {
                    "requirement_index": 1,
                    "evidence_ids": [],
                },
            ]
        }
    )

    try:
        parse_evidence_refinement(raw_json, matches)
    except ValueError as error:
        assert "未检索到的证据" in str(error)
    else:
        raise AssertionError("非法 evidence ID 应该被拒绝")


def check_incomplete_result_rejected() -> None:
    """每条岗位要求都必须恰好得到一项核对结果。"""

    matches, _ = build_matches()
    raw_json = json.dumps(
        {
            "selections": [
                {
                    "requirement_index": 0,
                    "evidence_ids": [],
                },
                {
                    "requirement_index": 0,
                    "evidence_ids": [],
                },
            ]
        }
    )

    try:
        parse_evidence_refinement(raw_json, matches)
    except ValueError as error:
        assert "重复索引" in str(error)
    else:
        raise AssertionError("重复 requirement_index 应该被拒绝")


def check_empty_matches_skip_client() -> None:
    """没有候选证据时不调用模型。"""

    matches, _ = build_matches()
    empty_matches = [
        RequirementEvidence(
            requirement=match.requirement,
            evidence=[],
        )
        for match in matches
    ]
    client = Mock()

    assert refine_requirement_evidence(empty_matches, client) == empty_matches
    client.generate_json.assert_not_called()


if __name__ == "__main__":
    check_strict_selection()
    check_invalid_id_rejected()
    check_incomplete_result_rejected()
    check_empty_matches_skip_client()
    print("Day 7 strict evidence refinement passed.")
