"""Client LLM tương thích OpenAI, tuỳ chọn (SPEC §12.1).

Mặc định **tắt**: chỉ hoạt động khi có `OPENAI_BASE_URL` + `OPENAI_API_KEY` + `LLM_MODEL`
trong biến môi trường (tên biến ghi trong `config/llm.yaml`, không ghi secret vào file).
Không có cấu hình thì pipeline dùng đường trích nguyên văn, không lỗi.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import httpx


class LLMUnavailable(RuntimeError):
    """Chưa cấu hình endpoint hoặc endpoint lỗi."""


@dataclass
class LLMClient:
    base_url: str
    api_key: str
    model: str
    timeout: float = 60.0
    transport: httpx.BaseTransport | None = None

    @classmethod
    def from_env(cls) -> LLMClient | None:
        base_url = os.environ.get("OPENAI_BASE_URL", "").strip()
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        model = os.environ.get("LLM_MODEL", "").strip()
        if not (base_url and api_key and model):
            return None
        return cls(base_url=base_url.rstrip("/"), api_key=api_key, model=model)

    @property
    def available(self) -> bool:
        return bool(self.base_url and self.api_key and self.model)

    def complete(self, system: str, user: str, temperature: float = 0.0) -> str:
        """Gọi /chat/completions và trả text; lỗi mạng/HTTP thành LLMUnavailable."""
        if not self.available:
            raise LLMUnavailable("chưa cấu hình OPENAI_BASE_URL/OPENAI_API_KEY/LLM_MODEL")
        payload = {
            "model": self.model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        try:
            with httpx.Client(timeout=self.timeout, transport=self.transport) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise LLMUnavailable(str(error)) from error
        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as error:
            raise LLMUnavailable(f"phản hồi không đúng định dạng: {data}") from error