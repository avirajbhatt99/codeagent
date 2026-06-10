"""Tests for the FreeLLMAPI provider."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from codeagent.config.manager import StoredConfig
from codeagent.config.settings import ProviderType
from codeagent.core.exceptions import ProviderConfigError
from codeagent.providers.factory import ProviderFactory
from codeagent.providers.freellmapi import DEFAULT_BASE_URL, FreeLLMAPIProvider


def make_provider(**kwargs) -> FreeLLMAPIProvider:
    provider = FreeLLMAPIProvider(api_key="freellmapi-test-key", **kwargs)
    provider._client = MagicMock()
    return provider


class TestConstruction:
    def test_requires_api_key(self):
        with pytest.raises(ProviderConfigError):
            FreeLLMAPIProvider(api_key="")

    def test_default_base_url(self):
        provider = make_provider()
        assert provider.base_url == DEFAULT_BASE_URL

    def test_custom_base_url(self):
        provider = make_provider(base_url="http://myserver:9000/v1")
        assert provider.base_url == "http://myserver:9000/v1"

    def test_default_model_is_auto(self):
        assert FreeLLMAPIProvider.get_default_model() == "auto"
        assert make_provider().model == "auto"

    def test_model_override(self):
        assert make_provider(model="gemini-2.5-flash").model == "gemini-2.5-flash"

    def test_list_models_static(self):
        assert FreeLLMAPIProvider.list_models() == ["auto"]


class TestFetchModels:
    def test_returns_ids_from_instance(self):
        provider = make_provider()
        provider._client.models.list.return_value = [
            SimpleNamespace(id="auto"),
            SimpleNamespace(id="gemini-2.5-flash"),
        ]
        assert provider.fetch_models() == ["auto", "gemini-2.5-flash"]

    def test_falls_back_when_unreachable(self):
        provider = make_provider()
        provider._client.models.list.side_effect = Exception("connection refused")
        assert provider.fetch_models() == ["auto"]

    def test_falls_back_when_empty(self):
        provider = make_provider()
        provider._client.models.list.return_value = []
        assert provider.fetch_models() == ["auto"]


class TestValidateApiKey:
    def test_valid(self):
        provider = make_provider()
        provider._client.models.list.return_value = []
        assert provider.validate_api_key() is True

    def test_invalid_key(self):
        provider = make_provider()
        provider._client.models.list.side_effect = Exception("401 Unauthorized")
        with pytest.raises(ProviderConfigError, match="Invalid API key"):
            provider.validate_api_key()

    def test_unreachable_mentions_base_url(self):
        provider = make_provider(base_url="http://myserver:9000/v1")
        provider._client.models.list.side_effect = Exception("Connection error")
        with pytest.raises(ProviderConfigError, match="myserver:9000"):
            provider.validate_api_key()


class TestChat:
    def test_parses_content_and_tool_calls(self):
        provider = make_provider()
        tool_call = SimpleNamespace(
            id="call_1",
            function=SimpleNamespace(
                name="read_file",
                arguments=json.dumps({"file_path": "a.py"}),
            ),
        )
        response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="hi", tool_calls=[tool_call]),
                    finish_reason="tool_calls",
                )
            ],
            usage=SimpleNamespace(total_tokens=42),
        )
        provider._client.chat.completions.create.return_value = response

        result = provider.chat([{"role": "user", "content": "hello"}])

        assert result.content == "hi"
        assert result.tool_calls[0].name == "read_file"
        assert result.tool_calls[0].arguments == {"file_path": "a.py"}
        assert provider.total_tokens_used == 42


class TestFactory:
    def test_registered(self):
        assert (
            ProviderFactory.get_provider_class(ProviderType.FREELLMAPI)
            is FreeLLMAPIProvider
        )

    def test_requires_api_key(self):
        with pytest.raises(ProviderConfigError):
            ProviderFactory.create(ProviderType.FREELLMAPI)

    def test_passes_base_url(self):
        provider = ProviderFactory.create(
            ProviderType.FREELLMAPI,
            api_key="freellmapi-test-key",
            base_url="http://myserver:9000/v1",
        )
        assert provider.base_url == "http://myserver:9000/v1"


class TestStoredConfig:
    def test_defaults(self):
        config = StoredConfig()
        assert config.freellmapi_api_key is None
        assert config.freellmapi_base_url == "http://localhost:3001/v1"
