"""File reading tool."""

import os
from pathlib import Path
from typing import Any

from codeagent.core.exceptions import ToolExecutionError
from codeagent.tools.base import Tool, ToolParameter


class ReadFileTool(Tool):
    """Tool for reading file contents."""

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return (
            "Read the contents of a file. Returns the file content with line numbers. "
            "Use offset and limit for large files."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="file_path",
                type="string",
                description="Absolute path to the file to read",
                required=True,
            ),
            ToolParameter(
                name="offset",
                type="integer",
                description="Line number to start reading from (0-indexed)",
                required=False,
                default=0,
            ),
            ToolParameter(
                name="limit",
                type="integer",
                description="Maximum number of lines to read",
                required=False,
                default=2000,
            ),
        ]

    def execute(
        self,
        file_path: str,
        offset: int = 0,
        limit: int = 2000,
        **kwargs: Any,
    ) -> str:
        """
        Read file contents with optional offset and limit.

        Args:
            file_path: Path to the file
            offset: Starting line (0-indexed)
            limit: Maximum lines to read

        Returns:
            File contents with line numbers
        """
        path = Path(file_path).expanduser()

        # Validate path
        if not path.is_absolute():
            raise ToolExecutionError(
                self.name,
                f"Path must be absolute: {file_path}",
            )

        if not path.exists():
            raise ToolExecutionError(
                self.name,
                f"File not found: {file_path}",
            )

        if not path.is_file():
            raise ToolExecutionError(
                self.name,
                f"Not a file: {file_path}",
            )

        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except PermissionError:
            raise ToolExecutionError(
                self.name,
                f"Permission denied: {file_path}",
            )
        except Exception as e:
            raise ToolExecutionError(
                self.name,
                f"Failed to read file: {e}",
            )

        # Apply offset and limit
        total_lines = len(lines)
        lines = lines[offset : offset + limit]

        # Format with line numbers
        numbered_lines = []
        for i, line in enumerate(lines):
            line_num = offset + i + 1  # 1-indexed line numbers
            # Truncate very long lines
            if len(line) > 2000:
                line = line[:2000] + "... (truncated)\n"
            numbered_lines.append(f"{line_num:6d}\t{line.rstrip()}")

        result = "\n".join(numbered_lines)

        # Add metadata if truncated
        if offset > 0 or offset + limit < total_lines:
            showing = f"lines {offset + 1}-{min(offset + limit, total_lines)}"
            result = f"[Showing {showing} of {total_lines} total lines]\n\n{result}"

        return result
