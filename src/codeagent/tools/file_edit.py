"""File editing tool with search and replace."""

import difflib
from pathlib import Path
from typing import Any, Optional

from codeagent.core.exceptions import ToolExecutionError
from codeagent.tools.base import Tool, ToolParameter


def _find_similar_lines(content: str, search: str, max_results: int = 3) -> list[str]:
    """Find lines in content that are similar to the search string."""
    content_lines = content.split('\n')
    search_lines = search.split('\n')
    search_first_line = search_lines[0].strip()

    similar = []
    for i, line in enumerate(content_lines):
        ratio = difflib.SequenceMatcher(None, line.strip(), search_first_line).ratio()
        if ratio > 0.6:  # 60% similar
            similar.append(f"Line {i+1}: {line[:80]}{'...' if len(line) > 80 else ''}")
        if len(similar) >= max_results:
            break

    return similar


class EditFileTool(Tool):
    """Tool for editing files using search and replace."""

    @property
    def name(self) -> str:
        return "edit_file"

    @property
    def description(self) -> str:
        return (
            "Edit a file by replacing a specific string with a new string. "
            "The old_string must match EXACTLY including whitespace and indentation. "
            "For multi-line edits, include enough context to make the match unique. "
            "Always read the file first before editing."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="file_path",
                type="string",
                description="Absolute path to the file to edit",
                required=True,
            ),
            ToolParameter(
                name="old_string",
                type="string",
                description="The exact string to find (must match exactly including whitespace)",
                required=True,
            ),
            ToolParameter(
                name="new_string",
                type="string",
                description="The string to replace old_string with",
                required=True,
            ),
            ToolParameter(
                name="replace_all",
                type="boolean",
                description="If true, replace all occurrences. If false (default), old_string must be unique",
                required=False,
                default=False,
            ),
        ]

    def execute(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
        working_dir: str | None = None,
        **kwargs: Any,
    ) -> str:
        """
        Edit a file by replacing old_string with new_string.

        Args:
            file_path: Path to the file
            old_string: String to find
            new_string: String to replace with
            replace_all: If True, replace all occurrences
            working_dir: Working directory for resolving relative paths

        Returns:
            Success message with replacement count
        """
        path = Path(file_path).expanduser()

        # Resolve relative paths against working directory
        if not path.is_absolute():
            if working_dir:
                path = Path(working_dir) / path
            else:
                path = Path.cwd() / path

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

        # Read current content
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except PermissionError:
            raise ToolExecutionError(
                self.name,
                f"Permission denied reading: {file_path}",
            )
        except Exception as e:
            raise ToolExecutionError(
                self.name,
                f"Failed to read file: {e}",
            )

        # Check if old_string exists
        if old_string not in content:
            # Try to find similar lines to help debug
            similar = _find_similar_lines(content, old_string)

            error_msg = "old_string not found in file."

            if similar:
                error_msg += "\n\nDid you mean one of these?\n" + "\n".join(similar)
            else:
                # Check for common issues
                if old_string.strip() in content:
                    error_msg += "\n\nThe text exists but whitespace doesn't match. Check indentation."
                elif old_string.replace('\n', '') in content.replace('\n', ''):
                    error_msg += "\n\nThe text exists but line breaks don't match."

            raise ToolExecutionError(self.name, error_msg)

        # Count occurrences
        count = content.count(old_string)

        # Validate uniqueness if not replace_all
        if not replace_all and count > 1:
            # Find locations of each occurrence
            lines = content.split('\n')
            occurrences = []
            search_pos = 0
            for i in range(count):
                pos = content.find(old_string, search_pos)
                line_num = content[:pos].count('\n') + 1
                occurrences.append(f"Line {line_num}")
                search_pos = pos + 1

            raise ToolExecutionError(
                self.name,
                f"old_string appears {count} times at: {', '.join(occurrences)}. "
                f"Use replace_all=true or include more context to make it unique.",
            )

        # Check for no-op
        if old_string == new_string:
            raise ToolExecutionError(
                self.name,
                "old_string and new_string are identical. No changes made.",
            )

        # Perform replacement
        if replace_all:
            new_content = content.replace(old_string, new_string)
        else:
            new_content = content.replace(old_string, new_string, 1)

        # Write back
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)
        except PermissionError:
            raise ToolExecutionError(
                self.name,
                f"Permission denied writing: {file_path}",
            )
        except Exception as e:
            raise ToolExecutionError(
                self.name,
                f"Failed to write file: {e}",
            )

        # Calculate diff stats
        old_lines = old_string.count('\n') + 1
        new_lines = new_string.count('\n') + 1
        diff_str = ""
        if old_lines != new_lines:
            diff_str = f" ({'+' if new_lines > old_lines else ''}{new_lines - old_lines} lines)"

        if replace_all:
            return f"Replaced {count} occurrence(s) in {file_path}{diff_str}"
        else:
            return f"Edited {file_path}{diff_str}"
