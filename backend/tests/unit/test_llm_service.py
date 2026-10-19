import httpx
import pytest

from app.services.llm_service import LLMService, LLMUnavailableError


def make_service():
    service = LLMService()
    service.provider = "groq"
    service.groq_api_key = "test-key"
    service.groq_model = "test-model"
    service.ollama_base_url = "http://ollama.test"
    service.ollama_model = "test-model"
    service.timeout = 1.0
    return service


def test_groq_success(monkeypatch):
    service = make_service()

    def fake_post(url, **kwargs):
        assert url.endswith("/chat/completions")
        assert kwargs["headers"]["Authorization"] == "Bearer test-key"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": "  Draft plan  "}}
                ]
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr("app.services.llm_service.httpx.post", fake_post)

    result = service.generate(system_prompt="system", user_prompt="user")
    assert result == "Draft plan"


def test_groq_failure_falls_back_to_ollama(monkeypatch):
    service = make_service()
    calls = []

    def fake_post(url, **kwargs):
        calls.append(url)
        if "api.groq.com" in url:
            request = httpx.Request("POST", url)
            response = httpx.Response(503, request=request)
            raise httpx.HTTPStatusError(
                "unavailable", request=request, response=response
            )

        return httpx.Response(
            200,
            json={"message": {"content": "Local response"}},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr("app.services.llm_service.httpx.post", fake_post)

    assert service.generate(system_prompt="s", user_prompt="u") == "Local response"
    assert len(calls) == 2
    assert "api.groq.com" in calls[0]
    assert "/api/chat" in calls[1]


def test_both_providers_unavailable(monkeypatch):
    service = make_service()

    def fake_post(url, **kwargs):
        request = httpx.Request("POST", url)
        raise httpx.ConnectError("unavailable", request=request)

    monkeypatch.setattr("app.services.llm_service.httpx.post", fake_post)

    with pytest.raises(LLMUnavailableError):
        service.generate(system_prompt="s", user_prompt="u")


def test_empty_groq_response_falls_back_to_ollama(monkeypatch):
    service = make_service()

    def fake_post(url, **kwargs):
        if "api.groq.com" in url:
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": " "}}]},
                request=httpx.Request("POST", url),
            )
        return httpx.Response(
            200,
            json={"message": {"content": "Ollama works"}},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr("app.services.llm_service.httpx.post", fake_post)

    assert service.generate(system_prompt="s", user_prompt="u") == "Ollama works"
