from __future__ import annotations

import httpx
import pytest

from src.core.llm import LLMClient, LLMUnavailable


def test_from_env_is_none_without_configuration(monkeypatch) -> None:
    for name in ("OPENAI_BASE_URL", "OPENAI_API_KEY", "LLM_MODEL"):
        monkeypatch.delenv(name, raising=False)
    assert LLMClient.from_env() is None


def test_complete_raises_when_not_configured() -> None:
    client = LLMClient(base_url="", api_key="", model="")
    assert client.available is False
    with pytest.raises(LLMUnavailable):
        client.complete("system", "user")


def test_complete_parses_chat_completion() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer k"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": 'Trả lời [[X:D98.K1.a]]'}}]},
        )

    client = LLMClient(
        base_url="http://llm.local/v1",
        api_key="k",
        model="test",
        transport=httpx.MockTransport(handler),
    )
    assert client.complete("s", "u") == 'Trả lời [[X:D98.K1.a]]'


def test_complete_maps_http_error_to_unavailable() -> None:
    client = LLMClient(
        base_url="http://llm.local/v1",
        api_key="k",
        model="test",
        transport=httpx.MockTransport(lambda request: httpx.Response(500, json={})),
    )
    with pytest.raises(LLMUnavailable):
        client.complete("s", "u")