"""
Tool permission system.

Mutating tools (file writes, shell commands, destructive git operations,
network requests with side effects) ask the user before running unless
already approved for the session.
"""

from enum import Enum
from typing import Any, Callable, Optional


class PermissionDecision(str, Enum):
    ALLOW_ONCE = "allow_once"
    ALLOW_SESSION = "allow_session"
    DENY = "deny"


# Tools that mutate state or have side effects. Everything else (read_file,
# grep, glob, ls, git_status, git_diff, git_log, tree, find_symbol, code_stats,
# env_get, pip_list, etc.) runs without prompting.
MUTATING_TOOLS: frozenset[str] = frozenset({
    "write_file",
    "edit_file",
    "delete",
    "copy",
    "move",
    "mkdir",
    "bash",
    "git_add",
    "git_commit",
    "git_push",
    "git_pull",
    "git_reset",
    "git_merge",
    "git_checkout",
    "git_stash",
    "git_clone",
    "git_init",
    "git_tag",
    "git_remote",
    "http_request",
    "npm_install",
    "npm_run",
    "pip_install",
    "pip_uninstall",
    "cargo_build",
    "cargo_run",
    "cargo_test",
    "cargo_add",
    "env_set",
    "env_unset",
    "env_load",
})


# Callback signature: (tool_name, arguments) -> PermissionDecision
PermissionPrompt = Callable[[str, dict[str, Any]], PermissionDecision]


class PermissionManager:
    """
    Tracks per-tool session approvals.

    When a mutating tool is invoked, asks via the provided prompt callback
    unless the tool was already approved for the session.
    """

    def __init__(self, prompt: Optional[PermissionPrompt] = None) -> None:
        self._prompt = prompt
        self._session_allowed: set[str] = set()

    def set_prompt(self, prompt: PermissionPrompt) -> None:
        self._prompt = prompt

    def reset(self) -> None:
        self._session_allowed.clear()

    def check(self, tool_name: str, arguments: dict[str, Any]) -> PermissionDecision:
        """Return a decision for this tool call."""
        if tool_name not in MUTATING_TOOLS:
            return PermissionDecision.ALLOW_ONCE
        if tool_name in self._session_allowed:
            return PermissionDecision.ALLOW_ONCE
        if self._prompt is None:
            # No interactive prompt configured (non-interactive use) — allow.
            return PermissionDecision.ALLOW_ONCE

        decision = self._prompt(tool_name, arguments)
        if decision == PermissionDecision.ALLOW_SESSION:
            self._session_allowed.add(tool_name)
        return decision
