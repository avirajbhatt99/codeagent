"""
Base classes for tools.

Implements the Command pattern with a Registry for tool management.
Tools are self-describing, making it easy to generate schemas for LLMs.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, TypeVar

from codeagent.core.exceptions import ToolExecutionError, ToolNotFoundError
from codeagent.core.types import ToolResult


@dataclass(frozen=True)
class ToolParameter:
    """Definition of a tool parameter."""

    name: str
    type: str  # JSON Schema type
    description: str
    required: bool = True
    default: Any = None
    enum: Optional[list[Any]] = None


@dataclass
class ToolDefinition:
    """Complete definition of a tool for schema generation."""

    name: str
    description: str
    parameters: list[ToolParameter] = field(default_factory=list)

    def to_openai_schema(self) -> dict[str, Any]:
        """Convert to OpenAI function calling format."""
        properties: dict[str, Any] = {}
        required: list[str] = []

        for param in self.parameters:
            prop: dict[str, Any] = {
                "type": param.type,
                "description": param.description,
            }
            if param.enum:
                prop["enum"] = param.enum

            properties[param.name] = prop

            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }


class Tool(ABC):
    """
    Abstract base class for tools.

    Tools are self-describing commands that can be executed by the agent.
    Each tool defines its name, description, parameters, and execution logic.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for the tool."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what the tool does."""
        pass

    @property
    def parameters(self) -> list[ToolParameter]:
        """List of parameters the tool accepts. Override to define parameters."""
        return []

    def get_definition(self) -> ToolDefinition:
        """Get the complete tool definition."""
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
        )

    def get_schema(self) -> dict[str, Any]:
        """Get OpenAI-compatible tool schema."""
        return self.get_definition().to_openai_schema()

    @abstractmethod
    def execute(self, **kwargs: Any) -> str:
        """
        Execute the tool with the given arguments.

        Args:
            **kwargs: Tool-specific arguments

        Returns:
            String result of the execution

        Raises:
            ToolExecutionError: If execution fails
        """
        pass

    def safe_execute(self, tool_call_id: str, **kwargs: Any) -> ToolResult:
        """
        Execute the tool safely, catching exceptions.

        Args:
            tool_call_id: ID of the tool call
            **kwargs: Tool-specific arguments

        Returns:
            ToolResult with success or error information
        """
        try:
            result = self.execute(**kwargs)
            return ToolResult(
                tool_call_id=tool_call_id,
                content=result,
                is_error=False,
            )
        except ToolExecutionError as e:
            return ToolResult(
                tool_call_id=tool_call_id,
                content=f"Error: {e.reason}",
                is_error=True,
            )
        except Exception as e:
            return ToolResult(
                tool_call_id=tool_call_id,
                content=f"Unexpected error: {e}",
                is_error=True,
            )


class ToolRegistry:
    """
    Registry for managing tools.

    Implements the Registry pattern for tool discovery and management.
    Thread-safe for concurrent access.
    """

    def __init__(self, working_dir: str | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        self._working_dir = working_dir

    def set_working_dir(self, working_dir: str) -> None:
        """Set the working directory for tool execution."""
        self._working_dir = working_dir

    def register(self, tool: Tool) -> None:
        """
        Register a tool.

        Args:
            tool: Tool instance to register

        Raises:
            ValueError: If a tool with the same name is already registered
        """
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        """
        Unregister a tool by name.

        Args:
            name: Name of the tool to remove
        """
        self._tools.pop(name, None)

    def get(self, name: str) -> Tool:
        """
        Get a tool by name.

        Args:
            name: Name of the tool

        Returns:
            The tool instance

        Raises:
            ToolNotFoundError: If tool is not found
        """
        if name not in self._tools:
            raise ToolNotFoundError(name)
        return self._tools[name]

    def has(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools

    def list_tools(self) -> list[str]:
        """Get list of registered tool names."""
        return list(self._tools.keys())

    def get_all_schemas(self) -> list[dict[str, Any]]:
        """Get OpenAI-compatible schemas for all registered tools."""
        return [tool.get_schema() for tool in self._tools.values()]

    def execute(self, name: str, tool_call_id: str, **kwargs: Any) -> ToolResult:
        """
        Execute a tool by name.

        Args:
            name: Name of the tool to execute
            tool_call_id: ID of the tool call
            **kwargs: Arguments to pass to the tool

        Returns:
            ToolResult from the execution
        """
        tool = self.get(name)
        # Pass working_dir to tools for resolving relative paths
        if self._working_dir:
            kwargs["working_dir"] = self._working_dir
        return tool.safe_execute(tool_call_id, **kwargs)

    def __len__(self) -> int:
        return len(self._tools)

    def __iter__(self):
        return iter(self._tools.values())
