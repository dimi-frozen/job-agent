"""DeepSeek 的最小 JSON Output 客户端。"""

import os

from dotenv import load_dotenv
from openai import OpenAI


DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-flash"


class DeepSeekClient:
    """负责调用 DeepSeek，并返回未经业务解析的 JSON 字符串。"""

    def __init__(self) -> None:
        load_dotenv()
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise RuntimeError("未设置环境变量 DEEPSEEK_API_KEY")

        base_url = os.getenv("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL)
        self.model = os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL)
        self._client = OpenAI(api_key=api_key, base_url=base_url)

    def generate_json(self, system_prompt: str, user_prompt: str) -> str:
        """向模型发送两条消息并返回 JSON 格式的原始字符串。"""

        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        if content is None or not content.strip():
            raise RuntimeError("DeepSeek 返回了空内容")
        return content
