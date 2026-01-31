"""File writing tool."""

import os
from pathlib import Path
from typing import Any

from codeagent.core.exceptions import ToolExecutionError
from codeagent.tools.base import Tool, ToolParameter


class WriteFileTool(Tool):
    """Tool for creating or overwriting files."""

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return (
            "Create a new file or overwrite an existing file with the given content. "
            "Use this for creating new files. For modifying existing files, prefer edit_file."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="file_path",
                type="string",
                description="Absolute path where the file should be written",
                required=True,
            ),
            ToolParameter(
                name="content",
                type="string",
                description="The content to write to the file",
                required=True,
            ),
        ]

    def execute(
        self,
        file_path: str,
        content: str,
        **kwargs: Any,
    ) -> str:
        """
        Write content to a file.

        Args:
            file_path: Path to write to
            content: Content to write

        Returns:
            Success message
        """
        path = Path(file_path).expanduser()

        # Validate path
        if not path.is_absolute():
            raise ToolExecutionError(
                self.name,
                f"Path must be absolute: {file_path}",
            )

        # Check if parent directory exists
        if not path.parent.exists():
            raise ToolExecutionError(
                self.name,
                f"Parent directory does not exist: {path.parent}",
            )

        # Check if it's a directory
        if path.exists() and path.is_dir():
            raise ToolExecutionError(
                self.name,
                f"Cannot write to directory: {file_path}",
            )

        try:
            is_new = not path.exists()
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

            action = "Created" if is_new else "Wrote"
            lines = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
            return f"{action} {file_path} ({lines} lines, {len(content)} bytes)"

        except PermissionError:
            raise ToolExecutionError(
                self.name,
                f"Permission denied: {file_path}",
            )
        except Exception as e:
            raise ToolExecutionError(
                self.name,
                f"Failed to write file: {e}",
            )
