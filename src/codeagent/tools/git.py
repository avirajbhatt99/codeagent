"""Git tools for version control operations."""

import subprocess
from pathlib import Path
from typing import Any, Optional

from codeagent.core.exceptions import ToolExecutionError
from codeagent.tools.base import Tool, ToolParameter


def _run_git(args: list[str], cwd: Optional[str] = None, timeout: int = 30) -> tuple[str, str, int]:
    """Run a git command and return stdout, stderr, returncode."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.stdout, result.stderr, result.returncode
    except FileNotFoundError:
        raise ToolExecutionError("git", "Git is not installed or not in PATH")
    except subprocess.TimeoutExpired:
        raise ToolExecutionError("git", f"Git command timed out after {timeout}s")


class GitStatusTool(Tool):
    """Tool for checking git status."""

    @property
    def name(self) -> str:
        return "git_status"

    @property
    def description(self) -> str:
        return "Show the working tree status - modified, staged, and untracked files."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="path",
                type="string",
                description="Path to the git repository (defaults to current directory)",
                required=False,
            ),
        ]

    def execute(self, path: Optional[str] = None, **kwargs: Any) -> str:
        """Get git status."""
        cwd = path or kwargs.get("working_dir", ".")
        stdout, stderr, code = _run_git(["status", "--short", "--branch"], cwd=cwd)

        if code != 0:
            if "not a git repository" in stderr.lower():
                return "Not a git repository"
            raise ToolExecutionError(self.name, stderr.strip())

        if not stdout.strip():
            return "Working tree clean, nothing to commit"
        return stdout.strip()


class GitDiffTool(Tool):
    """Tool for showing git diffs."""

    @property
    def name(self) -> str:
        return "git_diff"

    @property
    def description(self) -> str:
        return "Show changes between commits, working tree, etc. Shows unstaged changes by default."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="path",
                type="string",
                description="Path to the git repository",
                required=False,
            ),
            ToolParameter(
                name="file",
                type="string",
                description="Specific file to diff (optional)",
                required=False,
            ),
            ToolParameter(
                name="staged",
                type="boolean",
                description="Show staged changes instead of unstaged",
                required=False,
            ),
        ]

    def execute(
        self,
        path: Optional[str] = None,
        file: Optional[str] = None,
        staged: bool = False,
        **kwargs: Any
    ) -> str:
        """Get git diff."""
        cwd = path or kwargs.get("working_dir", ".")
        args = ["diff"]

        if staged:
            args.append("--cached")

        if file:
            args.append("--")
            args.append(file)

        stdout, stderr, code = _run_git(args, cwd=cwd)

        if code != 0:
            raise ToolExecutionError(self.name, stderr.strip())

        if not stdout.strip():
            return "No changes" + (" staged" if staged else "")
        return stdout.strip()


class GitLogTool(Tool):
    """Tool for showing git commit history."""

    @property
    def name(self) -> str:
        return "git_log"

    @property
    def description(self) -> str:
        return "Show commit history."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="path",
                type="string",
                description="Path to the git repository",
                required=False,
            ),
            ToolParameter(
                name="count",
                type="integer",
                description="Number of commits to show (default 10)",
                required=False,
            ),
            ToolParameter(
                name="oneline",
                type="boolean",
                description="Show each commit on one line",
                required=False,
            ),
        ]

    def execute(
        self,
        path: Optional[str] = None,
        count: int = 10,
        oneline: bool = True,
        **kwargs: Any
    ) -> str:
        """Get git log."""
        cwd = path or kwargs.get("working_dir", ".")
        args = ["log", f"-{count}"]

        if oneline:
            args.append("--oneline")

        stdout, stderr, code = _run_git(args, cwd=cwd)

        if code != 0:
            if "does not have any commits" in stderr.lower():
                return "No commits yet"
            raise ToolExecutionError(self.name, stderr.strip())

        return stdout.strip() or "No commits"


class GitAddTool(Tool):
    """Tool for staging files."""

    @property
    def name(self) -> str:
        return "git_add"

    @property
    def description(self) -> str:
        return "Stage files for commit."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="files",
                type="string",
                description="Files to stage (space-separated, or '.' for all)",
                required=True,
            ),
            ToolParameter(
                name="path",
                type="string",
                description="Path to the git repository",
                required=False,
            ),
        ]

    def execute(self, files: str, path: Optional[str] = None, **kwargs: Any) -> str:
        """Stage files."""
        cwd = path or kwargs.get("working_dir", ".")
        file_list = files.split()

        stdout, stderr, code = _run_git(["add"] + file_list, cwd=cwd)

        if code != 0:
            raise ToolExecutionError(self.name, stderr.strip())

        return f"Staged: {files}"


class GitCommitTool(Tool):
    """Tool for creating commits."""

    @property
    def name(self) -> str:
        return "git_commit"

    @property
    def description(self) -> str:
        return "Create a commit with staged changes."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="message",
                type="string",
                description="Commit message",
                required=True,
            ),
            ToolParameter(
                name="path",
                type="string",
                description="Path to the git repository",
                required=False,
            ),
        ]

    def execute(self, message: str, path: Optional[str] = None, **kwargs: Any) -> str:
        """Create a commit."""
        cwd = path or kwargs.get("working_dir", ".")

        stdout, stderr, code = _run_git(["commit", "-m", message], cwd=cwd)

        if code != 0:
            if "nothing to commit" in stdout.lower() or "nothing to commit" in stderr.lower():
                return "Nothing to commit"
            raise ToolExecutionError(self.name, stderr.strip() or stdout.strip())

        # Extract commit hash from output
        lines = stdout.strip().split("\n")
        return lines[0] if lines else "Committed"


class GitBranchTool(Tool):
    """Tool for listing and managing branches."""

    @property
    def name(self) -> str:
        return "git_branch"

    @property
    def description(self) -> str:
        return "List branches or create a new branch."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="name",
                type="string",
                description="Name of new branch to create (omit to list branches)",
                required=False,
            ),
            ToolParameter(
                name="path",
                type="string",
                description="Path to the git repository",
                required=False,
            ),
        ]

    def execute(self, name: Optional[str] = None, path: Optional[str] = None, **kwargs: Any) -> str:
        """List or create branches."""
        cwd = path or kwargs.get("working_dir", ".")

        if name:
            # Create new branch
            stdout, stderr, code = _run_git(["branch", name], cwd=cwd)
            if code != 0:
                raise ToolExecutionError(self.name, stderr.strip())
            return f"Created branch: {name}"
        else:
            # List branches
            stdout, stderr, code = _run_git(["branch", "-a"], cwd=cwd)
            if code != 0:
                raise ToolExecutionError(self.name, stderr.strip())
            return stdout.strip() or "No branches"


class GitCheckoutTool(Tool):
    """Tool for switching branches or restoring files."""

    @property
    def name(self) -> str:
        return "git_checkout"

    @property
    def description(self) -> str:
        return "Switch branches or restore working tree files."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="target",
                type="string",
                description="Branch name or commit to checkout",
                required=True,
            ),
            ToolParameter(
                name="create",
                type="boolean",
                description="Create a new branch (-b flag)",
                required=False,
            ),
            ToolParameter(
                name="path",
                type="string",
                description="Path to the git repository",
                required=False,
            ),
        ]

    def execute(
        self,
        target: str,
        create: bool = False,
        path: Optional[str] = None,
        **kwargs: Any
    ) -> str:
        """Checkout branch or commit."""
        cwd = path or kwargs.get("working_dir", ".")
        args = ["checkout"]

        if create:
            args.append("-b")
        args.append(target)

        stdout, stderr, code = _run_git(args, cwd=cwd)

        if code != 0:
            raise ToolExecutionError(self.name, stderr.strip())

        return f"Switched to {'new branch' if create else 'branch'}: {target}"


class GitInitTool(Tool):
    """Tool for initializing a git repository."""

    @property
    def name(self) -> str:
        return "git_init"

    @property
    def description(self) -> str:
        return "Initialize a new git repository."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="path",
                type="string",
                description="Path where to initialize the repository",
                required=False,
            ),
        ]

    def execute(self, path: Optional[str] = None, **kwargs: Any) -> str:
        """Initialize git repository."""
        cwd = path or kwargs.get("working_dir", ".")

        stdout, stderr, code = _run_git(["init"], cwd=cwd)

        if code != 0:
            raise ToolExecutionError(self.name, stderr.strip())

        if "reinitialized" in stdout.lower():
            return f"Reinitialized existing Git repository in {cwd}"
        return f"Initialized empty Git repository in {cwd}"
