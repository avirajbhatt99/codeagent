"""
Core type definitions for CodeAgent.

Uses dataclasses and enums for clean, immutable data structures.
All types are designed to be serializable for conversation history.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class Role(str, Enum):
    """Message roles in the conversation."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass(frozen=True, slots=True)
class ToolCall:
    """
    Represents a tool invocation request from the LLM.

    Attributes:
        id: Unique identifier for this tool call
        name: Name of the tool to invoke
        arguments: Dictionary of arguments to pass to the tool
    """

    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "type": "function",
            "function": {
                "name": self.name,
                "arguments": self.arguments,
            },
        }


@dataclass(frozen=True, slots=True)
class ToolResult:
    """
    Result from executing a tool.

    Attributes:
        tool_call_id: ID of the tool call this is responding to
        content: String result from the tool
        is_error: Whether the result represents an error
    """

    tool_call_id: str
    content: str
    is_error: bool = False

    def to_message_dict(self) -> dict[str, Any]:
        """Convert to message dictionary for LLM."""
        return {
            "role": Role.TOOL.value,
            "tool_call_id": self.tool_call_id,
            "content": self.content,
        }


@dataclass(slots=True)
class Message:
    """
    A message in the conversation.

    Supports all message types: system, user, assistant, and tool responses.
    """

    role: Role
    content: Optional[str] = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: Optional[str] = None  # For tool response messages
    name: Optional[str] = None  # Optional name for the message sender

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for LLM API."""
        result: dict[str, Any] = {"role": self.role.value}

        if self.content is not None:
            result["content"] = self.content

        if self.tool_calls:
            result["tool_calls"] = [tc.to_dict() for tc in self.tool_calls]

        if self.tool_call_id:
            result["tool_call_id"] = self.tool_call_id

        if self.name:
            result["name"] = self.name

        return result

    @classmethod
    def system(cls, content: str) -> "Message":
        """Create a system message."""
        return cls(role=Role.SYSTEM, content=content)

    @classmethod
    def user(cls, content: str) -> "Message":
        """Create a user message."""
        return cls(role=Role.USER, content=content)

    @classmethod
    def assistant(
        cls,
        content: Optional[str] = None,
        tool_calls: Optional[list[ToolCall]] = None,
    ) -> "Message":
        """Create an assistant message."""
        return cls(
            role=Role.ASSISTANT,
            content=content,
            tool_calls=tool_calls or [],
        )

    @classmethod
    def tool_response(cls, tool_call_id: str, content: str) -> "Message":
        """Create a tool response message."""
        return cls(
            role=Role.TOOL,
            content=content,
            tool_call_id=tool_call_id,
        )


@dataclass(slots=True)
class LLMResponse:
    """
    Response from an LLM provider.

    Attributes:
        content: Text content of the response
        tool_calls: List of tool calls requested by the LLM
        finish_reason: Why the response ended (stop, tool_calls, length, etc.)
    """

    content: Optional[str] = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: Optional[str] = None

    @property
    def has_tool_calls(self) -> bool:
        """Check if the response contains tool calls."""
        return len(self.tool_calls) > 0

    @property
    def is_complete(self) -> bool:
        """Check if this is a complete response (no more tool calls needed)."""
        return not self.has_tool_calls


@dataclass(slots=True)
class StreamChunk:
    """
    A chunk of streamed response from an LLM.

    Used for real-time streaming of responses.
    """

    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    is_complete: bool = False
    finish_reason: Optional[str] = None
