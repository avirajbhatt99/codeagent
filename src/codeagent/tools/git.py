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


class GitStashTool(Tool):
    """Tool for stashing changes."""

    @property
    def name(self) -> str:
        return "git_stash"

    @property
    def description(self) -> str:
        return "Stash changes in working directory. Can also list, pop, or apply stashes."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="action",
                type="string",
                description="Action to perform: push (default), pop, apply, list, drop",
                required=False,
                default="push",
                enum=["push", "pop", "apply", "list", "drop"],
            ),
            ToolParameter(
                name="message",
                type="string",
                description="Message for the stash (only for push action)",
                required=False,
            ),
            ToolParameter(
                name="stash_id",
                type="string",
                description="Stash reference like 'stash@{0}' (for pop, apply, drop)",
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
        action: str = "push",
        message: Optional[str] = None,
        stash_id: Optional[str] = None,
        path: Optional[str] = None,
        **kwargs: Any
    ) -> str:
        """Stash operations."""
        cwd = path or kwargs.get("working_dir", ".")

        if action == "push":
            args = ["stash", "push"]
            if message:
                args.extend(["-m", message])
        elif action == "list":
            args = ["stash", "list"]
        elif action in ("pop", "apply", "drop"):
            args = ["stash", action]
            if stash_id:
                args.append(stash_id)
        else:
            raise ToolExecutionError(self.name, f"Unknown action: {action}")

        stdout, stderr, code = _run_git(args, cwd=cwd)

        if code != 0:
            if "No stash entries" in stderr or "No local changes" in stdout:
                return "No stash entries found" if action == "list" else "No local changes to stash"
            raise ToolExecutionError(self.name, stderr.strip() or stdout.strip())

        if action == "list":
            return stdout.strip() if stdout.strip() else "No stash entries"
        elif action == "push":
            return stdout.strip() if stdout.strip() else "Changes stashed"
        else:
            return stdout.strip() if stdout.strip() else f"Stash {action} completed"


class GitPullTool(Tool):
    """Tool for pulling changes from remote."""

    @property
    def name(self) -> str:
        return "git_pull"

    @property
    def description(self) -> str:
        return "Pull changes from remote repository."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="remote",
                type="string",
                description="Remote name (default: origin)",
                required=False,
                default="origin",
            ),
            ToolParameter(
                name="branch",
                type="string",
                description="Branch to pull (default: current branch)",
                required=False,
            ),
            ToolParameter(
                name="rebase",
                type="boolean",
                description="Use rebase instead of merge",
                required=False,
                default=False,
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
        remote: str = "origin",
        branch: Optional[str] = None,
        rebase: bool = False,
        path: Optional[str] = None,
        **kwargs: Any
    ) -> str:
        """Pull from remote."""
        cwd = path or kwargs.get("working_dir", ".")
        args = ["pull"]

        if rebase:
            args.append("--rebase")

        args.append(remote)
        if branch:
            args.append(branch)

        stdout, stderr, code = _run_git(args, cwd=cwd, timeout=120)

        if code != 0:
            raise ToolExecutionError(self.name, stderr.strip() or stdout.strip())

        return stdout.strip() if stdout.strip() else "Already up to date"


class GitPushTool(Tool):
    """Tool for pushing changes to remote."""

    @property
    def name(self) -> str:
        return "git_push"

    @property
    def description(self) -> str:
        return "Push commits to remote repository."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="remote",
                type="string",
                description="Remote name (default: origin)",
                required=False,
                default="origin",
            ),
            ToolParameter(
                name="branch",
                type="string",
                description="Branch to push (default: current branch)",
                required=False,
            ),
            ToolParameter(
                name="set_upstream",
                type="boolean",
                description="Set upstream tracking reference (-u flag)",
                required=False,
                default=False,
            ),
            ToolParameter(
                name="tags",
                type="boolean",
                description="Push all tags",
                required=False,
                default=False,
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
        remote: str = "origin",
        branch: Optional[str] = None,
        set_upstream: bool = False,
        tags: bool = False,
        path: Optional[str] = None,
        **kwargs: Any
    ) -> str:
        """Push to remote."""
        cwd = path or kwargs.get("working_dir", ".")
        args = ["push"]

        if set_upstream:
            args.append("-u")

        if tags:
            args.append("--tags")

        args.append(remote)
        if branch:
            args.append(branch)

        stdout, stderr, code = _run_git(args, cwd=cwd, timeout=120)

        if code != 0:
            raise ToolExecutionError(self.name, stderr.strip() or stdout.strip())

        # Git push outputs to stderr on success
        output = stderr.strip() or stdout.strip()
        return output if output else "Push completed"


