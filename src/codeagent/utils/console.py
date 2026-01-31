"""Console output utilities - Claude Code style UI."""

import os
import random
import sys
import threading
import time
from typing import Optional

from rich.console import Console as RichConsole
from rich.panel import Panel
from rich.text import Text
from prompt_toolkit import prompt
from prompt_toolkit.styles import Style as PTStyle


# Words that appear during "thinking" - like Claude Code
THINKING_WORDS = [
    "Analyzing", "Reading", "Thinking", "Processing", "Understanding",
    "Examining", "Reviewing", "Checking", "Scanning", "Parsing",
    "Evaluating", "Considering", "Exploring", "Investigating", "Searching",
]


class Console:
    """
    Claude Code style console output.

    - Input box with `>` prompt
    - Thinking indicator with random words
    - Tool calls shown with dimmed text
    - Clean output
    """

    def __init__(self) -> None:
        self._console = RichConsole(highlight=False)
        self._thinking = False
        self._think_thread: Optional[threading.Thread] = None

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

    def start_thinking(self) -> None:
        """Start the thinking indicator."""
        self._thinking = True
        self._think_thread = threading.Thread(target=self._think_loop, daemon=True)
        self._think_thread.start()

    def stop_thinking(self) -> None:
        """Stop the thinking indicator."""
        if self._thinking:
            self._thinking = False
            # Clear the line
            sys.stdout.write("\r\033[K")
            sys.stdout.flush()
            if self._think_thread:
                self._think_thread.join(timeout=0.3)

    def _think_loop(self) -> None:
        """Show cycling thinking words."""
        while self._thinking:
            word = random.choice(THINKING_WORDS)
            # Use raw stdout to avoid Rich formatting issues
            sys.stdout.write(f"\r\033[2m{word}...\033[0m")
            sys.stdout.flush()
            time.sleep(0.5)
            if self._thinking:
                sys.stdout.write("\r\033[K")  # Clear line
                sys.stdout.flush()
                time.sleep(0.1)

    def assistant_start(self) -> None:
        """Start assistant response - stop thinking indicator."""
        self.stop_thinking()

    def assistant_stream(self, chunk: str) -> None:
        """Stream output directly."""
        sys.stdout.write(chunk)
        sys.stdout.flush()

    def assistant_end(self) -> None:
        """End response with newlines."""
        sys.stdout.write("\n\n")
        sys.stdout.flush()

    def tool_start(self, tool_name: str, args: dict) -> None:
        """Show tool execution - Claude Code style with dimmed text."""
        self.stop_thinking()  # Stop thinking when tool starts

        # Use ANSI dim code for consistent output
        dim = "\033[2m"
        reset = "\033[0m"

        if tool_name == "read_file":
            path = args.get("file_path", "")
            path = self._shorten_path(path)
            print(f"{dim}Read {path}{reset}")

        elif tool_name == "write_file":
            path = args.get("file_path", "")
            path = self._shorten_path(path)
            print(f"{dim}Write {path}{reset}")

        elif tool_name == "edit_file":
            path = args.get("file_path", "")
            path = self._shorten_path(path)
            print(f"{dim}Edit {path}{reset}")

        elif tool_name == "bash":
            cmd = args.get("command", "")
            if len(cmd) > 60:
                cmd = cmd[:60] + "..."
            print(f"{dim}$ {cmd}{reset}")

        elif tool_name == "grep":
            pattern = args.get("pattern", "")
            print(f"{dim}Grep {pattern}{reset}")

        elif tool_name == "glob":
            pattern = args.get("pattern", "")
            print(f"{dim}Glob {pattern}{reset}")

        else:
            print(f"{dim}{tool_name}{reset}")

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
        """Show tool result - only errors."""
        if is_error:
            first_line = result.split("\n")[0]
            if len(first_line) > 80:
                first_line = first_line[:80] + "..."
            print(f"\033[31m{first_line}\033[0m")  # Red

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
