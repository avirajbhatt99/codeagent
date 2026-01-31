"""
Application settings using Pydantic Settings.

Follows the 12-factor app methodology for configuration management.
Settings can be loaded from environment variables or a config file.
"""

from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProviderType(str, Enum):
    """Supported LLM providers."""

    OLLAMA = "ollama"
    OPENROUTER = "openrouter"
    HUGGINGFACE = "huggingface"


class Settings(BaseSettings):
    """
    Application settings with environment variable support.

    Environment variables are prefixed with CODEAGENT_.
    Example: CODEAGENT_PROVIDER=openrouter
    """

    model_config = SettingsConfigDict(
        env_prefix="CODEAGENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Provider settings
    provider: ProviderType = Field(
        default=ProviderType.OLLAMA,
        description="LLM provider to use",
    )
    model: Optional[str] = Field(
        default=None,
        description="Model name (uses provider default if not set)",
    )

    # API Keys (using SecretStr for security)
    openrouter_api_key: Optional[SecretStr] = Field(
        default=None,
        description="OpenRouter API key",
    )
    huggingface_api_key: Optional[SecretStr] = Field(
        default=None,
        description="HuggingFace API token",
    )

    # Ollama settings
    ollama_host: str = Field(
        default="http://localhost:11434",
        description="Ollama server URL",
    )

    # Agent settings
    max_iterations: int = Field(
        default=25,
        ge=1,
        le=100,
        description="Maximum agent loop iterations",
    )
    timeout: int = Field(
        default=120,
        ge=10,
        le=600,
        description="Command execution timeout in seconds",
    )

    # Safety settings
    confirm_commands: bool = Field(
        default=True,
        description="Ask for confirmation before running commands",
    )
    blocked_commands: list[str] = Field(
        default_factory=lambda: [
            "rm -rf /",
            "rm -rf /*",
            "mkfs",
            ":(){:|:&};:",
            "> /dev/sda",
            "dd if=/dev/zero",
        ],
        description="Commands that are blocked for safety",
    )

    # Paths
    config_dir: Path = Field(
        default_factory=lambda: Path.home() / ".config" / "codeagent",
        description="Configuration directory",
    )

    @field_validator("config_dir", mode="before")
    @classmethod
    def expand_path(cls, v: str | Path) -> Path:
        """Expand user home directory in paths."""
        return Path(v).expanduser()

    def get_api_key(self, provider: ProviderType) -> Optional[str]:
        """Get API key for the specified provider."""
        key_map = {
            ProviderType.OPENROUTER: self.openrouter_api_key,
            ProviderType.HUGGINGFACE: self.huggingface_api_key,
        }
        secret = key_map.get(provider)
        return secret.get_secret_value() if secret else None


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Uses LRU cache to ensure settings are loaded only once.
    """
    return Settings()
