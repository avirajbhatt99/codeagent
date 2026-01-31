"""Glob tool for finding files by pattern."""

import os
from pathlib import Path
from typing import Any

from codeagent.core.exceptions import ToolExecutionError
from codeagent.tools.base import Tool, ToolParameter


class GlobTool(Tool):
    """Tool for finding files using glob patterns."""

    # Directories to ignore
    DEFAULT_IGNORE = [
        "__pycache__",
        ".git",
        ".svn",
        ".hg",
        "node_modules",
        ".venv",
        "venv",
        ".env",
        "dist",
        "build",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "*.egg-info",
    ]

    @property
    def name(self) -> str:
        return "glob"

    @property
    def description(self) -> str:
        return (
            "Find files matching a glob pattern. "
            "Use patterns like '**/*.py' for all Python files, "
            "'src/**/*.ts' for TypeScript files in src, "
            "or '*.json' for JSON files in current directory."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="pattern",
                type="string",
                description="Glob pattern to match (e.g., '**/*.py', 'src/*.ts')",
                required=True,
            ),
            ToolParameter(
                name="path",
                type="string",
                description="Base directory to search from (default: current directory)",
                required=False,
            ),
            ToolParameter(
                name="max_results",
                type="integer",
                description="Maximum number of files to return",
                required=False,
                default=100,
            ),
            ToolParameter(
                name="include_hidden",
                type="boolean",
                description="Include hidden files (starting with .)",
                required=False,
                default=False,
            ),
        ]

    def execute(
        self,
        pattern: str,
        path: str | None = None,
        max_results: int = 100,
        include_hidden: bool = False,
        **kwargs: Any,
    ) -> str:
        """
        Find files matching a glob pattern.

        Args:
            pattern: Glob pattern to match
            path: Base directory
            max_results: Maximum files to return
            include_hidden: Include hidden files

        Returns:
            List of matching file paths
        """
        base_path = Path(path).expanduser() if path else Path.cwd()

        if not base_path.exists():
            raise ToolExecutionError(
                self.name,
                f"Directory not found: {base_path}",
            )

        if not base_path.is_dir():
            raise ToolExecutionError(
                self.name,
                f"Not a directory: {base_path}",
            )

        try:
            matches = []
            for match in base_path.glob(pattern):
                # Skip ignored directories
                if self._should_ignore(match):
                    continue

                # Skip hidden files unless requested
                if not include_hidden and self._is_hidden(match, base_path):
                    continue

                # Only include files, not directories
                if match.is_file():
                    # Get relative path for cleaner output
                    try:
                        rel_path = match.relative_to(base_path)
                        matches.append(str(rel_path))
                    except ValueError:
                        matches.append(str(match))

                if len(matches) >= max_results:
                    break

            if not matches:
                return f"No files found matching pattern: {pattern}"

            # Sort for consistent output
            matches.sort()

            result = "\n".join(matches)
            if len(matches) == max_results:
                result += f"\n\n... (limited to {max_results} results)"

            return result

        except Exception as e:
            raise ToolExecutionError(
                self.name,
                f"Glob search failed: {e}",
            )

    def _should_ignore(self, path: Path) -> bool:
        """Check if path should be ignored."""
        parts = path.parts
        for ignore_pattern in self.DEFAULT_IGNORE:
            if ignore_pattern.startswith("*"):
                # Handle wildcard patterns like *.egg-info
                suffix = ignore_pattern[1:]
                if any(part.endswith(suffix) for part in parts):
                    return True
            else:
                if ignore_pattern in parts:
                    return True
        return False

    def _is_hidden(self, path: Path, base: Path) -> bool:
        """Check if any component of the path (relative to base) is hidden."""
        try:
            rel = path.relative_to(base)
            return any(part.startswith(".") for part in rel.parts)
        except ValueError:
            return path.name.startswith(".")
