"""
Groq provider for ultra-fast cloud inference.

Groq runs open-weight models on custom LPU hardware with very low latency.
The API is OpenAI-compatible. See: https://console.groq.com
"""

import json
import logging
import time
from typing import Any, Generator, Optional

from codeagent.core.exceptions import APIError, ProviderConfigError
from codeagent.core.types import LLMResponse, StreamChunk, ToolCall
from codeagent.providers.base import LLMProvider

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 1.0
RETRY_BACKOFF = 2.0


class GroqProvider(LLMProvider):
    """Groq cloud provider — very fast inference on open-weight models."""

    name = "groq"
    BASE_URL = "https://api.groq.com/openai/v1"

    # Models on Groq verified for clean tool-call behavior with our 48-tool
    # schema as of 0.2.2. Avoid llama-3.3-70b-versatile (tool-name concat bug)
    # and small-context models (413 with our schema).
    RECOMMENDED_MODELS = [
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
        "llama-3.3-70b-versatile",
        "meta-llama/llama-4-scout-17b-16e-instruct",
    ]

    def __init__(
        self,
        api_key: str,
        model: Optional[str] = None,
    ) -> None:
        if not api_key:
            raise ProviderConfigError(
                self.name,
                "API key is required. Get one at https://console.groq.com/keys",
            )

        try:
            import openai
        except ImportError as e:
            raise ImportError(
                "openai package not installed. Run: pip install openai"
            ) from e

        self.model = model or self.get_default_model()
        self._api_key = api_key
        self._client = openai.OpenAI(base_url=self.BASE_URL, api_key=api_key)
        self._total_tokens = 0

    @property
    def total_tokens_used(self) -> int:
        return self._total_tokens

    @classmethod
    def get_default_model(cls) -> str:
        return "openai/gpt-oss-120b"

    @classmethod
    def list_models(cls) -> list[str]:
        return cls.RECOMMENDED_MODELS

    @property
    def supports_streaming(self) -> bool:
        return True

    def validate_api_key(self) -> bool:
        """Probe the API for a clean success; surface real errors otherwise."""
        try:
            self._client.models.list()
            return True
        except Exception as e:
            msg = str(e)
            low = msg.lower()
            if "401" in low or "unauthorized" in low or "invalid api key" in low:
                raise ProviderConfigError(
                    self.name,
                    "Invalid API key. Check your key at https://console.groq.com/keys",
                )
            if "403" in low or "forbidden" in low:
                raise ProviderConfigError(
                    self.name, "API key rejected (403). Check key permissions."
                )
            if "connection" in low or "timeout" in low or "network" in low:
                raise ProviderConfigError(
                    self.name,
                    f"Could not reach Groq to validate the key ({msg}). "
                    "Check your internet connection.",
                )
            raise ProviderConfigError(self.name, f"Validation failed: {msg}")

    def _retry_request(self, func, *args, **kwargs):
        last_error = None
        delay = RETRY_DELAY
        for attempt in range(MAX_RETRIES):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                low = str(e).lower()
                if "401" in low or "unauthorized" in low:
                    raise
                if "400" in low or "invalid" in low:
                    raise
                if attempt < MAX_RETRIES - 1:
                    logger.warning(
                        f"Request failed (attempt {attempt + 1}), retrying in {delay}s: {e}"
                    )
                    time.sleep(delay)
                    delay *= RETRY_BACKOFF
        raise last_error

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> LLMResponse:
        def _make_request():
            kwargs: dict[str, Any] = {"model": self.model, "messages": messages}
            if tools:
                kwargs["tools"] = tools
            return self._client.chat.completions.create(**kwargs)

        try:
            response = self._retry_request(_make_request)
            return self._parse_response(response)
        except APIError:
            raise
        except Exception as e:
            msg = str(e)
            status_code = getattr(e, "status_code", None)
            low = msg.lower()
            if "rate limit" in low:
                msg = "Rate limit exceeded. Please wait a moment and try again."
            elif "timeout" in low:
                msg = "Request timed out. The model may be overloaded."
            elif "connection" in low:
                msg = "Connection failed. Check your internet connection."
            raise APIError(self.name, msg, status_code) from e

    def stream(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> Generator[StreamChunk, None, None]:
        try:
            kwargs: dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "stream": True,
                "stream_options": {"include_usage": True},
            }
            if tools:
                kwargs["tools"] = tools

            tool_calls_buffer: dict[int, dict[str, Any]] = {}
            response = self._client.chat.completions.create(**kwargs)

            for chunk in response:
                usage = getattr(chunk, "usage", None)
                if usage and getattr(usage, "total_tokens", None):
                    self._total_tokens += usage.total_tokens

                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta

                if delta.content:
                    yield StreamChunk(content=delta.content)

                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in tool_calls_buffer:
                            tool_calls_buffer[idx] = {
                                "id": tc.id or f"call_{idx}",
                                "name": "",
                                "arguments": "",
                            }
                        if tc.function:
                            if tc.function.name:
                                name = tc.function.name
                                # Some Groq responses concatenate the JSON
                                # args into the name field. Split if so.
                                if "{" in name:
                                    pure_name, _, tail = name.partition("{")
                                    tool_calls_buffer[idx]["name"] = pure_name.strip()
                                    tool_calls_buffer[idx]["arguments"] += "{" + tail
                                else:
                                    tool_calls_buffer[idx]["name"] = name
                            if tc.function.arguments:
                                tool_calls_buffer[idx]["arguments"] += tc.function.arguments

                finish_reason = chunk.choices[0].finish_reason
                if finish_reason:
                    tool_calls = self._parse_tool_calls_buffer(tool_calls_buffer)
                    yield StreamChunk(
                        content="",
                        tool_calls=tool_calls,
                        is_complete=True,
                        finish_reason=finish_reason,
                    )

        except Exception as e:
            raise APIError(self.name, f"Streaming error: {e}") from e

    def _parse_response(self, response: Any) -> LLMResponse:
        msg = response.choices[0].message
        tool_calls: list[ToolCall] = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls.append(
                    ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=self._parse_arguments(tc.function.arguments),
                    )
                )

        if hasattr(response, "usage") and response.usage:
            self._total_tokens += response.usage.total_tokens

        return LLMResponse(
            content=msg.content,
            tool_calls=tool_calls,
            finish_reason=response.choices[0].finish_reason,
        )

    def _parse_tool_calls_buffer(
        self, buffer: dict[int, dict[str, Any]]
    ) -> list[ToolCall]:
        out: list[ToolCall] = []
        for tc_data in buffer.values():
            out.append(
                ToolCall(
                    id=tc_data["id"],
                    name=tc_data["name"],
                    arguments=self._parse_arguments(tc_data["arguments"]),
                )
            )
        return out

    @staticmethod
    def _parse_arguments(arguments: str | dict[str, Any]) -> dict[str, Any]:
        if isinstance(arguments, dict):
            return arguments
        if not arguments:
            return {}
        try:
            return json.loads(arguments)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse tool arguments: {arguments}")
            return {}
