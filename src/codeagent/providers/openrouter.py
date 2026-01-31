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
        Validate the API key by making a test request.

        Returns:
            True if API key is valid

        Raises:
            ProviderConfigError: If API key is invalid
        """
        try:
            # Make a minimal request to validate the key
            self._client.models.list()
            return True
        except Exception as e:
            error_msg = str(e).lower()
            if "401" in error_msg or "unauthorized" in error_msg or "invalid" in error_msg:
                raise ProviderConfigError(
                    self.name,
                    "Invalid API key. Check your key at https://openrouter.ai/keys"
                )
            # Other errors might be temporary, don't fail validation
            logger.warning(f"API validation warning: {e}")
            return True

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
        def _make_request():
            kwargs: dict[str, Any] = {
                "model": self.model,
                "messages": messages,
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
            kwargs: dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "stream": True,
            }
            if tools:
                kwargs["tools"] = tools

            # Buffer for accumulating tool calls across chunks
            tool_calls_buffer: dict[int, dict[str, Any]] = {}

            response = self._client.chat.completions.create(**kwargs)

            for chunk in response:
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
