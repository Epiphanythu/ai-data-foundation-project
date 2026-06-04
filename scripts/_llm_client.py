"""scripts/_llm_client.py LLM 调用封装
基于 OpenAI SDK 适配 GLM；统一管理 base_url、模型名与重试。
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from constant.llm import (  # noqa: E402
    resolve_api_key,
    resolve_base_url,
    resolve_model,
)

logger = logging.getLogger(__name__)


class LLMClient:
    """LLMClient 封装基于 OpenAI 协议的 LLM 调用
    通过 OPENAI_BASE_URL/OPENAI_API_KEY/OPENAI_MODEL 控制后端，
    用户可指向 GLM / OpenAI / 其他兼容服务。
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        # 1. 解析配置（参数优先，否则读环境变量，最后用默认值）
        self.api_key = api_key or resolve_api_key()
        self.base_url = base_url or resolve_base_url()
        self.model = model or resolve_model()
        self._client = None

    def _ensure_client(self):
        # 2. 延迟初始化 openai 客户端，避免无 key 时也强制依赖
        if self._client is not None:
            return
        if not self.api_key:
            raise RuntimeError(
                "未检测到 OPENAI_API_KEY，请先 export OPENAI_API_KEY=...（GLM 也使用同名变量）"
            )
        from openai import OpenAI

        self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 1500,
    ) -> str:
        """chat 单轮对话调用，返回模型回复文本"""
        self._ensure_client()
        resp = self._client.chat.completions.create(  # type: ignore[union-attr]
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content or ""
