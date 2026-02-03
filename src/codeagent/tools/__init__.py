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
    # Extended git tools
    GitStashTool,
    GitPullTool,
    GitPushTool,
    GitResetTool,
    GitMergeTool,
    GitCloneTool,
    GitRemoteTool,
    GitTagTool,
)
from codeagent.tools.web import (
    WebFetchTool,
    HttpRequestTool,
)
from codeagent.tools.code_analysis import (
    TreeTool,
    FindSymbolTool,
    CodeStatsTool,
)
from codeagent.tools.package_managers import (
    # npm tools
    NpmInstallTool,
    NpmRunTool,
    NpmListTool,
    # pip tools
    PipInstallTool,
    PipListTool,
    PipFreezeTool,
    PipUninstallTool,
    # cargo tools
    CargoBuildTool,
    CargoRunTool,
    CargoTestTool,
    CargoAddTool,
)
from codeagent.tools.env import (
    EnvGetTool,
    EnvSetTool,
    EnvUnsetTool,
    EnvLoadTool,
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

    # Git tools (basic)
    registry.register(GitStatusTool())
    registry.register(GitDiffTool())
    registry.register(GitLogTool())
    registry.register(GitAddTool())
    registry.register(GitCommitTool())
    registry.register(GitBranchTool())
    registry.register(GitCheckoutTool())
    registry.register(GitInitTool())

    # Git tools (extended)
    registry.register(GitStashTool())
    registry.register(GitPullTool())
    registry.register(GitPushTool())
    registry.register(GitResetTool())
    registry.register(GitMergeTool())
    registry.register(GitCloneTool())
    registry.register(GitRemoteTool())
    registry.register(GitTagTool())

    # Web tools
    registry.register(WebFetchTool())
    registry.register(HttpRequestTool())

    # Code analysis tools
    registry.register(TreeTool())
    registry.register(FindSymbolTool())
    registry.register(CodeStatsTool())

    # Package manager tools - npm
    registry.register(NpmInstallTool())
    registry.register(NpmRunTool())
    registry.register(NpmListTool())

    # Package manager tools - pip
    registry.register(PipInstallTool())
    registry.register(PipListTool())
    registry.register(PipFreezeTool())
    registry.register(PipUninstallTool())

    # Package manager tools - cargo
    registry.register(CargoBuildTool())
    registry.register(CargoRunTool())
    registry.register(CargoTestTool())
    registry.register(CargoAddTool())

    # Environment variable tools
    registry.register(EnvGetTool())
    registry.register(EnvSetTool())
    registry.register(EnvUnsetTool())
    registry.register(EnvLoadTool())

    return registry


__all__ = [
    # Base
    "Tool",
    "ToolRegistry",
    "create_default_registry",
    # File tools
    "ReadFileTool",
    "WriteFileTool",
    "EditFileTool",
    "DeleteFileTool",
    "CopyFileTool",
    "MoveFileTool",
    "MkdirTool",
    "ListDirTool",
    # Search tools
    "BashTool",
    "GrepTool",
    "GlobTool",
    # Git tools (basic)
    "GitStatusTool",
    "GitDiffTool",
    "GitLogTool",
    "GitAddTool",
    "GitCommitTool",
    "GitBranchTool",
    "GitCheckoutTool",
    "GitInitTool",
    # Git tools (extended)
    "GitStashTool",
    "GitPullTool",
    "GitPushTool",
    "GitResetTool",
    "GitMergeTool",
    "GitCloneTool",
    "GitRemoteTool",
    "GitTagTool",
    # Web tools
    "WebFetchTool",
    "HttpRequestTool",
    # Code analysis tools
    "TreeTool",
    "FindSymbolTool",
    "CodeStatsTool",
    # Package manager tools - npm
    "NpmInstallTool",
    "NpmRunTool",
    "NpmListTool",
    # Package manager tools - pip
    "PipInstallTool",
    "PipListTool",
    "PipFreezeTool",
    "PipUninstallTool",
    # Package manager tools - cargo
    "CargoBuildTool",
    "CargoRunTool",
    "CargoTestTool",
    "CargoAddTool",
    # Environment variable tools
    "EnvGetTool",
    "EnvSetTool",
    "EnvUnsetTool",
    "EnvLoadTool",
]
