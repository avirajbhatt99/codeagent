"""Console output utilities - Claude Code style UI."""

import difflib
import os
import random
import shutil
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console as RichConsole
from rich.panel import Panel
from rich.text import Text
from prompt_toolkit import prompt
from prompt_toolkit.styles import Style as PTStyle


# Fun cooking/action words that appear during "thinking" - like Claude Code's "Sautéing..."
THINKING_WORDS = [
    # Cooking themed (like Claude Code)
    "Sautéing", "Simmering", "Marinating", "Braising", "Whisking",
    "Folding", "Kneading", "Seasoning", "Garnishing", "Plating",
    "Reducing", "Caramelizing", "Infusing", "Tempering", "Blanching",
    # Tech/thinking themed
    "Pondering", "Brewing", "Concocting", "Crafting", "Weaving",
    "Distilling", "Synthesizing", "Composing", "Orchestrating", "Calibrating",
    # Action themed
    "Crunching", "Juggling", "Spinning", "Churning", "Percolating",
]


class StatusBar:
    """
    Persistent status bar at the bottom of the terminal.

    Shows:
    - Current activity (thinking word or tool)
    - Escape hint
    - Elapsed time
    - Token count (if available)
    """

    # ANSI codes
    RESET = "\033[0m"
    DIM = "\033[2m"
    BOLD = "\033[1m"
    SALMON = "\033[38;5;209m"
    SAVE_CURSOR = "\033[s"
    RESTORE_CURSOR = "\033[u"

    def __init__(self):
        self._active = False
        self._thread: Optional[threading.Thread] = None
        self._status_text = ""
        self._start_time: Optional[datetime] = None
        self._token_count = 0
        self._current_todo: Optional[str] = None
        self._lock = threading.Lock()

    def start(self, initial_status: str = "Working", todo: Optional[str] = None) -> None:
        """Start showing the status bar."""
        with self._lock:
            self._active = True
            self._status_text = initial_status
            self._start_time = datetime.now()
            self._current_todo = todo

        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._update_loop, daemon=True)
            self._thread.start()

    def update(self, status: str = None, todo: str = None, tokens: int = None) -> None:
        """Update the status bar content."""
        with self._lock:
            if status is not None:
                self._status_text = status
            if todo is not None:
                self._current_todo = todo
            if tokens is not None:
                self._token_count = tokens

    def stop(self) -> None:
        """Stop and clear the status bar."""
        self._active = False
        if self._thread:
            self._thread.join(timeout=0.3)
        self._clear_status_line()

    def _get_elapsed(self) -> str:
        """Get elapsed time string."""
        if not self._start_time:
            return "0s"
        elapsed = datetime.now() - self._start_time
        total_seconds = int(elapsed.total_seconds())

        if total_seconds < 60:
            return f"{total_seconds}s"
        elif total_seconds < 3600:
            mins = total_seconds // 60
            secs = total_seconds % 60
            return f"{mins}m {secs}s"
        else:
            hours = total_seconds // 3600
            mins = (total_seconds % 3600) // 60
            return f"{hours}h {mins}m"

    def _get_terminal_width(self) -> int:
        """Get terminal width."""
        try:
            return shutil.get_terminal_size().columns
        except Exception:
            return 80

    def _clear_status_line(self) -> None:
        """Clear the status line."""
        width = self._get_terminal_width()
        # Move to bottom, clear line
        sys.stdout.write(f"\r\033[K")
        sys.stdout.flush()

    def _render_status(self) -> str:
        """Render the status bar content."""
        with self._lock:
            status = self._status_text
            todo = self._current_todo
            tokens = self._token_count
            elapsed = self._get_elapsed()

        # Build the status line
        parts = []

        # Main status with asterisk
        parts.append(f"{self.SALMON}✱{self.RESET} {self.SALMON}{status}…{self.RESET}")

        # Controls and stats
        info_parts = ["esc to interrupt"]

        # Elapsed time
        info_parts.append(elapsed)

        # Token count if available
        if tokens > 0:
            if tokens >= 1000:
                token_str = f"↓ {tokens / 1000:.1f}k tokens"
            else:
                token_str = f"↓ {tokens} tokens"
            info_parts.append(token_str)

        parts.append(f"{self.DIM}({' · '.join(info_parts)}){self.RESET}")

        line1 = " ".join(parts)

        # Todo line if present
        if todo:
            line2 = f"\n{self.DIM}└─ ☐ {todo}{self.RESET}"
            return line1 + line2

        return line1

    def _update_loop(self) -> None:
        """Update the status bar periodically."""
        blink_on = True

        while self._active:
            status_line = self._render_status()

            # Toggle asterisk blink
            if blink_on:
                display = status_line
            else:
                display = status_line.replace("✱", "✲", 1)  # Slightly different asterisk

            sys.stdout.write(f"\r\033[K{display}")
            sys.stdout.flush()

            blink_on = not blink_on
            time.sleep(0.5)


