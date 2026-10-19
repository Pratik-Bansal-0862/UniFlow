import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMUnavailableError(RuntimeError):
    """Raised when no configured language model can produce a response."""


class LLMService:
    """Backend-only LLM adapter with Groq-first and Ollama fallback."""

    def __init__(self) -> None:
        self.provider = settings.llm_provider.strip().lower()
        self.groq_api_key = settings.groq_api_key
        self.groq_model = settings.groq_model
        self.ollama_base_url = settings.ollama_base_url.rstrip("/")
        self.ollama_model = settings.ollama_model
        self.timeout = settings.llm_timeout_seconds

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        errors: list[str] = []

        providers = (
            ["ollama", "groq"]
            if self.provider == "ollama"
            else ["groq", "ollama"]
        )

        for provider in providers:
            try:
                if provider == "groq":
                    if not self.groq_api_key:
                        errors.append("Groq API key is not configured.")
                        continue
                    return self._generate_groq(system_prompt, user_prompt)

                return self._generate_ollama(system_prompt, user_prompt)

            except (httpx.HTTPError, ValueError, KeyError) as exc:
                # Do not log prompts, student documents, or API credentials.
                logger.warning(
                    "LLM provider %s failed (%s).",
                    provider,
                    type(exc).__name__,
                )
                errors.append(f"{provider}: {type(exc).__name__}")

        raise LLMUnavailableError(
            "No language model is currently available. "
            "Check the backend provider configuration and local Ollama service. "
            + " ".join(errors)
        )

    def _generate_groq(self, system_prompt: str, user_prompt: str) -> str:
        response = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.groq_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.groq_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.2,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]

        if not isinstance(content, str) or not content.strip():
            raise ValueError("Groq returned an empty response.")

        return content.strip()

    def _generate_ollama(self, system_prompt: str, user_prompt: str) -> str:
        response = httpx.post(
            f"{self.ollama_base_url}/api/chat",
            json={
                "model": self.ollama_model,
                "stream": False,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "options": {"temperature": 0.2},
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        content = response.json()["message"]["content"]

        if not isinstance(content, str) or not content.strip():
            raise ValueError("Ollama returned an empty response.")

        return content.strip()
