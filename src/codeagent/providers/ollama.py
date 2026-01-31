"""
Ollama provider for local LLM inference.

Ollama runs models locally, providing privacy and no API costs.
See: https://ollama.ai
"""

import json
import logging
from typing import Any, Generator, Optional

from codeagent.core.exceptions import APIError, ModelNotFoundError
from codeagent.core.types import LLMResponse, StreamChunk, ToolCall
from codeagent.providers.base import LLMProvider

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    """
    Ollama provider for running local models.

    Requires Ollama to be installed and running locally.
    Install from: https://ollama.ai/download
    """

    name = "ollama"

    # Models with good tool-calling support
    RECOMMENDED_MODELS = [
        "qwen2.5-coder:7b",
        "qwen2.5-coder:14b",
        "qwen2.5-coder:32b",
        "qwen2.5:7b",
        "qwen2.5:14b",
        "llama3.1:8b",
        "llama3.1:70b",
        "mistral:7b",
        "mixtral:8x7b",
        "deepseek-coder-v2:16b",
        "codellama:7b",
        "codellama:13b",
    ]

    def __init__(
        self,
        model: Optional[str] = None,
        host: Optional[str] = None,
    ) -> None:
        """
        Initialize Ollama provider.

        Args:
            model: Model name to use (e.g., 'qwen2.5-coder:7b')
            host: Ollama server URL (default: http://localhost:11434)
        """
        try:
            import ollama
        except ImportError as e:
            raise ImportError(
                "Ollama package not installed. Run: pip install ollama"
            ) from e

        self.model = model or self.get_default_model()
        self._host = host
        self._client = ollama.Client(host=host) if host else ollama

    @classmethod
    def get_default_model(cls) -> str:
        return "qwen2.5-coder:7b"

    @classmethod
    def list_models(cls) -> list[str]:
        return cls.RECOMMENDED_MODELS

    @property
    def supports_streaming(self) -> bool:
        return True

    def get_local_models(self) -> list[str]:
        """Get list of models currently downloaded in Ollama."""
        try:
            response = self._client.list()
            return [m["name"] for m in response.get("models", [])]
        except Exception as e:
            logger.warning(f"Failed to list local models: {e}")
            return []

    def pull_model(self, model: Optional[str] = None) -> None:
        """
        Pull a model from Ollama registry.

        Args:
            model: Model name to pull (uses configured model if not specified)
        """
        model_name = model or self.model
        logger.info(f"Pulling model: {model_name}")
        self._client.pull(model_name)

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> LLMResponse:
        """Send a chat request to Ollama."""
        import ollama

        try:
            kwargs: dict[str, Any] = {
                "model": self.model,
                "messages": messages,
            }
            if tools:
                kwargs["tools"] = tools

            response = self._client.chat(**kwargs)
            return self._parse_response(response)

        except ollama.ResponseError as e:
            if "model" in str(e).lower() and "not found" in str(e).lower():
                raise ModelNotFoundError(self.model, self.name) from e
            raise APIError(self.name, str(e)) from e

    def stream(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> Generator[StreamChunk, None, None]:
        """Stream a chat response from Ollama."""
        import ollama

        try:
            kwargs: dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "stream": True,
            }
            if tools:
                kwargs["tools"] = tools

            full_content = ""
            tool_calls: list[ToolCall] = []

            for chunk in self._client.chat(**kwargs):
                msg = chunk.get("message", {})

                # Handle content chunks
                if content := msg.get("content"):
                    full_content += content
                    yield StreamChunk(content=content)

                # Handle tool calls (usually at the end)
                if "tool_calls" in msg and msg["tool_calls"]:
                    for tc in msg["tool_calls"]:
                        tool_calls.append(self._parse_tool_call(tc, len(tool_calls)))

                # Check for completion
                if chunk.get("done"):
                    yield StreamChunk(
                        content="",
                        tool_calls=tool_calls,
                        is_complete=True,
                        finish_reason="stop" if not tool_calls else "tool_calls",
                    )

        except ollama.ResponseError as e:
            raise APIError(self.name, f"Streaming error: {e}") from e

    def _parse_response(self, response: dict[str, Any]) -> LLMResponse:
        """Parse Ollama response into LLMResponse."""
        msg = response.get("message", {})
        tool_calls: list[ToolCall] = []

        if "tool_calls" in msg and msg["tool_calls"]:
            for i, tc in enumerate(msg["tool_calls"]):
                tool_calls.append(self._parse_tool_call(tc, i))

        return LLMResponse(
            content=msg.get("content"),
            tool_calls=tool_calls,
            finish_reason="stop" if not tool_calls else "tool_calls",
        )

    def _parse_tool_call(self, tc: dict[str, Any], index: int) -> ToolCall:
        """Parse a single tool call from Ollama response."""
        func = tc.get("function", {})
        arguments = func.get("arguments", {})

        # Handle string arguments (need to parse as JSON)
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                arguments = {}

        return ToolCall(
            id=tc.get("id", f"call_{index}"),
            name=func.get("name", ""),
            arguments=arguments,
        )
