"""File writing tool."""

import os
from pathlib import Path
from typing import Any, Callable, Optional

from codeagent.core.exceptions import ToolExecutionError
from codeagent.tools.base import Tool, ToolParameter


# Global callback for diff display - set by CLI
_diff_callback: Optional[Callable[[str, Optional[str], str], None]] = None


def set_diff_callback(callback: Optional[Callable[[str, Optional[str], str], None]]) -> None:
    """Set the callback for displaying diffs. Callback receives (file_path, old_content, new_content)."""
    global _diff_callback
    _diff_callback = callback


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
        working_dir: str | None = None,
        **kwargs: Any,
    ) -> str:
        """
        Write content to a file.

        Args:
            file_path: Path to write to
            content: Content to write
            working_dir: Working directory for resolving relative paths

        Returns:
            Success message
        """
        path = Path(file_path).expanduser()

        # Resolve relative paths against working directory
        if not path.is_absolute():
            if working_dir:
                path = Path(working_dir) / path
            else:
                path = Path.cwd() / path

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

            # Read old content for diff display
            old_content = None
            if not is_new:
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        old_content = f.read()
                except Exception:
                    pass

            # Display diff if callback is set
            if _diff_callback:
                try:
                    _diff_callback(str(path), old_content, content)
                except Exception:
                    pass  # Don't fail on diff display errors

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