class GitResetTool(Tool):
    """Tool for resetting changes."""

    @property
    def name(self) -> str:
        return "git_reset"

    @property
    def description(self) -> str:
        return "Reset current HEAD to a specified state. Can unstage files or reset commits."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="target",
                type="string",
                description="Commit, branch, or file to reset to (default: HEAD)",
                required=False,
                default="HEAD",
            ),
            ToolParameter(
                name="mode",
                type="string",
                description="Reset mode: soft (keep changes staged), mixed (unstage changes, default), hard (discard all changes)",
                required=False,
                default="mixed",
                enum=["soft", "mixed", "hard"],
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
        target: str = "HEAD",
        mode: str = "mixed",
        path: Optional[str] = None,
        **kwargs: Any
    ) -> str:
        """Reset HEAD."""
        cwd = path or kwargs.get("working_dir", ".")
        args = ["reset", f"--{mode}", target]

        stdout, stderr, code = _run_git(args, cwd=cwd)

        if code != 0:
            raise ToolExecutionError(self.name, stderr.strip() or stdout.strip())

        output = stdout.strip() or stderr.strip()
        if not output:
            if mode == "hard":
                return f"Hard reset to {target}"
            elif mode == "soft":
                return f"Soft reset to {target}"
            else:
                return f"Reset to {target}"
        return output


class GitMergeTool(Tool):
    """Tool for merging branches."""

    @property
    def name(self) -> str:
        return "git_merge"

    @property
    def description(self) -> str:
        return "Merge a branch into the current branch."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="branch",
                type="string",
                description="Branch to merge into current branch",
                required=True,
            ),
            ToolParameter(
                name="no_ff",
                type="boolean",
                description="Create a merge commit even for fast-forward merges",
                required=False,
                default=False,
            ),
            ToolParameter(
                name="message",
                type="string",
                description="Merge commit message",
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
        branch: str,
        no_ff: bool = False,
        message: Optional[str] = None,
        path: Optional[str] = None,
        **kwargs: Any
    ) -> str:
        """Merge branch."""
        cwd = path or kwargs.get("working_dir", ".")
        args = ["merge"]

        if no_ff:
            args.append("--no-ff")

        if message:
            args.extend(["-m", message])

        args.append(branch)

        stdout, stderr, code = _run_git(args, cwd=cwd)

        if code != 0:
            if "CONFLICT" in stdout or "CONFLICT" in stderr:
                return f"Merge conflict detected:\n{stdout}\n{stderr}"
            raise ToolExecutionError(self.name, stderr.strip() or stdout.strip())

        return stdout.strip() if stdout.strip() else f"Merged {branch}"


class GitCloneTool(Tool):
    """Tool for cloning repositories."""

    @property
    def name(self) -> str:
        return "git_clone"

    @property
    def description(self) -> str:
        return "Clone a repository from a URL."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="url",
                type="string",
                description="Repository URL to clone",
                required=True,
            ),
            ToolParameter(
                name="directory",
                type="string",
                description="Directory to clone into (optional, defaults to repo name)",
                required=False,
            ),
            ToolParameter(
                name="branch",
                type="string",
                description="Branch to clone (default: default branch)",
                required=False,
            ),
            ToolParameter(
                name="depth",
                type="integer",
                description="Create a shallow clone with specified depth",
                required=False,
            ),
            ToolParameter(
                name="path",
                type="string",
                description="Path to clone into",
                required=False,
            ),
        ]

    def execute(
        self,
        url: str,
        directory: Optional[str] = None,
        branch: Optional[str] = None,
        depth: Optional[int] = None,
        path: Optional[str] = None,
        **kwargs: Any
    ) -> str:
        """Clone repository."""
        cwd = path or kwargs.get("working_dir", ".")
        args = ["clone"]

        if branch:
            args.extend(["--branch", branch])

        if depth:
            args.extend(["--depth", str(depth)])

        args.append(url)

        if directory:
            args.append(directory)

        stdout, stderr, code = _run_git(args, cwd=cwd, timeout=300)

        if code != 0:
            raise ToolExecutionError(self.name, stderr.strip() or stdout.strip())

        # Git clone outputs to stderr
        output = stderr.strip() or stdout.strip()
        return output if output else f"Cloned {url}"


