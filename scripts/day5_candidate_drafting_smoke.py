"""离线检查候选证据草稿的解析、校验与服务调用。"""

import json
from unittest.mock import Mock

from pydantic import ValidationError

from job_agent.domain.jobs import JobRequirement
from job_agent.services.candidate_drafting import (
    draft_candidate_evidence,
    parse_candidate_evidence,
)


answer = "我使用 LangGraph 实现了证据检查与条件路由"
payload = {
    "capability_name": "LangGraph",
    "summary": "使用 LangGraph 实现证据检查与条件路由",
    "source_quote": answer,
    "status": "candidate",
}
raw_json = json.dumps(payload, ensure_ascii=False)

draft = parse_candidate_evidence(raw_json, answer)
assert draft.status == "candidate"

client = Mock()
client.generate_json.return_value = raw_json
requirement = JobRequirement(
    text="熟悉 LangGraph",
    priority="required",
    source_quote="熟悉 LangGraph",
    evidence_query="LangGraph 项目经验",
)
generated_draft = draft_candidate_evidence(
    requirement,
    answer,
    client,
)
assert generated_draft == draft
assert "<job_requirement>" in client.generate_json.call_args.kwargs[
    "user_prompt"
]

bad_quote_payload = {
    **payload,
    "source_quote": "用户没有说过的话",
}
try:
    parse_candidate_evidence(
        json.dumps(bad_quote_payload, ensure_ascii=False),
        answer,
    )
except ValueError:
    pass
else:
    raise AssertionError("不存在于用户回答中的引用不应通过校验")

bad_status_payload = {
    **payload,
    "status": "confirmed",
}
try:
    parse_candidate_evidence(
        json.dumps(bad_status_payload, ensure_ascii=False),
        answer,
    )
except ValidationError:
    pass
else:
    raise AssertionError("模型不能把候选草稿直接标记为 confirmed")

print("Day 5 candidate drafting service passed.")
