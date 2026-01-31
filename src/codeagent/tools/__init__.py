"""Tools for CodeAgent."""

from codeagent.tools.base import Tool, ToolRegistry
from codeagent.tools.file_read import ReadFileTool
from codeagent.tools.file_write import WriteFileTool
from codeagent.tools.file_edit import EditFileTool
from codeagent.tools.file_ops import (
    DeleteFileTool,
    CopyFileTool,
    MoveFileTool,
    MkdirTool,
    ListDirTool,
)
from codeagent.tools.bash import BashTool
from codeagent.tools.grep import GrepTool
from codeagent.tools.glob import GlobTool
from codeagent.tools.git import (
    GitStatusTool,
    GitDiffTool,
    GitLogTool,
    GitAddTool,
    GitCommitTool,
    GitBranchTool,
    GitCheckoutTool,
    GitInitTool,
)


def create_default_registry() -> ToolRegistry:
    """Create a tool registry with all default tools."""
    registry = ToolRegistry()

    # File tools
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    registry.register(EditFileTool())
    registry.register(DeleteFileTool())
    registry.register(CopyFileTool())
    registry.register(MoveFileTool())
    registry.register(MkdirTool())
    registry.register(ListDirTool())

    # Search tools
    registry.register(GrepTool())
    registry.register(GlobTool())

    # Shell
    registry.register(BashTool())

    # Git tools
    registry.register(GitStatusTool())
    registry.register(GitDiffTool())
    registry.register(GitLogTool())
    registry.register(GitAddTool())
    registry.register(GitCommitTool())
    registry.register(GitBranchTool())
    registry.register(GitCheckoutTool())
    registry.register(GitInitTool())

    return registry


__all__ = [
    "Tool",
    "ToolRegistry",
    "ReadFileTool",
    "WriteFileTool",
    "EditFileTool",
    "DeleteFileTool",
    "CopyFileTool",
    "MoveFileTool",
    "MkdirTool",
    "ListDirTool",
    "BashTool",
    "GrepTool",
    "GlobTool",
    "GitStatusTool",
    "GitDiffTool",
    "GitLogTool",
    "GitAddTool",
    "GitCommitTool",
    "GitBranchTool",
    "GitCheckoutTool",
    "GitInitTool",
    "create_default_registry",
]
