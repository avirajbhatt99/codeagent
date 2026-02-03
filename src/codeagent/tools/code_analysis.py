"""Code analysis tools."""

import os
import re
from pathlib import Path
from typing import Any

from codeagent.core.exceptions import ToolExecutionError
from codeagent.tools.base import Tool, ToolParameter


class TreeTool(Tool):
    """Tool for displaying directory structure as a tree."""

    # Directories to ignore by default
    DEFAULT_IGNORE = {
        ".git",
        ".svn",
        ".hg",
        "__pycache__",
        "node_modules",
        ".venv",
        "venv",
        ".env",
        "env",
        ".tox",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "dist",
        "build",
        ".eggs",
        "*.egg-info",
        ".coverage",
        "htmlcov",
        ".idea",
        ".vscode",
        ".DS_Store",
        "Thumbs.db",
    }

    def __init__(self, max_depth: int = 5, max_files: int = 500) -> None:
        """Initialize the tree tool."""
        self._max_depth = max_depth
        self._max_files = max_files

    @property
    def name(self) -> str:
        return "tree"

    @property
    def description(self) -> str:
        return (
            "Display directory structure as a tree. Shows files and folders "
            "in a hierarchical format. Useful for understanding project layout. "
            "Automatically ignores common directories like node_modules, .git, __pycache__."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="path",
                type="string",
                description="Directory path to display (default: current directory)",
                required=False,
                default=".",
            ),
            ToolParameter(
                name="max_depth",
                type="integer",
                description="Maximum depth to traverse (default: 5, max: 10)",
                required=False,
                default=5,
            ),
            ToolParameter(
                name="show_hidden",
                type="boolean",
                description="Show hidden files and directories (default: false)",
                required=False,
                default=False,
            ),
        ]

    def _should_ignore(self, name: str, show_hidden: bool) -> bool:
        """Check if a file/directory should be ignored."""
        if not show_hidden and name.startswith('.'):
            return True
        return name in self.DEFAULT_IGNORE or any(
            name.endswith(pattern.lstrip('*'))
            for pattern in self.DEFAULT_IGNORE
            if pattern.startswith('*')
        )

    def _build_tree(
        self,
        path: Path,
        prefix: str,
        depth: int,
        max_depth: int,
        show_hidden: bool,
        file_count: list[int],  # Mutable counter
    ) -> list[str]:
        """Recursively build tree structure."""
        if depth > max_depth or file_count[0] >= self._max_files:
            return []

        lines: list[str] = []

        try:
            entries = sorted(path.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            return [f"{prefix}[permission denied]"]

        # Filter entries
        entries = [e for e in entries if not self._should_ignore(e.name, show_hidden)]

        for i, entry in enumerate(entries):
            if file_count[0] >= self._max_files:
                lines.append(f"{prefix}... (truncated, max files reached)")
                break

            file_count[0] += 1
            is_last = i == len(entries) - 1
            connector = "└── " if is_last else "├── "
            extension = "    " if is_last else "│   "

            if entry.is_dir():
                lines.append(f"{prefix}{connector}{entry.name}/")
                lines.extend(
                    self._build_tree(
                        entry,
                        prefix + extension,
                        depth + 1,
                        max_depth,
                        show_hidden,
                        file_count,
                    )
                )
            else:
                lines.append(f"{prefix}{connector}{entry.name}")

        return lines

    def execute(
        self,
        path: str = ".",
        max_depth: int = 5,
        show_hidden: bool = False,
        working_dir: str | None = None,
        **kwargs: Any,
    ) -> str:
        """
        Display directory structure as a tree.

        Args:
            path: Directory to display
            max_depth: Maximum depth to traverse
            show_hidden: Whether to show hidden files

        Returns:
            Tree structure as a string
        """
        # Resolve path
        if working_dir and not os.path.isabs(path):
            full_path = Path(working_dir) / path
        else:
            full_path = Path(path)

        full_path = full_path.resolve()

        if not full_path.exists():
            raise ToolExecutionError(self.name, f"Path does not exist: {path}")

        if not full_path.is_dir():
            raise ToolExecutionError(self.name, f"Path is not a directory: {path}")

        effective_depth = min(max_depth, 10)
        file_count = [0]

        lines = [f"{full_path.name}/"]
        lines.extend(
            self._build_tree(full_path, "", 1, effective_depth, show_hidden, file_count)
        )

        result = "\n".join(lines)
        if file_count[0] >= self._max_files:
            result += f"\n\n(Showing {self._max_files} of potentially more entries)"

        return result


class FindSymbolTool(Tool):
    """Tool for finding function/class definitions in code."""

    # Language-specific patterns for finding definitions
    PATTERNS = {
        ".py": [
            (r"^\s*(async\s+)?def\s+{symbol}\s*\(", "function"),
            (r"^\s*class\s+{symbol}\s*[:\(]", "class"),
            (r"^\s*{symbol}\s*=", "variable"),
        ],
        ".js": [
            (r"^\s*(async\s+)?function\s+{symbol}\s*\(", "function"),
            (r"^\s*(const|let|var)\s+{symbol}\s*=\s*(async\s+)?\(", "arrow function"),
            (r"^\s*(const|let|var)\s+{symbol}\s*=\s*function", "function expression"),
            (r"^\s*class\s+{symbol}\s*(\s+extends|\{{)", "class"),
            (r"^\s*(export\s+)?(const|let|var)\s+{symbol}\s*=", "variable"),
        ],
        ".ts": [
            (r"^\s*(async\s+)?function\s+{symbol}\s*[<\(]", "function"),
            (r"^\s*(const|let|var)\s+{symbol}\s*=\s*(async\s+)?\(", "arrow function"),
            (r"^\s*(export\s+)?class\s+{symbol}\s*[<\{\s]", "class"),
            (r"^\s*(export\s+)?interface\s+{symbol}\s*[<\{]", "interface"),
            (r"^\s*(export\s+)?type\s+{symbol}\s*[<=]", "type"),
            (r"^\s*(export\s+)?(const|let|var)\s+{symbol}\s*[=:]", "variable"),
        ],
        ".tsx": [
            (r"^\s*(async\s+)?function\s+{symbol}\s*[<\(]", "function"),
            (r"^\s*(const|let|var)\s+{symbol}\s*=\s*(async\s+)?\(", "arrow function"),
            (r"^\s*(export\s+)?class\s+{symbol}\s*[<\{\s]", "class"),
            (r"^\s*(export\s+)?interface\s+{symbol}\s*[<\{]", "interface"),
            (r"^\s*(export\s+)?type\s+{symbol}\s*[<=]", "type"),
            (r"^\s*(export\s+)?(const|let|var)\s+{symbol}\s*[=:]", "variable/component"),
        ],
        ".go": [
            (r"^\s*func\s+{symbol}\s*\(", "function"),
            (r"^\s*func\s+\([^)]+\)\s+{symbol}\s*\(", "method"),
            (r"^\s*type\s+{symbol}\s+struct\s*\{{", "struct"),
            (r"^\s*type\s+{symbol}\s+interface\s*\{{", "interface"),
            (r"^\s*type\s+{symbol}\s+", "type"),
        ],
        ".rs": [
            (r"^\s*(pub\s+)?fn\s+{symbol}\s*[<\(]", "function"),
            (r"^\s*(pub\s+)?struct\s+{symbol}\s*[<\{]", "struct"),
            (r"^\s*(pub\s+)?enum\s+{symbol}\s*[<\{]", "enum"),
            (r"^\s*(pub\s+)?trait\s+{symbol}\s*[<\{]", "trait"),
            (r"^\s*(pub\s+)?type\s+{symbol}\s*[<=]", "type alias"),
        ],
        ".java": [
            (r"^\s*(public|private|protected)?\s*(static\s+)?\w+\s+{symbol}\s*\(", "method"),
            (r"^\s*(public|private|protected)?\s*(abstract\s+)?class\s+{symbol}\s*[<\{]", "class"),
            (r"^\s*(public|private|protected)?\s*interface\s+{symbol}\s*[<\{]", "interface"),
            (r"^\s*(public|private|protected)?\s*enum\s+{symbol}\s*\{{", "enum"),
        ],
        ".rb": [
            (r"^\s*def\s+{symbol}\s*[\(\n]", "method"),
            (r"^\s*class\s+{symbol}\s*[<\n]", "class"),
            (r"^\s*module\s+{symbol}\s*\n", "module"),
        ],
    }

    # Directories to skip
    SKIP_DIRS = {
        ".git", "node_modules", "__pycache__", ".venv", "venv",
        "dist", "build", ".tox", ".pytest_cache", ".mypy_cache",
    }

    @property
    def name(self) -> str:
        return "find_symbol"

    @property
    def description(self) -> str:
        return (
            "Find where a function, class, or variable is defined in the codebase. "
            "Searches through source files and returns file paths with line numbers. "
            "Supports Python, JavaScript/TypeScript, Go, Rust, Java, and Ruby."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="symbol",
                type="string",
                description="The name of the function, class, or variable to find",
                required=True,
            ),
            ToolParameter(
                name="path",
                type="string",
                description="Directory to search in (default: current directory)",
                required=False,
                default=".",
            ),
            ToolParameter(
                name="file_types",
                type="string",
                description="Comma-separated file extensions to search (e.g., '.py,.js'). Default: all supported types",
                required=False,
            ),
        ]

    def _search_file(
        self,
        file_path: Path,
        symbol: str,
        patterns: list[tuple[str, str]],
    ) -> list[tuple[int, str, str]]:
        """Search a file for symbol definitions."""
        results = []

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line_num, line in enumerate(f, 1):
                    for pattern_template, def_type in patterns:
                        pattern = pattern_template.format(symbol=re.escape(symbol))
                        if re.match(pattern, line):
                            results.append((line_num, def_type, line.strip()))
        except (OSError, IOError):
            pass

        return results

    def execute(
        self,
        symbol: str,
        path: str = ".",
        file_types: str | None = None,
        working_dir: str | None = None,
        **kwargs: Any,
    ) -> str:
        """
        Find symbol definitions in the codebase.

        Args:
            symbol: The symbol to find
            path: Directory to search
            file_types: File extensions to search

        Returns:
            List of locations where the symbol is defined
        """
        # Resolve path
        if working_dir and not os.path.isabs(path):
            search_path = Path(working_dir) / path
        else:
            search_path = Path(path)

        search_path = search_path.resolve()

        if not search_path.exists():
            raise ToolExecutionError(self.name, f"Path does not exist: {path}")

        # Determine which file types to search
        if file_types:
            extensions = [ext.strip() if ext.startswith('.') else f".{ext.strip()}"
                          for ext in file_types.split(',')]
            patterns_to_use = {ext: self.PATTERNS.get(ext, []) for ext in extensions}
        else:
            patterns_to_use = self.PATTERNS

        # Search for the symbol
        findings: list[str] = []
        files_searched = 0
        max_files = 5000

        for root, dirs, files in os.walk(search_path):
            # Skip ignored directories
            dirs[:] = [d for d in dirs if d not in self.SKIP_DIRS]

            for filename in files:
                if files_searched >= max_files:
                    break

                ext = Path(filename).suffix
                if ext not in patterns_to_use or not patterns_to_use[ext]:
                    continue

                files_searched += 1
                file_path = Path(root) / filename
                results = self._search_file(file_path, symbol, patterns_to_use[ext])

                for line_num, def_type, line_content in results:
                    rel_path = file_path.relative_to(search_path)
                    findings.append(
                        f"{rel_path}:{line_num} ({def_type})\n  {line_content}"
                    )

        if not findings:
            return f"No definitions found for '{symbol}' in {search_path}"

        result = f"Found {len(findings)} definition(s) for '{symbol}':\n\n"
        result += "\n\n".join(findings)

        return result


