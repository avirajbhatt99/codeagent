"""Environment variable tools."""

import os
from typing import Any, Optional

from codeagent.core.exceptions import ToolExecutionError
from codeagent.tools.base import Tool, ToolParameter


class EnvGetTool(Tool):
    """Tool for getting environment variables."""

    @property
    def name(self) -> str:
        return "env_get"

    @property
    def description(self) -> str:
        return (
            "Get the value of an environment variable. "
            "Can also list all environment variables if no name is provided."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="name",
                type="string",
                description="Name of the environment variable (omit to list all)",
                required=False,
            ),
            ToolParameter(
                name="default",
                type="string",
                description="Default value if variable is not set",
                required=False,
            ),
        ]

    def execute(
        self,
        name: Optional[str] = None,
        default: Optional[str] = None,
        **kwargs: Any
    ) -> str:
        """Get environment variable(s)."""
        if name is None:
            # List all environment variables (sorted)
            env_vars = sorted(os.environ.items())

            # Filter out potentially sensitive variables
            sensitive_patterns = [
                "key", "secret", "password", "token", "credential",
                "auth", "private", "api_key", "apikey"
            ]

            result_lines = ["Environment Variables:", "=" * 50]
            for key, value in env_vars:
                # Mask potentially sensitive values
                key_lower = key.lower()
                if any(pattern in key_lower for pattern in sensitive_patterns):
                    display_value = "********" if value else "(not set)"
                else:
                    # Truncate very long values
                    display_value = value if len(value) <= 100 else value[:100] + "..."

                result_lines.append(f"{key}={display_value}")

            return "\n".join(result_lines)
        else:
            value = os.environ.get(name)
            if value is None:
                if default is not None:
                    return f"{name}={default} (default)"
                return f"{name} is not set"
            return f"{name}={value}"


class EnvSetTool(Tool):
    """Tool for setting environment variables."""

    @property
    def name(self) -> str:
        return "env_set"

    @property
    def description(self) -> str:
        return (
            "Set an environment variable for the current session. "
            "Note: This only affects the current process and its children, "
            "not the parent shell or other processes."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="name",
                type="string",
                description="Name of the environment variable",
                required=True,
            ),
            ToolParameter(
                name="value",
                type="string",
                description="Value to set (use empty string to set empty value)",
                required=True,
            ),
        ]

    def execute(
        self,
        name: str,
        value: str,
        **kwargs: Any
    ) -> str:
        """Set environment variable."""
        # Validate name
        if not name or not name.replace("_", "").isalnum():
            raise ToolExecutionError(
                self.name,
                f"Invalid environment variable name: {name}"
            )

        old_value = os.environ.get(name)
        os.environ[name] = value

        if old_value is not None:
            return f"Updated {name} (was: {old_value[:50]}{'...' if len(old_value) > 50 else ''})"
        return f"Set {name}={value[:50]}{'...' if len(value) > 50 else ''}"


class EnvUnsetTool(Tool):
    """Tool for unsetting environment variables."""

    @property
    def name(self) -> str:
        return "env_unset"

    @property
    def description(self) -> str:
        return (
            "Unset (remove) an environment variable from the current session. "
            "Note: This only affects the current process and its children."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="name",
                type="string",
                description="Name of the environment variable to unset",
                required=True,
            ),
        ]

    def execute(
        self,
        name: str,
        **kwargs: Any
    ) -> str:
        """Unset environment variable."""
        if name in os.environ:
            del os.environ[name]
            return f"Unset {name}"
        return f"{name} was not set"


class EnvLoadTool(Tool):
    """Tool for loading environment variables from a .env file."""

    @property
    def name(self) -> str:
        return "env_load"

    @property
    def description(self) -> str:
        return (
            "Load environment variables from a .env file. "
            "Each line should be in KEY=value format. "
            "Lines starting with # are treated as comments."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="file_path",
                type="string",
                description="Path to the .env file (default: .env)",
                required=False,
                default=".env",
            ),
            ToolParameter(
                name="override",
                type="boolean",
                description="Override existing variables (default: false)",
                required=False,
                default=False,
            ),
        ]

    def execute(
        self,
        file_path: str = ".env",
        override: bool = False,
        working_dir: Optional[str] = None,
        **kwargs: Any
    ) -> str:
        """Load environment from file."""
        # Resolve path
        if working_dir and not os.path.isabs(file_path):
            full_path = os.path.join(working_dir, file_path)
        else:
            full_path = file_path

        if not os.path.exists(full_path):
            raise ToolExecutionError(self.name, f"File not found: {file_path}")

        loaded = 0
        skipped = 0
        errors = []

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()

                    # Skip empty lines and comments
                    if not line or line.startswith("#"):
                        continue

                    # Parse KEY=value format
                    if "=" not in line:
                        errors.append(f"Line {line_num}: Invalid format (missing '=')")
                        continue

                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip()

                    # Remove quotes if present
                    if (value.startswith('"') and value.endswith('"')) or \
                       (value.startswith("'") and value.endswith("'")):
                        value = value[1:-1]

                    if not key:
                        errors.append(f"Line {line_num}: Empty key")
                        continue

                    # Set variable
                    if key in os.environ and not override:
                        skipped += 1
                    else:
                        os.environ[key] = value
                        loaded += 1

        except IOError as e:
            raise ToolExecutionError(self.name, f"Failed to read file: {e}")

        result_parts = [f"Loaded {loaded} variable(s) from {file_path}"]

        if skipped:
            result_parts.append(f"Skipped {skipped} existing variable(s)")

        if errors:
            result_parts.append("Errors:")
            result_parts.extend(f"  - {e}" for e in errors[:5])
            if len(errors) > 5:
                result_parts.append(f"  ... and {len(errors) - 5} more")

        return "\n".join(result_parts)
