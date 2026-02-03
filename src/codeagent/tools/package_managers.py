"""Package manager tools for npm, pip, and cargo."""

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Optional

from codeagent.core.exceptions import ToolExecutionError
from codeagent.tools.base import Tool, ToolParameter


def _run_command(
    args: list[str],
    cwd: Optional[str] = None,
    timeout: int = 300,
    env: Optional[dict[str, str]] = None,
) -> tuple[str, str, int]:
    """Run a command and return stdout, stderr, returncode."""
    try:
        run_env = {**os.environ}
        if env:
            run_env.update(env)

        result = subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=run_env,
        )
        return result.stdout, result.stderr, result.returncode
    except FileNotFoundError:
        raise ToolExecutionError(args[0], f"{args[0]} is not installed or not in PATH")
    except subprocess.TimeoutExpired:
        raise ToolExecutionError(args[0], f"Command timed out after {timeout}s")


# =============================================================================
# NPM Tools
# =============================================================================


class NpmInstallTool(Tool):
    """Tool for installing npm packages."""

    @property
    def name(self) -> str:
        return "npm_install"

    @property
    def description(self) -> str:
        return (
            "Install npm packages. Run without arguments to install all dependencies "
            "from package.json, or specify package names to install specific packages."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="packages",
                type="string",
                description="Package(s) to install (space-separated). Omit to install from package.json",
                required=False,
            ),
            ToolParameter(
                name="dev",
                type="boolean",
                description="Install as dev dependency (--save-dev)",
                required=False,
                default=False,
            ),
            ToolParameter(
                name="global_install",
                type="boolean",
                description="Install globally (-g)",
                required=False,
                default=False,
            ),
            ToolParameter(
                name="path",
                type="string",
                description="Path to run npm in",
                required=False,
            ),
        ]

    def execute(
        self,
        packages: Optional[str] = None,
        dev: bool = False,
        global_install: bool = False,
        path: Optional[str] = None,
        **kwargs: Any
    ) -> str:
        """Install npm packages."""
        cwd = path or kwargs.get("working_dir", ".")
        args = ["npm", "install"]

        if global_install:
            args.append("-g")

        if packages:
            args.extend(packages.split())
            if dev:
                args.append("--save-dev")

        stdout, stderr, code = _run_command(args, cwd=cwd, timeout=600)

        if code != 0:
            raise ToolExecutionError(self.name, stderr.strip() or stdout.strip())

        output = stdout.strip() or stderr.strip()
        return output if output else "Packages installed successfully"


class NpmRunTool(Tool):
    """Tool for running npm scripts."""

    @property
    def name(self) -> str:
        return "npm_run"

    @property
    def description(self) -> str:
        return "Run an npm script defined in package.json."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="script",
                type="string",
                description="Script name to run (e.g., 'build', 'test', 'start')",
                required=True,
            ),
            ToolParameter(
                name="args",
                type="string",
                description="Additional arguments to pass to the script",
                required=False,
            ),
            ToolParameter(
                name="path",
                type="string",
                description="Path to run npm in",
                required=False,
            ),
        ]

    def execute(
        self,
        script: str,
        args: Optional[str] = None,
        path: Optional[str] = None,
        **kwargs: Any
    ) -> str:
        """Run npm script."""
        cwd = path or kwargs.get("working_dir", ".")
        cmd = ["npm", "run", script]

        if args:
            cmd.append("--")
            cmd.extend(args.split())

        stdout, stderr, code = _run_command(cmd, cwd=cwd, timeout=600)

        if code != 0:
            output = stdout + "\n" + stderr
            raise ToolExecutionError(self.name, output.strip())

        return stdout.strip() or stderr.strip() or f"Script '{script}' completed"


class NpmListTool(Tool):
    """Tool for listing npm packages."""

    @property
    def name(self) -> str:
        return "npm_list"

    @property
    def description(self) -> str:
        return "List installed npm packages."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="depth",
                type="integer",
                description="Depth of dependency tree to show (default: 0)",
                required=False,
                default=0,
            ),
            ToolParameter(
                name="global_list",
                type="boolean",
                description="List global packages",
                required=False,
                default=False,
            ),
            ToolParameter(
                name="path",
                type="string",
                description="Path to run npm in",
                required=False,
            ),
        ]

    def execute(
        self,
        depth: int = 0,
        global_list: bool = False,
        path: Optional[str] = None,
        **kwargs: Any
    ) -> str:
        """List npm packages."""
        cwd = path or kwargs.get("working_dir", ".")
        args = ["npm", "list", f"--depth={depth}"]

        if global_list:
            args.append("-g")

        stdout, stderr, code = _run_command(args, cwd=cwd)

        # npm list returns non-zero if there are missing packages
        output = stdout.strip()
        if not output:
            return "No packages installed"
        return output


