"""File operation tools - delete, copy, move, mkdir."""

import os
import shutil
from pathlib import Path
from typing import Any

from codeagent.core.exceptions import ToolExecutionError
from codeagent.tools.base import Tool, ToolParameter


class DeleteFileTool(Tool):
    """Tool for deleting files and directories."""

    @property
    def name(self) -> str:
        return "delete"

    @property
    def description(self) -> str:
        return (
            "Delete a file or directory. For directories, use recursive=true to delete "
            "non-empty directories. Be careful - this action cannot be undone."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="path",
                type="string",
                description="Absolute path to the file or directory to delete",
                required=True,
            ),
            ToolParameter(
                name="recursive",
                type="boolean",
                description="If true, delete directories and all contents. Required for non-empty directories.",
                required=False,
            ),
        ]

    def execute(self, path: str, recursive: bool = False, working_dir: str | None = None, **kwargs: Any) -> str:
        """Delete a file or directory."""
        target = Path(path).expanduser()

        # Resolve relative paths against working directory
        if not target.is_absolute():
            if working_dir:
                target = Path(working_dir) / target
            else:
                target = Path.cwd() / target

        if not target.exists():
            raise ToolExecutionError(self.name, f"Path does not exist: {path}")

        try:
            if target.is_file():
                target.unlink()
                return f"Deleted file: {path}"
            elif target.is_dir():
                if recursive:
                    shutil.rmtree(target)
                    return f"Deleted directory and contents: {path}"
                else:
                    # Try rmdir (only works on empty directories)
                    try:
                        target.rmdir()
                        return f"Deleted empty directory: {path}"
                    except OSError:
                        raise ToolExecutionError(
                            self.name,
                            f"Directory not empty. Use recursive=true to delete: {path}",
                        )
            else:
                raise ToolExecutionError(self.name, f"Unknown file type: {path}")
        except PermissionError:
            raise ToolExecutionError(self.name, f"Permission denied: {path}")
        except Exception as e:
            raise ToolExecutionError(self.name, f"Failed to delete: {e}")


class CopyFileTool(Tool):
    """Tool for copying files and directories."""

    @property
    def name(self) -> str:
        return "copy"

    @property
    def description(self) -> str:
        return "Copy a file or directory to a new location."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="source",
                type="string",
                description="Absolute path to the source file or directory",
                required=True,
            ),
            ToolParameter(
                name="destination",
                type="string",
                description="Absolute path to the destination",
                required=True,
            ),
        ]

    def execute(self, source: str, destination: str, working_dir: str | None = None, **kwargs: Any) -> str:
        """Copy a file or directory."""
        src = Path(source).expanduser()
        dst = Path(destination).expanduser()

        # Resolve relative paths against working directory
        if not src.is_absolute():
            if working_dir:
                src = Path(working_dir) / src
            else:
                src = Path.cwd() / src
        if not dst.is_absolute():
            if working_dir:
                dst = Path(working_dir) / dst
            else:
                dst = Path.cwd() / dst

        if not src.exists():
            raise ToolExecutionError(self.name, f"Source does not exist: {source}")

        try:
            if src.is_file():
                # Create parent directories if needed
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                return f"Copied file: {source} -> {destination}"
            elif src.is_dir():
                shutil.copytree(src, dst)
                return f"Copied directory: {source} -> {destination}"
            else:
                raise ToolExecutionError(self.name, f"Unknown file type: {source}")
        except PermissionError:
            raise ToolExecutionError(self.name, f"Permission denied")
        except FileExistsError:
            raise ToolExecutionError(self.name, f"Destination already exists: {destination}")
        except Exception as e:
            raise ToolExecutionError(self.name, f"Failed to copy: {e}")


