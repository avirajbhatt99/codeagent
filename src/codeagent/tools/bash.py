"""Bash command execution tool."""

import os
import shlex
import subprocess
from typing import Any

from codeagent.core.exceptions import ToolExecutionError
from codeagent.tools.base import Tool, ToolParameter


class BashTool(Tool):
    """Tool for executing bash commands."""

    # Dangerous command patterns that are blocked
    BLOCKED_PATTERNS = [
        "rm -rf /",
        "rm -rf /*",
        "rm -rf ~",
        "rm -rf $HOME",
        "> /dev/sda",
        "dd if=/dev/zero",
        "mkfs.",
        ":(){:|:&};:",  # Fork bomb
        "chmod -R 777 /",
        "chown -R",
    ]

    # Commands that should be warned about
    DANGEROUS_COMMANDS = [
        "rm -rf",
        "sudo",
        "curl | sh",
        "wget | sh",
        "curl | bash",
        "wget | bash",
    ]

    def __init__(
        self,
        working_dir: str | None = None,
        timeout: int = 120,
        blocked_patterns: list[str] | None = None,
    ) -> None:
        """
        Initialize bash tool.

        Args:
            working_dir: Working directory for commands (default: current dir)
            timeout: Command timeout in seconds
            blocked_patterns: Additional patterns to block
        """
        self._working_dir = working_dir or os.getcwd()
        self._timeout = timeout
        self._blocked = self.BLOCKED_PATTERNS.copy()
        if blocked_patterns:
            self._blocked.extend(blocked_patterns)

    @property
    def name(self) -> str:
        return "bash"

    @property
    def description(self) -> str:
        return (
            "Execute a bash command and return the output. "
            "Use for running builds, tests, git commands, and other shell operations. "
            "Commands run in the project directory."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="command",
                type="string",
                description="The bash command to execute",
                required=True,
            ),
            ToolParameter(
                name="timeout",
                type="integer",
                description="Timeout in seconds (default: 120, max: 600)",
                required=False,
                default=120,
            ),
        ]

    def _is_blocked(self, command: str) -> bool:
        """Check if command matches a blocked pattern."""
        command_lower = command.lower()
        return any(pattern.lower() in command_lower for pattern in self._blocked)

    def _is_dangerous(self, command: str) -> str | None:
        """Check if command is dangerous and return warning if so."""
        command_lower = command.lower()
        for pattern in self.DANGEROUS_COMMANDS:
            if pattern.lower() in command_lower:
                return f"Warning: '{pattern}' detected in command"
        return None

    def execute(
        self,
        command: str,
        timeout: int | None = None,
        **kwargs: Any,
    ) -> str:
        """
        Execute a bash command.

        Args:
            command: The command to run
            timeout: Optional timeout override

        Returns:
            Command output (stdout + stderr)
        """
        # Security check
        if self._is_blocked(command):
            raise ToolExecutionError(
                self.name,
                "Command blocked for safety. This command pattern is not allowed.",
            )

        # Use provided timeout or default, capped at 600 seconds
        effective_timeout = min(timeout or self._timeout, 600)

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=effective_timeout,
                cwd=self._working_dir,
                env={**os.environ, "TERM": "dumb"},  # Disable colors
            )

            output = result.stdout + result.stderr

            # Truncate very long output
            if len(output) > 30000:
                output = output[:30000] + "\n\n... (output truncated)"

            # Include return code if non-zero
            if result.returncode != 0:
                output = f"[Exit code: {result.returncode}]\n\n{output}"

            return output if output.strip() else "(no output)"

        except subprocess.TimeoutExpired:
            raise ToolExecutionError(
                self.name,
                f"Command timed out after {effective_timeout} seconds",
            )
        except Exception as e:
            raise ToolExecutionError(
                self.name,
                f"Command execution failed: {e}",
            )

    def set_working_dir(self, path: str) -> None:
        """Set the working directory for commands."""
        if os.path.isdir(path):
            self._working_dir = path
        else:
            raise ValueError(f"Not a valid directory: {path}")