class Console:
    """
    Claude Code style console output.

    - Input box with `>` prompt
    - Thinking indicator with random words
    - Tool calls shown with blinking indicator
    - Persistent status bar at bottom
    - Clean output
    """

    def __init__(self) -> None:
        self._console = RichConsole(highlight=False)
        self._thinking = False
        self._think_thread: Optional[threading.Thread] = None
        self._tool_running = False
        self._tool_thread: Optional[threading.Thread] = None
        self._current_tool_line: str = ""
        self._status_bar = StatusBar()
        self._session_start: Optional[datetime] = None
        self._total_tokens = 0

    @property
    def raw(self) -> RichConsole:
        """Access the underlying Rich console."""
        return self._console

    def print(self, *args, **kwargs) -> None:
        """Print to console."""
        self._console.print(*args, **kwargs)

    def user_prompt(self) -> str:
        """Display Claude Code style prompt - simple yellow > on new line."""
        from prompt_toolkit.formatted_text import FormattedText

        # Simple prompt like Claude Code: just ❯ or >
        prompt_text = FormattedText([
            ('bold fg:ansiyellow', '❯ '),
        ])

        try:
            return prompt(prompt_text)
        except (EOFError, KeyboardInterrupt):
            raise

    def start_thinking(self, todo: Optional[str] = None) -> None:
        """Start the thinking indicator with status bar."""
        self._thinking = True
        self._session_start = datetime.now()

        # Start status bar
        word = random.choice(THINKING_WORDS)
        self._status_bar.start(initial_status=word, todo=todo)

        # Start word cycling thread
        self._think_thread = threading.Thread(target=self._think_loop, daemon=True)
        self._think_thread.start()

    def stop_thinking(self) -> None:
        """Stop the thinking indicator."""
        if self._thinking:
            self._thinking = False
            self._status_bar.stop()
            # Clear the line
            sys.stdout.write("\r\033[K")
            sys.stdout.flush()
            if self._think_thread:
                self._think_thread.join(timeout=0.3)

    def _think_loop(self) -> None:
        """Cycle through thinking words and update status bar."""
        while self._thinking:
            word = random.choice(THINKING_WORDS)
            self._status_bar.update(status=word)
            time.sleep(0.8)

    def update_tokens(self, tokens: int) -> None:
        """Update the token count in status bar."""
        self._total_tokens = tokens
        self._status_bar.update(tokens=tokens)

    def assistant_start(self) -> None:
        """Start assistant response - stop thinking and tool indicators."""
        self.stop_thinking()
        self.stop_tool_indicator()

    def assistant_stream(self, chunk: str) -> None:
        """Stream output directly."""
        sys.stdout.write(chunk)
        sys.stdout.flush()

    def assistant_end(self) -> None:
        """End response with newlines."""
        sys.stdout.write("\n\n")
        sys.stdout.flush()

    def _get_tool_display(self, tool_name: str, args: dict) -> tuple[str, str]:
        """
        Get the color and display text for a tool.

        Returns:
            Tuple of (color_code, display_text without bullet)
        """
        reset = "\033[0m"
        bold = "\033[1m"
        dim = "\033[2m"

        # Bullet colors (like Claude Code)
        yellow = "\033[38;5;214m"   # Yellow/orange for file edits
        blue = "\033[38;5;75m"      # Blue for bash/commands
        green = "\033[38;5;78m"     # Green for reads/success
        purple = "\033[38;5;141m"   # Purple for git
        cyan = "\033[38;5;80m"      # Cyan for web/network
        pink = "\033[38;5;211m"     # Pink for search
        orange = "\033[38;5;208m"   # Orange for package managers

        # File operations
        if tool_name == "read_file":
            path = args.get("file_path", "")
            path = self._shorten_path(path)
            return green, f"{bold}Read{reset}({dim}{path}{reset})"

        elif tool_name == "write_file":
            path = args.get("file_path", "")
            path = self._shorten_path(path)
            return yellow, f"{bold}Write{reset}({dim}{path}{reset})"

        elif tool_name == "edit_file":
            path = args.get("file_path", "")
            path = self._shorten_path(path)
            return yellow, f"{bold}Update{reset}({dim}{path}{reset})"

        # Shell/bash
        elif tool_name == "bash":
            cmd = args.get("command", "")
            if len(cmd) > 60:
                cmd = cmd[:60] + "..."
            return blue, f"{bold}Bash{reset}({dim}{cmd}{reset})"

        # Search
        elif tool_name == "grep":
            pattern = args.get("pattern", "")
            if len(pattern) > 40:
                pattern = pattern[:40] + "..."
            return pink, f"{bold}Grep{reset}({dim}{pattern}{reset})"

        elif tool_name == "glob":
            pattern = args.get("pattern", "")
            return pink, f"{bold}Glob{reset}({dim}{pattern}{reset})"

        # Git operations
        elif tool_name.startswith("git_"):
            git_cmd = tool_name.replace("git_", "")
            extra = ""
            if git_cmd == "commit":
                msg = args.get("message", "")
                if msg:
                    extra = f": {msg[:30]}..." if len(msg) > 30 else f": {msg}"
            elif git_cmd == "checkout":
                target = args.get("target", "")
                extra = f" {target}" if target else ""
            elif git_cmd == "add":
                files = args.get("files", "")
                extra = f" {files}" if files else ""
            return purple, f"{bold}Git {git_cmd}{reset}{dim}{extra}{reset}"

        # Web operations
        elif tool_name == "web_fetch":
            url = args.get("url", "")
            if len(url) > 45:
                url = url[:45] + "..."
            return cyan, f"{bold}Fetch{reset}({dim}{url}{reset})"

        elif tool_name == "http_request":
            method = args.get("method", "GET")
            url = args.get("url", "")
            if len(url) > 40:
                url = url[:40] + "..."
            return cyan, f"{bold}{method}{reset}({dim}{url}{reset})"

        # Code analysis
        elif tool_name == "tree":
            path = args.get("path", ".")
            return green, f"{bold}Tree{reset}({dim}{path}{reset})"

        elif tool_name == "find_symbol":
            symbol = args.get("symbol", "")
            return pink, f"{bold}Find{reset}({dim}{symbol}{reset})"

        elif tool_name == "code_stats":
            path = args.get("path", ".")
            return green, f"{bold}Stats{reset}({dim}{path}{reset})"

        # Package managers - npm
        elif tool_name.startswith("npm_"):
            action = tool_name.replace("npm_", "")
            packages = args.get("packages", "") or args.get("script", "")
            extra = f" {packages}" if packages else ""
            return orange, f"{bold}npm {action}{reset}{dim}{extra}{reset}"

        # Package managers - pip
        elif tool_name.startswith("pip_"):
            action = tool_name.replace("pip_", "")
            packages = args.get("packages", "")
            extra = f" {packages}" if packages else ""
            return orange, f"{bold}pip {action}{reset}{dim}{extra}{reset}"

        # Package managers - cargo
        elif tool_name.startswith("cargo_"):
            action = tool_name.replace("cargo_", "")
            packages = args.get("packages", "")
            extra = f" {packages}" if packages else ""
            return orange, f"{bold}cargo {action}{reset}{dim}{extra}{reset}"

        # Environment
        elif tool_name.startswith("env_"):
            action = tool_name.replace("env_", "")
            name = args.get("name", "")
            extra = f" {name}" if name else ""
            return cyan, f"{bold}Env {action}{reset}{dim}{extra}{reset}"

        # File operations (delete, copy, move, etc.)
        elif tool_name in ("delete", "copy", "move", "mkdir", "ls"):
            path = args.get("path", "") or args.get("source", "") or args.get("file_path", "")
            path = self._shorten_path(path)
            return yellow, f"{bold}{tool_name.capitalize()}{reset}({dim}{path}{reset})"

        else:
            return blue, f"{bold}{tool_name}{reset}"

    def _tool_blink_loop(self) -> None:
        """Blink the tool indicator while running."""
        reset = "\033[0m"
        blink_on = True

        while self._tool_running:
            if blink_on:
                # Show bullet
                sys.stdout.write(f"\r{self._current_tool_line}")
            else:
                # Dim the bullet (show hollow circle or dimmed)
                # Replace the colored bullet with a dim one
                line = self._current_tool_line
                # Find and replace the bullet with dim version
                dim_line = line.replace("●", "○", 1)
                sys.stdout.write(f"\r{dim_line}")

            sys.stdout.flush()
            blink_on = not blink_on
            time.sleep(0.5)

    def tool_start(self, tool_name: str, args: dict) -> None:
        """Show tool execution with blinking indicator while running."""
        self.stop_thinking()  # Stop thinking when tool starts
        self.stop_tool_indicator()  # Stop any previous tool indicator

        reset = "\033[0m"
        color, display = self._get_tool_display(tool_name, args)

        # Build the full line
        self._current_tool_line = f"{color}●{reset} {display}"

        # Start blinking
        self._tool_running = True
        self._tool_thread = threading.Thread(target=self._tool_blink_loop, daemon=True)
        self._tool_thread.start()

    def stop_tool_indicator(self) -> None:
        """Stop the blinking tool indicator and show final state."""
        if self._tool_running:
            self._tool_running = False
            if self._tool_thread:
                self._tool_thread.join(timeout=0.3)

            # Clear the line and print final state (solid bullet)
            if self._current_tool_line:
                sys.stdout.write(f"\r\033[K{self._current_tool_line}\n")
                sys.stdout.flush()

            self._current_tool_line = ""

    def _shorten_path(self, path: str) -> str:
        """Shorten a file path for display."""
        if not path:
            return path
        # Get relative to cwd if possible
        cwd = os.getcwd()
        if path.startswith(cwd):
            path = path[len(cwd):].lstrip("/")
        elif "/" in path:
            # Show last 2-3 components
            parts = path.split("/")
            if len(parts) > 3:
                path = "/".join(parts[-3:])
        return path

    def tool_result(self, result: str, is_error: bool = False) -> None:
        """Show tool result - stop blinking and show errors."""
        self.stop_tool_indicator()  # Stop blinking when tool finishes

        if is_error:
            first_line = result.split("\n")[0]
            if len(first_line) > 80:
                first_line = first_line[:80] + "..."
            print(f"\033[31m  └─ {first_line}\033[0m")  # Red with indent

    def info(self, message: str) -> None:
        """Print info message."""
        print(f"\033[2m{message}\033[0m")  # Dim

    def success(self, message: str) -> None:
        """Print success message."""
        print(f"\033[32m{message}\033[0m")  # Green

    def warning(self, message: str) -> None:
        """Print warning message."""
        print(f"\033[33m{message}\033[0m")  # Yellow

    def error(self, message: str) -> None:
        """Print error message."""
        print(f"\033[31m{message}\033[0m")  # Red


