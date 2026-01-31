"""
Abstract base class for LLM providers.

Uses Protocol for structural subtyping and ABC for implementation contracts.
This follows the Strategy pattern, allowing different providers to be
swapped without changing the agent code.
"""

from abc import ABC, abstractmethod
from typing import Any, Generator, Optional, Protocol, runtime_checkable

from codeagent.core.types import LLMResponse, StreamChunk


@runtime_checkable
class SupportsChat(Protocol):
    """Protocol for objects that support chat completion."""

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> LLMResponse: ...


@runtime_checkable
class SupportsStreaming(Protocol):
    """Protocol for objects that support streaming."""

    def stream(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> Generator[StreamChunk, None, None]: ...


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    All providers must implement the chat method.
    Streaming is optional but recommended.

    Attributes:
        name: Human-readable name for the provider
        model: The model identifier being used
    """

    name: str
    model: str

    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> LLMResponse:
        """
        Send a chat completion request.

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            tools: Optional list of tool definitions in OpenAI format

        Returns:
            LLMResponse containing the model's response

        Raises:
            APIError: If the API call fails
        """
        pass

    def stream(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> Generator[StreamChunk, None, None]:
        """
        Stream a chat completion response.

        Default implementation falls back to non-streaming chat.
        Override for true streaming support.

        Args:
            messages: List of message dictionaries
            tools: Optional list of tool definitions

        Yields:
            StreamChunk objects containing partial responses
        """
        response = self.chat(messages, tools)
        yield StreamChunk(
            content=response.content or "",
            tool_calls=response.tool_calls,
            is_complete=True,
            finish_reason=response.finish_reason,
        )

    @property
    def supports_streaming(self) -> bool:
        """Check if this provider supports true streaming."""
        # Override in subclasses that support streaming
        return False

    @property
    def supports_tools(self) -> bool:
        """Check if this provider supports tool calling."""
        # Most modern providers do
        return True

    @classmethod
    @abstractmethod
    def get_default_model(cls) -> str:
        """Get the default model for this provider."""
        pass

    @classmethod
    @abstractmethod
    def list_models(cls) -> list[str]:
        """List available/recommended models for this provider."""
        pass

    def validate_model(self, model: str) -> bool:
        """
        Validate if a model is available.

        Default implementation returns True. Override for actual validation.
        """
        return True
