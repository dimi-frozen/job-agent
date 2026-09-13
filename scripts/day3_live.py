"""手动调用一次 DeepSeek，检查真实 JD 提取结果。"""

import sys

from job_agent.llm.client import DeepSeekClient
from job_agent.services.job_extraction import extract_job_posting


SAMPLE_JD = """某某科技正在招聘 AI 应用开发工程师。
岗位要求：熟悉 Python 开发，具有 RAG 项目经验。
加分项：了解 LangGraph。
"""


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    client = DeepSeekClient()
    job_posting = extract_job_posting(SAMPLE_JD, client)
    print(job_posting.model_dump_json(indent=2))
