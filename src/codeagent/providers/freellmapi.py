"""
FreeLLMAPI provider — self-hosted proxy pooling free tiers of many providers.

freellmapi (https://github.com/tashfeenahmed/freellmapi) is an OpenAI-compatible
proxy the user runs themselves (Docker/Node). It aggregates free-tier keys for
Gemini, Groq, Cerebras, Mistral and others behind one endpoint, issues a
unified "freellmapi-..." bearer key, and routes/falls back across providers
server-side. The wire format is OpenAI-compatible (chat, streaming, tools), so
this provider reuses GroqProvider's request/parse/retry logic and only changes
the connection details: a per-instance base URL (each user's deployment lives
at a different address) and a model catalog fetched from that instance.
"""

import logging
from typing import Optional

from codeagent.core.exceptions import ProviderConfigError
from codeagent.providers.groq import GroqProvider

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://localhost:3001/v1"


class FreeLLMAPIProvider(GroqProvider):
    """Self-hosted freellmapi proxy — free-tier aggregation, OpenAI-compatible."""

    name = "freellmapi"

    # "auto" lets the proxy route to whichever pooled provider/model is
    # available; the real catalog depends on which keys the user loaded into
    # their instance, so fetch_models() asks the instance directly.
    RECOMMENDED_MODELS = ["auto"]

    def __init__(
        self,
        api_key: str,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> None:
        if not api_key:
            raise ProviderConfigError(
                self.name,
                "API key is required. Generate a unified key in your "
                "freellmapi dashboard (Keys page).",
            )

        try:
            import openai
        except ImportError as e:
            raise ImportError(
                "openai package not installed. Run: pip install openai"
            ) from e

        self.base_url = base_url or DEFAULT_BASE_URL
        self.model = model or self.get_default_model()
        self._api_key = api_key
        self._client = openai.OpenAI(base_url=self.base_url, api_key=api_key)
        self._total_tokens = 0

    @classmethod
    def get_default_model(cls) -> str:
        return "auto"

    @classmethod
    def list_models(cls) -> list[str]:
        return cls.RECOMMENDED_MODELS

    def fetch_models(self) -> list[str]:
        """Ask the running instance for its model catalog (GET /v1/models).

        Falls back to the static list if the instance is unreachable.
        """
        try:
            models = [m.id for m in self._client.models.list()]
            return models or list(self.RECOMMENDED_MODELS)
        except Exception as e:
            logger.debug(f"Could not fetch models from {self.base_url}: {e}")
            return list(self.RECOMMENDED_MODELS)

    def validate_api_key(self) -> bool:
        """Probe the instance for a clean success; surface real errors otherwise."""
        try:
            self._client.models.list()
            return True
        except Exception as e:
            msg = str(e)
            low = msg.lower()
            if "401" in low or "unauthorized" in low or "invalid api key" in low:
                raise ProviderConfigError(
                    self.name,
                    "Invalid API key. Generate a unified key in your "
                    "freellmapi dashboard (Keys page).",
                )
            if "403" in low or "forbidden" in low:
                raise ProviderConfigError(
                    self.name, "API key rejected (403). Check key permissions."
                )
            if "connection" in low or "timeout" in low or "network" in low:
                raise ProviderConfigError(
                    self.name,
                    f"Could not reach your freellmapi instance at "
                    f"{self.base_url} ({msg}). Is it running? "
                    "Start it with: docker compose up -d",
                )
            raise ProviderConfigError(self.name, f"Validation failed: {msg}")
