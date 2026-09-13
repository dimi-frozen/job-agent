"""离线检查岗位 JSON 解析与业务校验边界。"""

import json
import os
from unittest.mock import Mock, patch

from pydantic import ValidationError

from job_agent.domain.jobs import JobPosting, RequirementPriority
from job_agent.llm.client import DEFAULT_MODEL, DeepSeekClient
from job_agent.services.job_extraction import (
    JOB_EXTRACTION_SYSTEM_PROMPT,
    extract_job_posting,
    parse_job_extraction,
)


SOURCE_TEXT = """AI 应用开发工程师
某某科技正在招聘 AI 应用开发工程师。
岗位要求：熟悉 Python 开发，有 RAG 项目经验。
加分项：了解 LangGraph。
"""

VALID_PAYLOAD = {
    "title": "AI 应用开发工程师",
    "company": "某某科技",
    "requirements": [
        {
            "text": "熟悉 Python 开发",
            "priority": "required",
            "source_quote": "熟悉 Python 开发",
            "evidence_query": "Python 开发项目经验",
        },
        {
            "text": "了解 LangGraph",
            "priority": "preferred",
            "source_quote": "了解 LangGraph",
            "evidence_query": "LangGraph 使用经验",
        },
    ],
}


def check_valid_extraction() -> None:
    raw_json = json.dumps(VALID_PAYLOAD, ensure_ascii=False)
    job_posting = parse_job_extraction(raw_json, SOURCE_TEXT)

    assert isinstance(job_posting, JobPosting)
    assert job_posting.title == "AI 应用开发工程师"
    assert job_posting.company == "某某科技"
    assert len(job_posting.requirements) == 2
    assert job_posting.requirements[0].priority is RequirementPriority.REQUIRED
    assert job_posting.requirements[1].text == "了解 LangGraph"


def check_invalid_json() -> None:
    try:
        parse_job_extraction('{"title":', SOURCE_TEXT)
    except json.JSONDecodeError:
        pass
    else:
        raise AssertionError("不合法的 JSON 应该触发 JSONDecodeError")


def check_invalid_model_data() -> None:
    invalid_payloads = [
        {"requirements": []},
        {
            "requirements": [
                {
                    "text": "",
                    "priority": "required",
                    "source_quote": "熟悉 Python 开发",
                    "evidence_query": "Python 开发项目经验",
                }
            ]
        },
        {
            "requirements": [
                {
                    "text": "熟悉 Python 开发",
                    "priority": "unknown",
                    "source_quote": "熟悉 Python 开发",
                    "evidence_query": "Python 开发项目经验",
                }
            ]
        },
    ]

    for payload in invalid_payloads:
        try:
            parse_job_extraction(
                json.dumps(payload, ensure_ascii=False),
                SOURCE_TEXT,
            )
        except ValidationError:
            continue

        raise AssertionError("不符合岗位模型的数据应该触发 ValidationError")


def check_source_quote() -> None:
    payload = {
        "requirements": [
            {
                "text": "精通 Java",
                "priority": "required",
                "source_quote": "精通 Java",
                "evidence_query": "Java 项目经验",
            }
        ]
    }

    try:
        parse_job_extraction(
            json.dumps(payload, ensure_ascii=False),
            SOURCE_TEXT,
        )
    except ValueError as error:
        assert "精通 Java" in str(error)
    else:
        raise AssertionError("原文中不存在的引用应该触发 ValueError")


def check_deepseek_client() -> None:
    with (
        patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}, clear=True),
        patch("job_agent.llm.client.load_dotenv"),
        patch("job_agent.llm.client.OpenAI") as openai_type,
    ):
        api = openai_type.return_value
        api.chat.completions.create.return_value = Mock(
            choices=[Mock(message=Mock(content='{"requirements": []}'))]
        )
        client = DeepSeekClient()
        content = client.generate_json("请输出 JSON", "一段 JD")

    assert content == '{"requirements": []}'
    api.chat.completions.create.assert_called_once_with(
        model=DEFAULT_MODEL,
        messages=[
            {"role": "system", "content": "请输出 JSON"},
            {"role": "user", "content": "一段 JD"},
        ],
        response_format={"type": "json_object"},
    )

    api.chat.completions.create.return_value = Mock(
        choices=[Mock(message=Mock(content="   "))]
    )
    try:
        client.generate_json("请输出 JSON", "一段 JD")
    except RuntimeError:
        pass
    else:
        raise AssertionError("模型返回空内容时应该触发 RuntimeError")


def check_extraction_service() -> None:
    client = Mock(spec=DeepSeekClient)
    client.generate_json.return_value = json.dumps(
        VALID_PAYLOAD,
        ensure_ascii=False,
    )

    job_posting = extract_job_posting(SOURCE_TEXT, client)

    assert job_posting.title == "AI 应用开发工程师"
    client.generate_json.assert_called_once()
    call_arguments = client.generate_json.call_args.kwargs
    assert call_arguments["system_prompt"] == JOB_EXTRACTION_SYSTEM_PROMPT
    assert "JSON" in call_arguments["system_prompt"]
    assert SOURCE_TEXT in call_arguments["user_prompt"]

    try:
        extract_job_posting("   ", client)
    except ValueError:
        pass
    else:
        raise AssertionError("空 JD 原文应该触发 ValueError")


if __name__ == "__main__":
    check_valid_extraction()
    check_invalid_json()
    check_invalid_model_data()
    check_source_quote()
    check_deepseek_client()
    check_extraction_service()
    print("Day 3 offline job extraction passed.")
