"""
HuggingFace provider for Inference API access.

HuggingFace provides access to open-source models via their Inference API.
See: https://huggingface.co/docs/api-inference
"""

import json
import logging
import re
from typing import Any, Generator, Optional

from codeagent.core.exceptions import APIError, ProviderConfigError
from codeagent.core.types import LLMResponse, StreamChunk, ToolCall
from codeagent.providers.base import LLMProvider

logger = logging.getLogger(__name__)


class HuggingFaceProvider(LLMProvider):
    """
    HuggingFace Inference API provider.

    Uses prompt-based tool calling since HF Inference API
    doesn't natively support the OpenAI tool format.
    """

    name = "huggingface"

    RECOMMENDED_MODELS = [
        "Qwen/Qwen2.5-Coder-32B-Instruct",
        "deepseek-ai/DeepSeek-Coder-V2-Instruct",
        "codellama/CodeLlama-34b-Instruct-hf",
        "bigcode/starcoder2-15b-instruct-v0.1",
        "meta-llama/Meta-Llama-3.1-70B-Instruct",
        "mistralai/Mixtral-8x7B-Instruct-v0.1",
        "meta-llama/Meta-Llama-3.1-8B-Instruct",
    ]

    # Tool call format for prompt-based tool calling
    TOOL_CALL_PATTERN = re.compile(
        r"```tool_call\s*\n?({.*?})\s*\n?```",
        re.DOTALL,
    )

    def __init__(
        self,
        api_key: str,
        model: Optional[str] = None,
    ) -> None:
        """
        Initialize HuggingFace provider.

        Args:
            api_key: HuggingFace API token
            model: Model identifier (e.g., 'Qwen/Qwen2.5-Coder-32B-Instruct')
        """
        if not api_key:
            raise ProviderConfigError(
                self.name,
                "API token required. Get one at https://huggingface.co/settings/tokens",
            )

        try:
            from huggingface_hub import InferenceClient
        except ImportError as e:
            raise ImportError(
                "HuggingFace Hub not installed. Run: pip install huggingface-hub"
            ) from e

        self.model = model or self.get_default_model()
        self._api_key = api_key
        self._client = InferenceClient(token=api_key)

    @classmethod
    def get_default_model(cls) -> str:
        return "Qwen/Qwen2.5-Coder-32B-Instruct"

    @classmethod
    def list_models(cls) -> list[str]:
        return cls.RECOMMENDED_MODELS

    @property
    def supports_streaming(self) -> bool:
        return True

    @property
    def supports_tools(self) -> bool:
        # Uses prompt-based tool calling
        return True

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> LLMResponse:
        """Send a chat request to HuggingFace Inference API."""
        try:
            # Inject tools into prompt if provided
            if tools:
                messages = self._inject_tools_into_messages(messages, tools)

            response = self._client.chat_completion(
                model=self.model,
                messages=messages,
                max_tokens=4096,
            )

            content = response.choices[0].message.content or ""
            clean_content, tool_calls = self._extract_tool_calls(content)

            return LLMResponse(
                content=clean_content,
                tool_calls=tool_calls,
                finish_reason="tool_calls" if tool_calls else "stop",
            )

        except Exception as e:
            raise APIError(self.name, str(e)) from e

    def stream(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> Generator[StreamChunk, None, None]:
        """Stream a chat response from HuggingFace."""
        try:
            if tools:
                messages = self._inject_tools_into_messages(messages, tools)

            full_content = ""

            for chunk in self._client.chat_completion(
                model=self.model,
                messages=messages,
                max_tokens=4096,
                stream=True,
            ):
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_content += content
                    yield StreamChunk(content=content)

                if chunk.choices and chunk.choices[0].finish_reason:
                    _, tool_calls = self._extract_tool_calls(full_content)
                    yield StreamChunk(
                        content="",
                        tool_calls=tool_calls,
                        is_complete=True,
                        finish_reason=chunk.choices[0].finish_reason,
                    )

        except Exception as e:
            raise APIError(self.name, f"Streaming error: {e}") from e

    def _inject_tools_into_messages(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Inject tool definitions into the system message.

        Since HF doesn't support native tool calling, we use
        a prompt-based approach where the model outputs tool
        calls in a specific format.
        """
        tool_prompt = self._format_tools_prompt(tools)
        new_messages = messages.copy()

        # Find or create system message
        if new_messages and new_messages[0].get("role") == "system":
            new_messages[0] = {
                "role": "system",
                "content": f"{new_messages[0]['content']}\n\n{tool_prompt}",
            }
        else:
            new_messages.insert(0, {"role": "system", "content": tool_prompt})

        return new_messages

    def _format_tools_prompt(self, tools: list[dict[str, Any]]) -> str:
        """Format tools as a prompt string."""
        tool_descriptions = []

        for tool in tools:
            func = tool.get("function", {})
            name = func.get("name", "")
            desc = func.get("description", "")
            params = json.dumps(func.get("parameters", {}), indent=2)
            tool_descriptions.append(
                f"### {name}\n{desc}\n\nParameters:\n```json\n{params}\n```"
            )

        tools_text = "\n\n".join(tool_descriptions)

        return f"""You have access to the following tools. To use a tool, respond with a JSON block in this exact format:

```tool_call
{{"name": "tool_name", "arguments": {{"arg1": "value1"}}}}
```

Available tools:

{tools_text}

Important: When you need to use a tool, output ONLY the tool_call block without any other text before it. After you receive the tool result, you can continue your response."""

    def _extract_tool_calls(self, content: str) -> tuple[str, list[ToolCall]]:
        """
        Extract tool calls from model response content.

        Returns:
            Tuple of (cleaned content, list of tool calls)
        """
        tool_calls: list[ToolCall] = []

        matches = self.TOOL_CALL_PATTERN.findall(content)

        for i, match in enumerate(matches):
            try:
                data = json.loads(match)
                tool_calls.append(
                    ToolCall(
                        id=f"call_{i}",
                        name=data.get("name", ""),
                        arguments=data.get("arguments", {}),
                    )
                )
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse tool call: {match}")
                continue

        # Remove tool call blocks from content
        clean_content = self.TOOL_CALL_PATTERN.sub("", content).strip()

        return clean_content, tool_calls