# =============================================================================
# Pip Tools
# =============================================================================


class PipInstallTool(Tool):
    """Tool for installing Python packages with pip."""

    @property
    def name(self) -> str:
        return "pip_install"

    @property
    def description(self) -> str:
        return (
            "Install Python packages using pip. Can install specific packages "
            "or from requirements.txt file."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="packages",
                type="string",
                description="Package(s) to install (space-separated), or '-r requirements.txt'",
                required=True,
            ),
            ToolParameter(
                name="upgrade",
                type="boolean",
                description="Upgrade packages to latest version",
                required=False,
                default=False,
            ),
            ToolParameter(
                name="path",
                type="string",
                description="Path to run pip in",
                required=False,
            ),
        ]

    def execute(
        self,
        packages: str,
        upgrade: bool = False,
        path: Optional[str] = None,
        **kwargs: Any
    ) -> str:
        """Install pip packages."""
        cwd = path or kwargs.get("working_dir", ".")
        args = ["pip", "install"]

        if upgrade:
            args.append("--upgrade")

        # Handle requirements file
        if packages.startswith("-r "):
            args.extend(packages.split())
        else:
            args.extend(packages.split())

        stdout, stderr, code = _run_command(args, cwd=cwd, timeout=600)

        if code != 0:
            raise ToolExecutionError(self.name, stderr.strip() or stdout.strip())

        return stdout.strip() or "Packages installed successfully"


class PipListTool(Tool):
    """Tool for listing installed Python packages."""

    @property
    def name(self) -> str:
        return "pip_list"

    @property
    def description(self) -> str:
        return "List installed Python packages."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="outdated",
                type="boolean",
                description="Show only outdated packages",
                required=False,
                default=False,
            ),
            ToolParameter(
                name="path",
                type="string",
                description="Path to run pip in",
                required=False,
            ),
        ]

    def execute(
        self,
        outdated: bool = False,
        path: Optional[str] = None,
        **kwargs: Any
    ) -> str:
        """List pip packages."""
        cwd = path or kwargs.get("working_dir", ".")
        args = ["pip", "list"]

        if outdated:
            args.append("--outdated")

        stdout, stderr, code = _run_command(args, cwd=cwd)

        if code != 0:
            raise ToolExecutionError(self.name, stderr.strip())

        return stdout.strip() or "No packages installed"


class PipFreezeTool(Tool):
    """Tool for generating requirements.txt."""

    @property
    def name(self) -> str:
        return "pip_freeze"

    @property
    def description(self) -> str:
        return "Output installed packages in requirements format (pip freeze)."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="path",
                type="string",
                description="Path to run pip in",
                required=False,
            ),
        ]

    def execute(self, path: Optional[str] = None, **kwargs: Any) -> str:
        """Freeze pip packages."""
        cwd = path or kwargs.get("working_dir", ".")
        stdout, stderr, code = _run_command(["pip", "freeze"], cwd=cwd)

        if code != 0:
            raise ToolExecutionError(self.name, stderr.strip())

        return stdout.strip() or "No packages installed"


class PipUninstallTool(Tool):
    """Tool for uninstalling Python packages."""

    @property
    def name(self) -> str:
        return "pip_uninstall"

    @property
    def description(self) -> str:
        return "Uninstall Python packages."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="packages",
                type="string",
                description="Package(s) to uninstall (space-separated)",
                required=True,
            ),
            ToolParameter(
                name="path",
                type="string",
                description="Path to run pip in",
                required=False,
            ),
        ]

    def execute(
        self,
        packages: str,
        path: Optional[str] = None,
        **kwargs: Any
    ) -> str:
        """Uninstall pip packages."""
        cwd = path or kwargs.get("working_dir", ".")
        args = ["pip", "uninstall", "-y"] + packages.split()

        stdout, stderr, code = _run_command(args, cwd=cwd)

        if code != 0:
            raise ToolExecutionError(self.name, stderr.strip() or stdout.strip())

        return stdout.strip() or f"Uninstalled: {packages}"


# =============================================================================
# Cargo Tools (Rust)
# =============================================================================


