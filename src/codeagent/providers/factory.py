"""
Provider factory for creating LLM provider instances.

Implements the Factory pattern for provider instantiation,
with support for registration and discovery.
"""

from typing import Callable, Optional, Type

from codeagent.config.settings import ProviderType, Settings
from codeagent.core.exceptions import ProviderConfigError, ProviderNotFoundError
from codeagent.providers.base import LLMProvider
from codeagent.providers.huggingface import HuggingFaceProvider
from codeagent.providers.ollama import OllamaProvider
from codeagent.providers.openrouter import OpenRouterProvider


class ProviderFactory:
    """
    Factory for creating LLM provider instances.

    Supports registration of custom providers and lazy instantiation.
    """

    # Registry mapping provider types to their classes
    _registry: dict[ProviderType, Type[LLMProvider]] = {
        ProviderType.OLLAMA: OllamaProvider,
        ProviderType.OPENROUTER: OpenRouterProvider,
        ProviderType.HUGGINGFACE: HuggingFaceProvider,
    }

    @classmethod
    def register(
        cls,
        provider_type: ProviderType,
        provider_class: Type[LLMProvider],
    ) -> None:
        """
        Register a new provider type.

        Args:
            provider_type: The provider type enum value
            provider_class: The provider class to register
        """
        cls._registry[provider_type] = provider_class

    @classmethod
    def get_provider_class(cls, provider_type: ProviderType) -> Type[LLMProvider]:
        """
        Get the provider class for a given type.

        Args:
            provider_type: The provider type

        Returns:
            The provider class

        Raises:
            ProviderNotFoundError: If provider type is not registered
        """
        if provider_type not in cls._registry:
            raise ProviderNotFoundError(provider_type.value)
        return cls._registry[provider_type]

    @classmethod
    def create(
        cls,
        provider_type: ProviderType,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        **kwargs: object,
    ) -> LLMProvider:
        """
        Create a provider instance.

        Args:
            provider_type: Type of provider to create
            model: Optional model override
            api_key: Optional API key (required for cloud providers)
            **kwargs: Additional provider-specific arguments

        Returns:
            Configured LLMProvider instance

        Raises:
            ProviderNotFoundError: If provider type is not registered
            ProviderConfigError: If required configuration is missing
        """
        provider_class = cls.get_provider_class(provider_type)

        # Build kwargs based on provider type
        init_kwargs: dict[str, object] = {}

        if model:
            init_kwargs["model"] = model

        # Handle API key requirements
        if provider_type == ProviderType.OLLAMA:
            if "host" in kwargs:
                init_kwargs["host"] = kwargs["host"]
        elif provider_type in (ProviderType.OPENROUTER, ProviderType.HUGGINGFACE):
            if not api_key:
                raise ProviderConfigError(
                    provider_type.value,
                    "API key is required for this provider",
                )
            init_kwargs["api_key"] = api_key

        return provider_class(**init_kwargs)  # type: ignore

    @classmethod
    def create_from_settings(
        cls,
        settings: Settings,
        provider_override: Optional[ProviderType] = None,
        model_override: Optional[str] = None,
    ) -> LLMProvider:
        """
        Create a provider from application settings.

        Args:
            settings: Application settings
            provider_override: Optional provider type override
            model_override: Optional model override

        Returns:
            Configured LLMProvider instance
        """
        provider_type = provider_override or settings.provider
        model = model_override or settings.model
        api_key = settings.get_api_key(provider_type)

        kwargs: dict[str, object] = {}
        if provider_type == ProviderType.OLLAMA:
            kwargs["host"] = settings.ollama_host

        return cls.create(
            provider_type=provider_type,
            model=model,
            api_key=api_key,
            **kwargs,
        )

    @classmethod
    def list_providers(cls) -> list[ProviderType]:
        """Get list of registered provider types."""
        return list(cls._registry.keys())

    @classmethod
    def get_models(cls, provider_type: ProviderType) -> list[str]:
        """Get recommended models for a provider type."""
        provider_class = cls.get_provider_class(provider_type)
        return provider_class.list_models()


def create_provider(
    provider: ProviderType | str,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    **kwargs: object,
) -> LLMProvider:
    """
    Convenience function to create a provider.

    Args:
        provider: Provider type (string or enum)
        model: Optional model name
        api_key: Optional API key
        **kwargs: Additional provider-specific options

    Returns:
        Configured LLMProvider instance
    """
    if isinstance(provider, str):
        provider = ProviderType(provider.lower())

    return ProviderFactory.create(
        provider_type=provider,
        model=model,
        api_key=api_key,
        **kwargs,
    )
