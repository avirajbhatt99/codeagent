"""
Custom exceptions for CodeAgent.

Follows the principle of creating specific exception types
for different error categories to enable proper error handling.
"""


class CodeAgentError(Exception):
    """Base exception for all CodeAgent errors."""

    def __init__(self, message: str, *args: object) -> None:
        self.message = message
        super().__init__(message, *args)


class ProviderError(CodeAgentError):
    """Errors related to LLM providers."""

    pass


class ProviderNotFoundError(ProviderError):
    """Raised when a requested provider is not available."""

    def __init__(self, provider: str) -> None:
        super().__init__(f"Provider '{provider}' is not available")
        self.provider = provider


class ProviderConfigError(ProviderError):
    """Raised when provider configuration is invalid."""

    def __init__(self, provider: str, reason: str) -> None:
        super().__init__(f"Invalid configuration for '{provider}': {reason}")
        self.provider = provider
        self.reason = reason


class ModelNotFoundError(ProviderError):
    """Raised when a requested model is not available."""

    def __init__(self, model: str, provider: str) -> None:
        super().__init__(f"Model '{model}' not found for provider '{provider}'")
        self.model = model
        self.provider = provider


class APIError(ProviderError):
    """Raised when an API call fails."""

    def __init__(self, provider: str, message: str, status_code: int | None = None) -> None:
        super().__init__(f"API error from '{provider}': {message}")
        self.provider = provider
        self.status_code = status_code


class ToolError(CodeAgentError):
    """Errors related to tools."""

    pass


class ToolNotFoundError(ToolError):
    """Raised when a requested tool is not registered."""

    def __init__(self, tool_name: str) -> None:
        super().__init__(f"Tool '{tool_name}' is not registered")
        self.tool_name = tool_name


class ToolExecutionError(ToolError):
    """Raised when a tool execution fails."""

    def __init__(self, tool_name: str, reason: str) -> None:
        super().__init__(f"Tool '{tool_name}' failed: {reason}")
        self.tool_name = tool_name
        self.reason = reason


class AgentError(CodeAgentError):
    """Errors related to the agent loop."""

    pass


class MaxIterationsError(AgentError):
    """Raised when the agent exceeds maximum iterations."""

    def __init__(self, max_iterations: int) -> None:
        super().__init__(f"Agent exceeded maximum iterations ({max_iterations})")
        self.max_iterations = max_iterations


class ConfigError(CodeAgentError):
    """Errors related to configuration."""

    pass
