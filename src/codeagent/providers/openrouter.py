"""
OpenRouter provider for accessing multiple cloud LLMs.

OpenRouter provides a unified API to access models from OpenAI,
Anthropic, Google, Meta, and others.
See: https://openrouter.ai
"""

import json
import logging
import time
from typing import Any, Generator, Optional

from codeagent.core.exceptions import APIError, ProviderConfigError
from codeagent.core.types import LLMResponse, StreamChunk, ToolCall
from codeagent.providers.base import LLMProvider

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 1.0  # seconds
RETRY_BACKOFF = 2.0  # exponential backoff multiplier


class OpenRouterProvider(LLMProvider):
    """
    OpenRouter provider for cloud model access.

    Requires an API key from https://openrouter.ai/keys
    """

    name = "openrouter"
    BASE_URL = "https://openrouter.ai/api/v1"

    # Popular models with good tool support
    RECOMMENDED_MODELS = [
        "deepseek/deepseek-chat",
        "deepseek/deepseek-coder",
        "anthropic/claude-3.5-sonnet",
        "anthropic/claude-3-haiku",
        "openai/gpt-4o",
        "openai/gpt-4o-mini",
        "google/gemini-pro-1.5",
        "meta-llama/llama-3.1-70b-instruct",
        "meta-llama/llama-3.1-8b-instruct",
        "mistralai/mistral-large",
        "qwen/qwen-2.5-coder-32b-instruct",
    ]

    # Models that are free to use
    FREE_MODELS = [
        "deepseek/deepseek-chat",
        "meta-llama/llama-3.1-8b-instruct:free",
        "google/gemma-2-9b-it:free",
        "mistralai/mistral-7b-instruct:free",
        "qwen/qwen-2.5-7b-instruct:free",
    ]

    def __init__(
        self,
        api_key: str,
        model: Optional[str] = None,
    ) -> None:
        """
        Initialize OpenRouter provider.

        Args:
            api_key: OpenRouter API key
            model: Model identifier (e.g., 'deepseek/deepseek-chat')
        """
        if not api_key:
            raise ProviderConfigError(
                self.name,
                "API key is required. Get one at https://openrouter.ai/keys",
            )

        try:
            import openai
        except ImportError as e:
            raise ImportError(
                "OpenAI package not installed. Run: pip install openai"
            ) from e

        self.model = model or self.get_default_model()
        self._api_key = api_key
        self._client = openai.OpenAI(
            base_url=self.BASE_URL,
            api_key=api_key,
        )
        self._total_tokens = 0

    @property
    def total_tokens_used(self) -> int:
        """Get total tokens used in this session."""
        return self._total_tokens

    @classmethod
    def get_default_model(cls) -> str:
        return "deepseek/deepseek-chat"

    @classmethod
    def list_models(cls) -> list[str]:
        return cls.RECOMMENDED_MODELS

    @classmethod
    def get_free_models(cls) -> list[str]:
        """Get list of free models on OpenRouter."""
        return cls.FREE_MODELS

    @property
    def supports_streaming(self) -> bool:
        return True

    def validate_api_key(self) -> bool:
        """
        Validate the API key by listing models.

        Returns True only on a clean success. A clear auth failure raises
        ProviderConfigError. Network/transport errors are surfaced too so the
        user isn't given a false "Valid" reading that fails on first real call.
        """
        try:
            self._client.models.list()
            return True
        except Exception as e:
            error_msg = str(e)
            lowered = error_msg.lower()
            if "401" in lowered or "unauthorized" in lowered or "invalid api key" in lowered:
                raise ProviderConfigError(
                    self.name,
                    "Invalid API key. Check your key at https://openrouter.ai/keys",
                )
            if "403" in lowered or "forbidden" in lowered:
                raise ProviderConfigError(
                    self.name,
                    "API key rejected (403). Check that it has access to chat completions.",
                )
            if "connection" in lowered or "timeout" in lowered or "network" in lowered:
                raise ProviderConfigError(
                    self.name,
                    f"Could not reach OpenRouter to validate the key ({error_msg}). "
                    "Check your internet connection.",
                )
            # Anything else: don't pretend it's valid.
            raise ProviderConfigError(
                self.name, f"Validation failed: {error_msg}"
            )

    def _supports_prompt_caching(self) -> bool:
        """OpenRouter passes cache_control through to Anthropic models."""
        return self.model.startswith("anthropic/")

    def _with_cache_breakpoints(
        self, messages: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Add Anthropic cache_control breakpoints to system prompt and last
        tool/user message. Long stable prefixes (system + most of the history)
        become cached; only the tail re-tokenizes each turn.
        """
        if not self._supports_prompt_caching() or not messages:
            return messages

        def add_cache(msg: dict[str, Any]) -> dict[str, Any]:
            content = msg.get("content")
            if not isinstance(content, str) or not content:
                return msg
            new = dict(msg)
            new["content"] = [
                {
                    "type": "text",
                    "text": content,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
            return new

        out = [dict(m) for m in messages]
        # Cache the system prompt (large + stable).
        if out and out[0].get("role") == "system":
            out[0] = add_cache(out[0])

        # Cache the most recent non-assistant message so prior turns get reused.
        for i in range(len(out) - 1, -1, -1):
            if out[i].get("role") in ("user", "tool"):
                if i != 0:  # don't double-mark when system is the only message
                    out[i] = add_cache(out[i])
                break
        return out

    def _retry_request(self, func, *args, **kwargs):
        """Execute a request with retry logic."""
        last_error = None
        delay = RETRY_DELAY

        for attempt in range(MAX_RETRIES):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                error_msg = str(e).lower()

                # Don't retry on auth errors
                if "401" in error_msg or "unauthorized" in error_msg:
                    raise

                # Don't retry on bad requests
                if "400" in error_msg or "invalid" in error_msg:
                    raise

                if attempt < MAX_RETRIES - 1:
                    logger.warning(f"Request failed (attempt {attempt + 1}), retrying in {delay}s: {e}")
                    time.sleep(delay)
                    delay *= RETRY_BACKOFF

        raise last_error

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> LLMResponse:
        """Send a chat request to OpenRouter with retry logic."""
        cached_messages = self._with_cache_breakpoints(messages)

        def _make_request():
            kwargs: dict[str, Any] = {
                "model": self.model,
                "messages": cached_messages,
            }
            if tools:
                kwargs["tools"] = tools
            return self._client.chat.completions.create(**kwargs)

        try:
            response = self._retry_request(_make_request)
            return self._parse_response(response)
        except APIError:
            raise
        except Exception as e:
            error_msg = str(e)
            status_code = getattr(e, "status_code", None)

            # Provide helpful error messages
            if "rate limit" in error_msg.lower():
                error_msg = "Rate limit exceeded. Please wait a moment and try again."
            elif "timeout" in error_msg.lower():
                error_msg = "Request timed out. The model may be overloaded."
            elif "connection" in error_msg.lower():
                error_msg = "Connection failed. Check your internet connection."

            raise APIError(self.name, error_msg, status_code) from e

    def stream(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> Generator[StreamChunk, None, None]:
        """Stream a chat response from OpenRouter."""
        try:
            cached_messages = self._with_cache_breakpoints(messages)
            kwargs: dict[str, Any] = {
                "model": self.model,
                "messages": cached_messages,
                "stream": True,
                "stream_options": {"include_usage": True},
            }
            if tools:
                kwargs["tools"] = tools

            # Buffer for accumulating tool calls across chunks
            tool_calls_buffer: dict[int, dict[str, Any]] = {}

            response = self._client.chat.completions.create(**kwargs)

            for chunk in response:
                # Trailing usage-only chunk arrives after choices are done.
                usage = getattr(chunk, "usage", None)
                if usage and getattr(usage, "total_tokens", None):
                    self._total_tokens += usage.total_tokens
                    logger.debug(f"Streaming usage: total={usage.total_tokens}, cumulative={self._total_tokens}")

                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta

                # Handle content
                if delta.content:
                    yield StreamChunk(content=delta.content)

                # Handle tool calls (accumulated across chunks)
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
                                tool_calls_buffer[idx]["name"] = tc.function.name
                            if tc.function.arguments:
                                tool_calls_buffer[idx]["arguments"] += tc.function.arguments

                # Check for completion
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
        """Parse OpenAI-format response into LLMResponse."""
        msg = response.choices[0].message
        tool_calls: list[ToolCall] = []

        if msg.tool_calls:
            for tc in msg.tool_calls:
                arguments = self._parse_arguments(tc.function.arguments)
                tool_calls.append(
                    ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=arguments,
                    )
                )

        # Track token usage
        usage = None
        if hasattr(response, 'usage') and response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
            # Update cumulative usage
            self._total_tokens += response.usage.total_tokens
            logger.debug(f"Token usage: {usage}, Total: {self._total_tokens}")

        return LLMResponse(
            content=msg.content,
            tool_calls=tool_calls,
            finish_reason=response.choices[0].finish_reason,
        )

    def _parse_tool_calls_buffer(
        self, buffer: dict[int, dict[str, Any]]
    ) -> list[ToolCall]:
        """Parse accumulated tool calls buffer into ToolCall objects."""
        tool_calls: list[ToolCall] = []
        for tc_data in buffer.values():
            arguments = self._parse_arguments(tc_data["arguments"])
            tool_calls.append(
                ToolCall(
                    id=tc_data["id"],
                    name=tc_data["name"],
                    arguments=arguments,
                )
            )
        return tool_calls

    def _parse_arguments(self, arguments: str | dict[str, Any]) -> dict[str, Any]:
        """Parse tool call arguments, handling both string and dict formats."""
        if isinstance(arguments, dict):
            return arguments
        if not arguments:
            return {}
        try:
            return json.loads(arguments)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse tool arguments: {arguments}")
            return {}
