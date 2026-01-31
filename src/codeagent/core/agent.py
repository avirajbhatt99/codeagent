"""
Core Agent implementation.

The Agent orchestrates the conversation loop, handling:
- Message management
- Tool execution
- Streaming responses
- Error recovery
"""

import json
import logging
from typing import Any, Callable, Generator, Optional

from codeagent.core.exceptions import AgentError, MaxIterationsError
from codeagent.core.prompts import get_system_prompt
from codeagent.core.types import (
    LLMResponse,
    Message,
    Role,
    StreamChunk,
    ToolCall,
    ToolResult,
)
from codeagent.providers.base import LLMProvider
from codeagent.tools.base import ToolRegistry

logger = logging.getLogger(__name__)


class Agent:
    """
    The core agent that processes user requests using an LLM and tools.

    Implements dependency injection for the provider and tools,
    making it easy to test and configure.
    """

    def __init__(
        self,
        provider: LLMProvider,
        tools: ToolRegistry,
        working_dir: str,
        max_iterations: int = 25,
        on_tool_start: Optional[Callable[[ToolCall], None]] = None,
        on_tool_end: Optional[Callable[[ToolResult], None]] = None,
    ) -> None:
        """
        Initialize the agent.

        Args:
            provider: LLM provider for generating responses
            tools: Registry of available tools
            working_dir: Working directory for the session
            max_iterations: Maximum tool-use iterations per request
            on_tool_start: Callback when a tool starts executing
            on_tool_end: Callback when a tool finishes executing
        """
        self._provider = provider
        self._tools = tools
        self._working_dir = working_dir
        self._max_iterations = max_iterations
        self._on_tool_start = on_tool_start
        self._on_tool_end = on_tool_end

        # Initialize conversation with system prompt
        self._messages: list[Message] = [
            Message.system(get_system_prompt(working_dir))
        ]

    @property
    def provider(self) -> LLMProvider:
        """Get the LLM provider."""
        return self._provider

    @property
    def tools(self) -> ToolRegistry:
        """Get the tool registry."""
        return self._tools

    @property
    def messages(self) -> list[Message]:
        """Get the conversation history."""
        return self._messages.copy()

    def reset(self) -> None:
        """Reset the conversation, keeping only the system message."""
        self._messages = [self._messages[0]]

    def run(self, user_input: str) -> str:
        """
        Process a user message and return the final response.

        This is the main entry point for non-streaming usage.

        Args:
            user_input: The user's message

        Returns:
            The agent's final response

        Raises:
            MaxIterationsError: If max iterations is exceeded
            AgentError: For other agent-related errors
        """
        # Add user message
        self._messages.append(Message.user(user_input))

        final_response = ""

        for iteration in range(self._max_iterations):
            logger.debug(f"Agent iteration {iteration + 1}/{self._max_iterations}")

            # Get LLM response
            response = self._call_llm()

            # If no tool calls, we're done
            if not response.has_tool_calls:
                final_response = response.content or ""
                self._messages.append(Message.assistant(content=final_response))
                break

            # Add assistant message with tool calls
            self._messages.append(
                Message.assistant(
                    content=response.content,
                    tool_calls=response.tool_calls,
                )
            )

            # Execute tools
            for tool_call in response.tool_calls:
                result = self._execute_tool(tool_call)
                self._messages.append(
                    Message.tool_response(
                        tool_call_id=tool_call.id,
                        content=result.content,
                    )
                )

        else:
            # Loop completed without breaking - max iterations reached
            raise MaxIterationsError(self._max_iterations)

        return final_response

    def stream(self, user_input: str) -> Generator[str, None, None]:
        """
        Process a user message with streaming response.

        Yields chunks of the response as they arrive.

        Args:
            user_input: The user's message

        Yields:
            Response chunks as strings

        Raises:
            MaxIterationsError: If max iterations is exceeded
        """
        # Add user message
        self._messages.append(Message.user(user_input))

        for iteration in range(self._max_iterations):
            logger.debug(f"Agent iteration {iteration + 1}/{self._max_iterations}")

            full_content = ""
            tool_calls: list[ToolCall] = []

            # Stream LLM response
            for chunk in self._stream_llm():
                if chunk.content:
                    full_content += chunk.content
                    yield chunk.content

                if chunk.is_complete:
                    tool_calls = chunk.tool_calls

            # If no tool calls, we're done
            if not tool_calls:
                self._messages.append(Message.assistant(content=full_content))
                return

            # Add assistant message with tool calls
            self._messages.append(
                Message.assistant(
                    content=full_content if full_content else None,
                    tool_calls=tool_calls,
                )
            )

            # Execute tools (callbacks handle display)
            for tool_call in tool_calls:
                result = self._execute_tool(tool_call)
                self._messages.append(
                    Message.tool_response(
                        tool_call_id=tool_call.id,
                        content=result.content,
                    )
                )

        else:
            raise MaxIterationsError(self._max_iterations)

    def _call_llm(self) -> LLMResponse:
        """Make a non-streaming LLM call."""
        messages = [m.to_dict() for m in self._messages]
        tools = self._tools.get_all_schemas()

        return self._provider.chat(messages=messages, tools=tools)

    def _stream_llm(self) -> Generator[StreamChunk, None, None]:
        """Make a streaming LLM call."""
        messages = [m.to_dict() for m in self._messages]
        tools = self._tools.get_all_schemas()

        yield from self._provider.stream(messages=messages, tools=tools)

    def _execute_tool(self, tool_call: ToolCall) -> ToolResult:
        """Execute a single tool call."""
        logger.info(f"Executing tool: {tool_call.name}")
        logger.debug(f"Tool arguments: {tool_call.arguments}")

        # Callback for tool start
        if self._on_tool_start:
            self._on_tool_start(tool_call)

        # Execute the tool
        result = self._tools.execute(
            name=tool_call.name,
            tool_call_id=tool_call.id,
            **tool_call.arguments,
        )

        logger.debug(f"Tool result (truncated): {result.content[:200]}")

        # Callback for tool end
        if self._on_tool_end:
            self._on_tool_end(result)

        return result

    def add_message(self, role: Role, content: str) -> None:
        """Add a message to the conversation history."""
        self._messages.append(Message(role=role, content=content))

    def get_conversation_json(self) -> str:
        """Export conversation history as JSON."""
        return json.dumps(
            [m.to_dict() for m in self._messages],
            indent=2,
        )
