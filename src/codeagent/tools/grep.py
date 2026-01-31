"""Grep tool for searching file contents."""

import os
import re
import subprocess
from pathlib import Path
from typing import Any

from codeagent.core.exceptions import ToolExecutionError
from codeagent.tools.base import Tool, ToolParameter


class GrepTool(Tool):
    """Tool for searching file contents using patterns."""

    @property
    def name(self) -> str:
        return "grep"

    @property
    def description(self) -> str:
        return (
            "Search for a pattern in files. Returns matching lines with file paths and line numbers. "
            "Supports regular expressions. Use for finding code, function definitions, usages, etc."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="pattern",
                type="string",
                description="The search pattern (regex supported)",
                required=True,
            ),
            ToolParameter(
                name="path",
                type="string",
                description="Directory or file to search in (default: current directory)",
                required=False,
            ),
            ToolParameter(
                name="include",
                type="string",
                description="File pattern to include (e.g., '*.py', '*.js')",
                required=False,
            ),
            ToolParameter(
                name="ignore_case",
                type="boolean",
                description="Case-insensitive search",
                required=False,
                default=False,
            ),
            ToolParameter(
                name="context_lines",
                type="integer",
                description="Number of context lines to show (before and after)",
                required=False,
                default=0,
            ),
            ToolParameter(
                name="max_results",
                type="integer",
                description="Maximum number of results to return",
                required=False,
                default=50,
            ),
        ]

    def execute(
        self,
        pattern: str,
        path: str | None = None,
        include: str | None = None,
        ignore_case: bool = False,
        context_lines: int = 0,
        max_results: int = 50,
        **kwargs: Any,
    ) -> str:
        """
        Search for pattern in files.

        Args:
            pattern: Search pattern (regex)
            path: Directory or file to search
            include: File pattern filter
            ignore_case: Case-insensitive search
            context_lines: Lines of context
            max_results: Maximum results

        Returns:
            Matching lines with file paths and line numbers
        """
        search_path = Path(path).expanduser() if path else Path.cwd()

        if not search_path.exists():
            raise ToolExecutionError(
                self.name,
                f"Path not found: {search_path}",
            )

        # Try to use ripgrep (rg) first, fall back to grep
        try:
            return self._search_with_rg(
                pattern=pattern,
                path=search_path,
                include=include,
                ignore_case=ignore_case,
                context_lines=context_lines,
                max_results=max_results,
            )
        except FileNotFoundError:
            return self._search_with_grep(
                pattern=pattern,
                path=search_path,
                include=include,
                ignore_case=ignore_case,
                context_lines=context_lines,
                max_results=max_results,
            )

    def _search_with_rg(
        self,
        pattern: str,
        path: Path,
        include: str | None,
        ignore_case: bool,
        context_lines: int,
        max_results: int,
    ) -> str:
        """Search using ripgrep."""
        cmd = ["rg", "--line-number", "--no-heading", "--color=never"]

        if ignore_case:
            cmd.append("--ignore-case")

        if context_lines > 0:
            cmd.extend(["-C", str(context_lines)])

        if include:
            cmd.extend(["--glob", include])

        cmd.extend(["--max-count", str(max_results)])
        cmd.append(pattern)
        cmd.append(str(path))

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            output = result.stdout
            if not output:
                return f"No matches found for pattern: {pattern}"

            # Truncate if too long
            lines = output.split("\n")
            if len(lines) > max_results:
                lines = lines[:max_results]
                output = "\n".join(lines) + f"\n\n... (showing first {max_results} results)"

            return output

        except subprocess.TimeoutExpired:
            raise ToolExecutionError(self.name, "Search timed out")

    def _search_with_grep(
        self,
        pattern: str,
        path: Path,
        include: str | None,
        ignore_case: bool,
        context_lines: int,
        max_results: int,
    ) -> str:
        """Fall back to grep if ripgrep not available."""
        cmd = ["grep", "-r", "-n", "--color=never"]

        if ignore_case:
            cmd.append("-i")

        if context_lines > 0:
            cmd.extend(["-C", str(context_lines)])

        if include:
            cmd.extend(["--include", include])

        cmd.append(pattern)
        cmd.append(str(path))

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            output = result.stdout
            if not output:
                return f"No matches found for pattern: {pattern}"

            # Truncate if too long
            lines = output.split("\n")
            if len(lines) > max_results:
                lines = lines[:max_results]
                output = "\n".join(lines) + f"\n\n... (showing first {max_results} results)"

            return output

        except subprocess.TimeoutExpired:
            raise ToolExecutionError(self.name, "Search timed out")
        except FileNotFoundError:
            raise ToolExecutionError(
                self.name,
                "Neither ripgrep (rg) nor grep found. Please install one.",
            )