def create_console() -> Console:
    """Create a new Console instance."""
    return Console()


class DiffDisplay:
    """
    Claude Code style diff display.

    Shows file changes with:
    - Red background for removed lines
    - Green background for added lines
    - Line numbers
    - File path header with summary
    """

    # ANSI color codes for diff display
    RED_BG = "\033[48;5;52m"      # Dark red background for removed
    GREEN_BG = "\033[48;5;22m"    # Dark green background for added
    DIM = "\033[2m"
    RESET = "\033[0m"
    BOLD = "\033[1m"
    YELLOW = "\033[38;5;214m"     # Yellow/orange bullet for updates (like Claude Code)
    GREEN = "\033[38;5;78m"       # Green bullet for creates

    def __init__(self, max_context_lines: int = 3, max_display_lines: int = 50):
        """
        Initialize diff display.

        Args:
            max_context_lines: Number of context lines around changes
            max_display_lines: Maximum lines to display before truncating
        """
        self.max_context_lines = max_context_lines
        self.max_display_lines = max_display_lines

    def show_diff(
        self,
        file_path: str,
        old_content: str,
        new_content: str,
        show_full: bool = False,
    ) -> None:
        """
        Display a diff between old and new content.

        Args:
            file_path: Path to the file being changed
            old_content: Original content
            new_content: New content
            show_full: If True, show all lines, not just changes
        """
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        # Generate unified diff
        diff = list(difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=file_path,
            tofile=file_path,
            lineterm='',
        ))

        if not diff:
            print(f"{self.DIM}No changes{self.RESET}")
            return

        # Count additions and deletions
        added = sum(1 for line in diff if line.startswith('+') and not line.startswith('+++'))
        removed = sum(1 for line in diff if line.startswith('-') and not line.startswith('---'))

        # Print header with yellow bullet (like Claude Code)
        short_path = self._shorten_path(file_path)
        header = f"{self.YELLOW}●{self.RESET} {self.BOLD}Update{self.RESET}({short_path})"

        # Summary
        summary_parts = []
        if added:
            summary_parts.append(f"Added {self.BOLD}{added}{self.RESET}{self.DIM} lines")
        if removed:
            summary_parts.append(f"removed {self.BOLD}{removed}{self.RESET}{self.DIM} lines")

        if summary_parts:
            header += f"\n{self.DIM}└─ {', '.join(summary_parts)}{self.RESET}"

        print(header)

        # Process and display diff lines
        self._display_diff_lines(diff, old_lines, new_lines)
        print()  # Empty line after diff

    def show_edit_diff(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        full_old_content: str,
    ) -> None:
        """
        Display a diff for an edit operation (search/replace).

        Args:
            file_path: Path to the file
            old_string: String being replaced
            new_string: New string
            full_old_content: Full original file content
        """
        # Create the new content
        full_new_content = full_old_content.replace(old_string, new_string, 1)
        self.show_diff(file_path, full_old_content, full_new_content)

    def show_write_diff(
        self,
        file_path: str,
        new_content: str,
        old_content: Optional[str] = None,
    ) -> None:
        """
        Display a diff for a write operation.

        Args:
            file_path: Path to the file
            new_content: Content being written
            old_content: Previous content (if file existed)
        """
        if old_content is None:
            # New file - show as all additions with green bullet
            lines = new_content.count('\n') + (1 if new_content and not new_content.endswith('\n') else 0)
            short_path = self._shorten_path(file_path)
            print(f"{self.GREEN}●{self.RESET} {self.BOLD}Create{self.RESET}({short_path})")
            print(f"{self.DIM}└─ Added {self.BOLD}{lines}{self.RESET}{self.DIM} lines{self.RESET}")

            # Show preview of new file (first few lines)
            preview_lines = new_content.splitlines()[:10]
            for i, line in enumerate(preview_lines, 1):
                line_display = line[:100] + '...' if len(line) > 100 else line
                print(f"{self.GREEN_BG}{i:>4} + {line_display}{self.RESET}")

            if len(new_content.splitlines()) > 10:
                remaining = len(new_content.splitlines()) - 10
                print(f"{self.DIM}     ... +{remaining} more lines{self.RESET}")
            print()
        else:
            self.show_diff(file_path, old_content, new_content)

    def _display_diff_lines(
        self,
        diff: list[str],
        old_lines: list[str],
        new_lines: list[str],
    ) -> None:
        """Display the diff lines with proper formatting."""
        displayed = 0
        old_line_num = 0
        new_line_num = 0
        in_hunk = False
        last_was_context = True

        for line in diff:
            if displayed >= self.max_display_lines:
                remaining = len([l for l in diff if l.startswith('+') or l.startswith('-')])
                print(f"{self.DIM}     ... {remaining} more changes{self.RESET}")
                break

            # Skip diff headers
            if line.startswith('---') or line.startswith('+++'):
                continue

            # Parse hunk header
            if line.startswith('@@'):
                # Extract line numbers from @@ -start,count +start,count @@
                try:
                    parts = line.split()
                    old_info = parts[1]  # -start,count
                    new_info = parts[2]  # +start,count
                    old_line_num = int(old_info.split(',')[0].lstrip('-')) - 1
                    new_line_num = int(new_info.split(',')[0].lstrip('+')) - 1
                except (IndexError, ValueError):
                    pass
                in_hunk = True
                if not last_was_context:
                    print(f"{self.DIM}     ...{self.RESET}")
                continue

            if not in_hunk:
                continue

            # Format line content (remove trailing newline for display)
            content = line[1:].rstrip('\n\r')
            if len(content) > 120:
                content = content[:117] + '...'

            if line.startswith('-'):
                old_line_num += 1
                print(f"{self.RED_BG}{old_line_num:>4} - {content}{self.RESET}")
                displayed += 1
                last_was_context = False
            elif line.startswith('+'):
                new_line_num += 1
                print(f"{self.GREEN_BG}{new_line_num:>4} + {content}{self.RESET}")
                displayed += 1
                last_was_context = False
            else:
                # Context line
                old_line_num += 1
                new_line_num += 1
                print(f"{self.DIM}{new_line_num:>4}   {content}{self.RESET}")
                displayed += 1
                last_was_context = True

    def _shorten_path(self, path: str) -> str:
        """Shorten a file path for display."""
        if not path:
            return path

        # Get relative to cwd if possible
        cwd = os.getcwd()
        if path.startswith(cwd):
            path = path[len(cwd):].lstrip("/")
        elif "/" in path:
            # Show last 2-3 components
            parts = path.split("/")
            if len(parts) > 3:
                path = "/".join(parts[-3:])
        return path


# Global instances
diff_display = DiffDisplay()
status_bar = StatusBar()