class GitRemoteTool(Tool):
    """Tool for managing remotes."""

    @property
    def name(self) -> str:
        return "git_remote"

    @property
    def description(self) -> str:
        return "Manage remote repositories. List, add, remove, or show remote URLs."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="action",
                type="string",
                description="Action: list (default), add, remove, get-url",
                required=False,
                default="list",
                enum=["list", "add", "remove", "get-url"],
            ),
            ToolParameter(
                name="name",
                type="string",
                description="Remote name (required for add, remove, get-url)",
                required=False,
            ),
            ToolParameter(
                name="url",
                type="string",
                description="Remote URL (required for add)",
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
        action: str = "list",
        name: Optional[str] = None,
        url: Optional[str] = None,
        path: Optional[str] = None,
        **kwargs: Any
    ) -> str:
        """Manage remotes."""
        cwd = path or kwargs.get("working_dir", ".")

        if action == "list":
            args = ["remote", "-v"]
        elif action == "add":
            if not name or not url:
                raise ToolExecutionError(self.name, "Both name and url are required for add")
            args = ["remote", "add", name, url]
        elif action == "remove":
            if not name:
                raise ToolExecutionError(self.name, "Name is required for remove")
            args = ["remote", "remove", name]
        elif action == "get-url":
            if not name:
                raise ToolExecutionError(self.name, "Name is required for get-url")
            args = ["remote", "get-url", name]
        else:
            raise ToolExecutionError(self.name, f"Unknown action: {action}")

        stdout, stderr, code = _run_git(args, cwd=cwd)

        if code != 0:
            raise ToolExecutionError(self.name, stderr.strip() or stdout.strip())

        if action == "list":
            return stdout.strip() if stdout.strip() else "No remotes configured"
        elif action == "add":
            return f"Added remote '{name}' -> {url}"
        elif action == "remove":
            return f"Removed remote '{name}'"
        else:
            return stdout.strip()


class GitTagTool(Tool):
    """Tool for managing tags."""

    @property
    def name(self) -> str:
        return "git_tag"

    @property
    def description(self) -> str:
        return "List, create, or delete tags."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="name",
                type="string",
                description="Tag name (omit to list tags)",
                required=False,
            ),
            ToolParameter(
                name="message",
                type="string",
                description="Tag message (creates annotated tag)",
                required=False,
            ),
            ToolParameter(
                name="delete",
                type="boolean",
                description="Delete the specified tag",
                required=False,
                default=False,
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
        name: Optional[str] = None,
        message: Optional[str] = None,
        delete: bool = False,
        path: Optional[str] = None,
        **kwargs: Any
    ) -> str:
        """Manage tags."""
        cwd = path or kwargs.get("working_dir", ".")

        if name is None:
            # List tags
            args = ["tag", "-l"]
        elif delete:
            args = ["tag", "-d", name]
        elif message:
            # Annotated tag
            args = ["tag", "-a", name, "-m", message]
        else:
            # Lightweight tag
            args = ["tag", name]

        stdout, stderr, code = _run_git(args, cwd=cwd)

        if code != 0:
            raise ToolExecutionError(self.name, stderr.strip() or stdout.strip())

        if name is None:
            return stdout.strip() if stdout.strip() else "No tags"
        elif delete:
            return f"Deleted tag '{name}'"
        else:
            return f"Created tag '{name}'"