class CargoBuildTool(Tool):
    """Tool for building Rust projects."""

    @property
    def name(self) -> str:
        return "cargo_build"

    @property
    def description(self) -> str:
        return "Build a Rust project using Cargo."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="release",
                type="boolean",
                description="Build in release mode (optimized)",
                required=False,
                default=False,
            ),
            ToolParameter(
                name="package",
                type="string",
                description="Specific package to build in workspace",
                required=False,
            ),
            ToolParameter(
                name="path",
                type="string",
                description="Path to the Rust project",
                required=False,
            ),
        ]

    def execute(
        self,
        release: bool = False,
        package: Optional[str] = None,
        path: Optional[str] = None,
        **kwargs: Any
    ) -> str:
        """Build Rust project."""
        cwd = path or kwargs.get("working_dir", ".")
        args = ["cargo", "build"]

        if release:
            args.append("--release")

        if package:
            args.extend(["-p", package])

        stdout, stderr, code = _run_command(args, cwd=cwd, timeout=600)

        if code != 0:
            raise ToolExecutionError(self.name, stderr.strip() or stdout.strip())

        # Cargo outputs to stderr
        return stderr.strip() or stdout.strip() or "Build completed"


class CargoRunTool(Tool):
    """Tool for running Rust projects."""

    @property
    def name(self) -> str:
        return "cargo_run"

    @property
    def description(self) -> str:
        return "Run a Rust project using Cargo."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="release",
                type="boolean",
                description="Run in release mode",
                required=False,
                default=False,
            ),
            ToolParameter(
                name="args",
                type="string",
                description="Arguments to pass to the program",
                required=False,
            ),
            ToolParameter(
                name="path",
                type="string",
                description="Path to the Rust project",
                required=False,
            ),
        ]

    def execute(
        self,
        release: bool = False,
        args: Optional[str] = None,
        path: Optional[str] = None,
        **kwargs: Any
    ) -> str:
        """Run Rust project."""
        cwd = path or kwargs.get("working_dir", ".")
        cmd = ["cargo", "run"]

        if release:
            cmd.append("--release")

        if args:
            cmd.append("--")
            cmd.extend(args.split())

        stdout, stderr, code = _run_command(cmd, cwd=cwd, timeout=300)

        if code != 0:
            raise ToolExecutionError(self.name, stderr.strip() or stdout.strip())

        return stdout.strip() or stderr.strip() or "Run completed"


class CargoTestTool(Tool):
    """Tool for running Rust tests."""

    @property
    def name(self) -> str:
        return "cargo_test"

    @property
    def description(self) -> str:
        return "Run tests in a Rust project using Cargo."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="test_name",
                type="string",
                description="Specific test or pattern to run",
                required=False,
            ),
            ToolParameter(
                name="package",
                type="string",
                description="Specific package to test in workspace",
                required=False,
            ),
            ToolParameter(
                name="path",
                type="string",
                description="Path to the Rust project",
                required=False,
            ),
        ]

    def execute(
        self,
        test_name: Optional[str] = None,
        package: Optional[str] = None,
        path: Optional[str] = None,
        **kwargs: Any
    ) -> str:
        """Run Rust tests."""
        cwd = path or kwargs.get("working_dir", ".")
        args = ["cargo", "test"]

        if package:
            args.extend(["-p", package])

        if test_name:
            args.append(test_name)

        stdout, stderr, code = _run_command(args, cwd=cwd, timeout=600)

        output = stdout + "\n" + stderr
        if code != 0:
            raise ToolExecutionError(self.name, output.strip())

        return output.strip() or "Tests completed"


class CargoAddTool(Tool):
    """Tool for adding Cargo dependencies."""

    @property
    def name(self) -> str:
        return "cargo_add"

    @property
    def description(self) -> str:
        return "Add dependencies to a Rust project (requires cargo-edit or Rust 1.62+)."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="packages",
                type="string",
                description="Package(s) to add (space-separated)",
                required=True,
            ),
            ToolParameter(
                name="dev",
                type="boolean",
                description="Add as dev dependency",
                required=False,
                default=False,
            ),
            ToolParameter(
                name="features",
                type="string",
                description="Comma-separated features to enable",
                required=False,
            ),
            ToolParameter(
                name="path",
                type="string",
                description="Path to the Rust project",
                required=False,
            ),
        ]

    def execute(
        self,
        packages: str,
        dev: bool = False,
        features: Optional[str] = None,
        path: Optional[str] = None,
        **kwargs: Any
    ) -> str:
        """Add Cargo dependencies."""
        cwd = path or kwargs.get("working_dir", ".")
        args = ["cargo", "add"]

        if dev:
            args.append("--dev")

        args.extend(packages.split())

        if features:
            args.extend(["--features", features])

        stdout, stderr, code = _run_command(args, cwd=cwd)

        if code != 0:
            raise ToolExecutionError(self.name, stderr.strip() or stdout.strip())

        return stderr.strip() or stdout.strip() or f"Added: {packages}"
