"""
TodoWrite tool — in-session task list the model can plan against.

The model passes the full list each call; we replace state and pretty-print
the current state to the console so the user sees the plan evolve.
"""

from __future__ import annotations

import json
from typing import Any

from codeagent.core.exceptions import ToolExecutionError
from codeagent.tools.base import Tool, ToolParameter


VALID_STATUSES = ("pending", "in_progress", "completed")

_STATE: list[dict[str, str]] = []


def _render(items: list[dict[str, str]]) -> str:
    """Render the todo list for the user (printed) and the model (returned)."""
    if not items:
        return "(todo list cleared)"

    icons = {"pending": "☐", "in_progress": "◐", "completed": "☑"}
    lines: list[str] = []
    for item in items:
        status = item.get("status", "pending")
        content = item.get("content", "")
        icon = icons.get(status, "☐")
        if status == "completed":
            lines.append(f"  {icon} \033[2m{content}\033[0m")
        elif status == "in_progress":
            lines.append(f"  \033[38;5;214m{icon}\033[0m \033[1m{content}\033[0m")
        else:
            lines.append(f"  {icon} {content}")
    rendered = "\n".join(lines)
    # Print so the user sees the updated list inline.
    print()
    print(rendered)
    print()
    # Return a plain-text version (no ANSI) for the model.
    plain = "\n".join(
        f"  {icons.get(i.get('status', 'pending'), '☐')} [{i.get('status', 'pending')}] {i.get('content', '')}"
        for i in items
    )
    return f"Todo list updated:\n{plain}"


class TodoWriteTool(Tool):
    """Maintain a structured plan for the current session."""

    @property
    def name(self) -> str:
        return "todo_write"

    @property
    def description(self) -> str:
        return (
            "Maintain a structured todo list for the current task. Pass the FULL "
            "list every call — it replaces the prior state. Use for multi-step work "
            "(3+ steps) to track progress; skip for trivial one-step tasks. "
            "Set exactly one item to 'in_progress' at a time, mark items 'completed' "
            "as soon as they're done. The list is shown to the user after each update."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="todos",
                type="array",
                description=(
                    'Full todo list. Each item: {"content": "short imperative task", '
                    '"status": "pending" | "in_progress" | "completed"}. '
                    'Pass [] to clear.'
                ),
                required=True,
            ),
        ]

    def execute(self, **kwargs: Any) -> str:
        global _STATE
        # working_dir is injected by the registry; ignore it.
        kwargs.pop("working_dir", None)

        todos = kwargs.get("todos")
        if todos is None:
            raise ToolExecutionError(self.name, "missing 'todos' argument")
        if isinstance(todos, str):
            try:
                todos = json.loads(todos)
            except json.JSONDecodeError as e:
                raise ToolExecutionError(self.name, f"todos must be a list, got invalid JSON: {e}")
        if not isinstance(todos, list):
            raise ToolExecutionError(self.name, "todos must be a list")

        cleaned: list[dict[str, str]] = []
        in_progress_count = 0
        for i, item in enumerate(todos):
            if not isinstance(item, dict):
                raise ToolExecutionError(self.name, f"todo #{i} must be an object")
            content = str(item.get("content", "")).strip()
            status = str(item.get("status", "pending")).strip()
            if not content:
                raise ToolExecutionError(self.name, f"todo #{i} has empty content")
            if status not in VALID_STATUSES:
                raise ToolExecutionError(
                    self.name,
                    f"todo #{i} status must be one of {VALID_STATUSES}, got {status!r}",
                )
            if status == "in_progress":
                in_progress_count += 1
            cleaned.append({"content": content, "status": status})

        if in_progress_count > 1:
            raise ToolExecutionError(
                self.name, "only one todo may be 'in_progress' at a time"
            )

        _STATE = cleaned
        return _render(cleaned)


def get_todos() -> list[dict[str, str]]:
    """Read the current todo list (for the CLI to surface in the status bar)."""
    return list(_STATE)


def reset_todos() -> None:
    """Clear todos (called on `clear` command)."""
    global _STATE
    _STATE = []