class MoveFileTool(Tool):
    """Tool for moving/renaming files and directories."""

    @property
    def name(self) -> str:
        return "move"

    @property
    def description(self) -> str:
        return "Move or rename a file or directory."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="source",
                type="string",
                description="Absolute path to the source file or directory",
                required=True,
            ),
            ToolParameter(
                name="destination",
                type="string",
                description="Absolute path to the destination",
                required=True,
            ),
        ]

    def execute(self, source: str, destination: str, working_dir: str | None = None, **kwargs: Any) -> str:
        """Move a file or directory."""
        src = Path(source).expanduser()
        dst = Path(destination).expanduser()

        # Resolve relative paths against working directory
        if not src.is_absolute():
            if working_dir:
                src = Path(working_dir) / src
            else:
                src = Path.cwd() / src
        if not dst.is_absolute():
            if working_dir:
                dst = Path(working_dir) / dst
            else:
                dst = Path.cwd() / dst

        if not src.exists():
            raise ToolExecutionError(self.name, f"Source does not exist: {source}")

        try:
            # Create parent directories if needed
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            return f"Moved: {source} -> {destination}"
        except PermissionError:
            raise ToolExecutionError(self.name, f"Permission denied")
        except Exception as e:
            raise ToolExecutionError(self.name, f"Failed to move: {e}")


class MkdirTool(Tool):
    """Tool for creating directories."""

    @property
    def name(self) -> str:
        return "mkdir"

    @property
    def description(self) -> str:
        return "Create a new directory. Creates parent directories if they don't exist."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="path",
                type="string",
                description="Absolute path of the directory to create",
                required=True,
            ),
        ]

    def execute(self, path: str, working_dir: str | None = None, **kwargs: Any) -> str:
        """Create a directory."""
        target = Path(path).expanduser()

        # Resolve relative paths against working directory
        if not target.is_absolute():
            if working_dir:
                target = Path(working_dir) / target
            else:
                target = Path.cwd() / target

        if target.exists():
            if target.is_dir():
                return f"Directory already exists: {path}"
            else:
                raise ToolExecutionError(self.name, f"Path exists but is not a directory: {path}")

        try:
            target.mkdir(parents=True, exist_ok=True)
            return f"Created directory: {path}"
        except PermissionError:
            raise ToolExecutionError(self.name, f"Permission denied: {path}")
        except Exception as e:
            raise ToolExecutionError(self.name, f"Failed to create directory: {e}")


class ListDirTool(Tool):
    """Tool for listing directory contents."""

    @property
    def name(self) -> str:
        return "ls"

    @property
    def description(self) -> str:
        return "List contents of a directory with file types and sizes."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="path",
                type="string",
                description="Absolute path to the directory to list",
                required=True,
            ),
            ToolParameter(
                name="all",
                type="boolean",
                description="Include hidden files (starting with .)",
                required=False,
            ),
        ]

    def execute(self, path: str, all: bool = False, working_dir: str | None = None, **kwargs: Any) -> str:
        """List directory contents."""
        target = Path(path).expanduser()

        # Resolve relative paths against working directory
        if not target.is_absolute():
            if working_dir:
                target = Path(working_dir) / target
            else:
                target = Path.cwd() / target

        if not target.exists():
            raise ToolExecutionError(self.name, f"Path does not exist: {path}")

        if not target.is_dir():
            raise ToolExecutionError(self.name, f"Path is not a directory: {path}")

        try:
            entries = []
            for item in sorted(target.iterdir()):
                # Skip hidden files unless all=True
                if not all and item.name.startswith("."):
                    continue

                if item.is_dir():
                    entries.append(f"  {item.name}/")
                else:
                    size = item.stat().st_size
                    if size < 1024:
                        size_str = f"{size}B"
                    elif size < 1024 * 1024:
                        size_str = f"{size // 1024}KB"
                    else:
                        size_str = f"{size // (1024 * 1024)}MB"
                    entries.append(f"  {item.name} ({size_str})")

            if not entries:
                return f"Directory is empty: {path}"

            return f"{path}:\n" + "\n".join(entries)
        except PermissionError:
            raise ToolExecutionError(self.name, f"Permission denied: {path}")
        except Exception as e:
            raise ToolExecutionError(self.name, f"Failed to list directory: {e}")
