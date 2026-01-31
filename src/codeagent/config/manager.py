"""
Configuration manager for persistent settings.

Stores configuration in ~/.config/codeagent/config.json
Provides simple API for reading/writing settings.
"""

import json
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field, SecretStr


class StoredConfig(BaseModel):
    """Configuration that gets persisted to disk."""

    provider: str = "ollama"
    model: Optional[str] = None
    ollama_host: str = "http://localhost:11434"
    openrouter_api_key: Optional[str] = None
    huggingface_api_key: Optional[str] = None
    max_iterations: int = 25
    timeout: int = 120


class ConfigManager:
    """
    Manages persistent configuration storage.

    Config is stored in ~/.config/codeagent/config.json
    """

    def __init__(self, config_dir: Optional[Path] = None) -> None:
        self._config_dir = config_dir or Path.home() / ".config" / "codeagent"
        self._config_file = self._config_dir / "config.json"
        self._config: Optional[StoredConfig] = None

    @property
    def config_file(self) -> Path:
        """Get the config file path."""
        return self._config_file

    @property
    def config_dir(self) -> Path:
        """Get the config directory path."""
        return self._config_dir

    def exists(self) -> bool:
        """Check if config file exists."""
        return self._config_file.exists()

    def load(self) -> StoredConfig:
        """Load config from disk, creating defaults if needed."""
        if self._config is not None:
            return self._config

        if self._config_file.exists():
            try:
                data = json.loads(self._config_file.read_text())
                self._config = StoredConfig(**data)
            except (json.JSONDecodeError, Exception):
                # Corrupted config, use defaults
                self._config = StoredConfig()
        else:
            self._config = StoredConfig()

        return self._config

    def save(self, config: Optional[StoredConfig] = None) -> None:
        """Save config to disk."""
        if config is not None:
            self._config = config

        if self._config is None:
            self._config = StoredConfig()

        # Ensure directory exists
        self._config_dir.mkdir(parents=True, exist_ok=True)

        # Write config
        self._config_file.write_text(
            json.dumps(self._config.model_dump(), indent=2)
        )

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value."""
        config = self.load()
        return getattr(config, key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a config value and save."""
        config = self.load()
        if hasattr(config, key):
            setattr(config, key, value)
            self.save(config)
        else:
            raise KeyError(f"Unknown config key: {key}")

    def update(self, **kwargs: Any) -> None:
        """Update multiple config values and save."""
        config = self.load()
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)
        self.save(config)

    def reset(self) -> None:
        """Reset config to defaults."""
        self._config = StoredConfig()
        self.save()

    def delete(self) -> None:
        """Delete the config file."""
        if self._config_file.exists():
            self._config_file.unlink()
        self._config = None

    def get_api_key(self, provider: str) -> Optional[str]:
        """Get API key for a provider."""
        config = self.load()
        if provider == "openrouter":
            return config.openrouter_api_key
        elif provider == "huggingface":
            return config.huggingface_api_key
        return None

    def set_api_key(self, provider: str, key: str) -> None:
        """Set API key for a provider."""
        if provider == "openrouter":
            self.set("openrouter_api_key", key)
        elif provider == "huggingface":
            self.set("huggingface_api_key", key)

    def is_configured(self) -> bool:
        """Check if basic configuration is done."""
        config = self.load()

        # Ollama doesn't need API key
        if config.provider == "ollama":
            return True

        # Cloud providers need API key
        if config.provider == "openrouter":
            return config.openrouter_api_key is not None
        if config.provider == "huggingface":
            return config.huggingface_api_key is not None

        return False


# Global instance
_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """Get the global config manager instance."""
    global _manager
    if _manager is None:
        _manager = ConfigManager()
    return _manager