class CodeStatsTool(Tool):
    """Tool for getting code statistics."""

    # File extensions for different languages
    LANGUAGES = {
        "Python": [".py", ".pyw", ".pyi"],
        "JavaScript": [".js", ".mjs", ".cjs"],
        "TypeScript": [".ts", ".tsx"],
        "Java": [".java"],
        "Go": [".go"],
        "Rust": [".rs"],
        "C/C++": [".c", ".cpp", ".cc", ".cxx", ".h", ".hpp", ".hxx"],
        "C#": [".cs"],
        "Ruby": [".rb"],
        "PHP": [".php"],
        "Swift": [".swift"],
        "Kotlin": [".kt", ".kts"],
        "Scala": [".scala"],
        "HTML": [".html", ".htm"],
        "CSS": [".css", ".scss", ".sass", ".less"],
        "SQL": [".sql"],
        "Shell": [".sh", ".bash", ".zsh"],
        "YAML": [".yaml", ".yml"],
        "JSON": [".json"],
        "Markdown": [".md", ".markdown"],
        "XML": [".xml"],
    }

    # Directories to skip
    SKIP_DIRS = {
        ".git", "node_modules", "__pycache__", ".venv", "venv",
        "dist", "build", ".tox", ".pytest_cache", ".mypy_cache",
        ".eggs", "htmlcov", ".idea", ".vscode",
    }

    @property
    def name(self) -> str:
        return "code_stats"

    @property
    def description(self) -> str:
        return (
            "Get statistics about the codebase including lines of code, "
            "file counts by language, and project size. "
            "Useful for understanding project scope and composition."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="path",
                type="string",
                description="Directory to analyze (default: current directory)",
                required=False,
                default=".",
            ),
        ]

    def _count_lines(self, file_path: Path) -> tuple[int, int, int]:
        """Count total, code, and blank lines in a file."""
        total = 0
        blank = 0
        code = 0

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    total += 1
                    if line.strip():
                        code += 1
                    else:
                        blank += 1
        except (OSError, IOError):
            pass

        return total, code, blank

    def execute(
        self,
        path: str = ".",
        working_dir: str | None = None,
        **kwargs: Any,
    ) -> str:
        """
        Get code statistics for a directory.

        Args:
            path: Directory to analyze

        Returns:
            Statistics about the codebase
        """
        # Resolve path
        if working_dir and not os.path.isabs(path):
            analyze_path = Path(working_dir) / path
        else:
            analyze_path = Path(path)

        analyze_path = analyze_path.resolve()

        if not analyze_path.exists():
            raise ToolExecutionError(self.name, f"Path does not exist: {path}")

        if not analyze_path.is_dir():
            raise ToolExecutionError(self.name, f"Path is not a directory: {path}")

        # Build extension to language mapping
        ext_to_lang: dict[str, str] = {}
        for lang, extensions in self.LANGUAGES.items():
            for ext in extensions:
                ext_to_lang[ext] = lang

        # Collect statistics
        stats: dict[str, dict[str, int]] = {}
        total_files = 0
        total_lines = 0
        total_code_lines = 0
        total_blank_lines = 0
        total_size = 0

        for root, dirs, files in os.walk(analyze_path):
            # Skip ignored directories
            dirs[:] = [d for d in dirs if d not in self.SKIP_DIRS]

            for filename in files:
                file_path = Path(root) / filename
                ext = file_path.suffix.lower()

                if ext not in ext_to_lang:
                    continue

                lang = ext_to_lang[ext]
                if lang not in stats:
                    stats[lang] = {"files": 0, "lines": 0, "code": 0, "blank": 0, "size": 0}

                lines, code, blank = self._count_lines(file_path)
                size = file_path.stat().st_size

                stats[lang]["files"] += 1
                stats[lang]["lines"] += lines
                stats[lang]["code"] += code
                stats[lang]["blank"] += blank
                stats[lang]["size"] += size

                total_files += 1
                total_lines += lines
                total_code_lines += code
                total_blank_lines += blank
                total_size += size

        if not stats:
            return f"No source files found in {analyze_path}"

        # Format output
        result_lines = [
            f"Code Statistics for: {analyze_path.name}/",
            "=" * 60,
            "",
        ]

        # Sort by lines of code
        sorted_langs = sorted(stats.items(), key=lambda x: x[1]["code"], reverse=True)

        # Header
        result_lines.append(f"{'Language':<15} {'Files':>8} {'Lines':>10} {'Code':>10} {'Blank':>8}")
        result_lines.append("-" * 60)

        for lang, data in sorted_langs:
            result_lines.append(
                f"{lang:<15} {data['files']:>8} {data['lines']:>10} {data['code']:>10} {data['blank']:>8}"
            )

        result_lines.append("-" * 60)
        result_lines.append(
            f"{'TOTAL':<15} {total_files:>8} {total_lines:>10} {total_code_lines:>10} {total_blank_lines:>8}"
        )

        result_lines.append("")
        result_lines.append(f"Total size: {self._format_size(total_size)}")

        return "\n".join(result_lines)

    def _format_size(self, size: int) -> str:
        """Format size in human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
