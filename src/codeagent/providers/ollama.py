"""
Ollama provider for local LLM inference.

Ollama runs models locally, providing privacy and no API costs.
See: https://ollama.ai
"""

import json
import logging
from typing import Any, Generator, Optional

from codeagent.core.exceptions import APIError, ModelNotFoundError
from codeagent.core.types import LLMResponse, StreamChunk, ToolCall
from codeagent.providers.base import LLMProvider

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    """
    Ollama provider for running local models.

    Requires Ollama to be installed and running locally.
    Install from: https://ollama.ai/download
    """

    name = "ollama"

    # Models with good tool-calling support
    RECOMMENDED_MODELS = [
        "qwen2.5-coder:7b",
        "qwen2.5-coder:14b",
        "qwen2.5-coder:32b",
        "qwen2.5:7b",
        "qwen2.5:14b",
        "llama3.1:8b",
        "llama3.1:70b",
        "mistral:7b",
        "mixtral:8x7b",
        "deepseek-coder-v2:16b",
        "codellama:7b",
        "codellama:13b",
    ]

    def __init__(
        self,
        model: Optional[str] = None,
        host: Optional[str] = None,
    ) -> None:
        """
        Initialize Ollama provider.

        Args:
            model: Model name to use (e.g., 'qwen2.5-coder:7b')
            host: Ollama server URL (default: http://localhost:11434)
        """
        try:
            import ollama
        except ImportError as e:
            raise ImportError(
                "Ollama package not installed. Run: pip install ollama"
            ) from e

        self.model = model or self.get_default_model()
        self._host = host
        self._client = ollama.Client(host=host) if host else ollama

    @classmethod
    def get_default_model(cls) -> str:
        return "qwen2.5-coder:7b"

    @classmethod
    def list_models(cls) -> list[str]:
        return cls.RECOMMENDED_MODELS

    @property
    def supports_streaming(self) -> bool:
        return True

    def get_local_models(self) -> list[str]:
        """Get list of models currently downloaded in Ollama."""
        try:
            response = self._client.list()
            return [m["name"] for m in response.get("models", [])]
        except Exception as e:
            logger.warning(f"Failed to list local models: {e}")
            return []

    def pull_model(self, model: Optional[str] = None) -> None:
        """
        Pull a model from Ollama registry.

        Args:
            model: Model name to pull (uses configured model if not specified)
        """
        model_name = model or self.model
        logger.info(f"Pulling model: {model_name}")
        self._client.pull(model_name)

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> LLMResponse:
        """Send a chat request to Ollama."""
        import ollama

        try:
            kwargs: dict[str, Any] = {
                "model": self.model,
                "messages": messages,
            }
            if tools:
                kwargs["tools"] = tools

            response = self._client.chat(**kwargs)
            return self._parse_response(response, tools=tools)

        except ollama.ResponseError as e:
            if "model" in str(e).lower() and "not found" in str(e).lower():
                raise ModelNotFoundError(self.model, self.name) from e
            raise APIError(self.name, str(e)) from e

    def stream(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> Generator[StreamChunk, None, None]:
        """Stream a chat response from Ollama.

        Some local models (qwen2.5-coder, some llama variants) emit tool calls
        as JSON in `message.content` instead of in the structured `tool_calls`
        field. To avoid spraying that JSON at the user, we buffer content until
        we know whether it's a real text reply or a tool-call hallucination.
        """
        import ollama

        try:
            kwargs: dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "stream": True,
            }
            if tools:
                kwargs["tools"] = tools

            buffered = ""
            buffering = True  # hold output until we know if it's tool-call JSON
            yielded_any = False
            tool_calls: list[ToolCall] = []
            tool_names = self._collect_tool_names(tools)

            for chunk in self._client.chat(**kwargs):
                msg = chunk.get("message", {})

                content = msg.get("content") or ""
                if content:
                    buffered += content
                    if buffering:
                        # If the buffer is clearly *not* tool-call JSON, flush.
                        if not self._looks_like_tool_call_start(buffered):
                            yield StreamChunk(content=buffered)
                            yielded_any = True
                            buffering = False
                            buffered = ""
                    else:
                        yield StreamChunk(content=content)

                # Native structured tool_calls (proper path)
                if msg.get("tool_calls"):
                    for tc in msg["tool_calls"]:
                        tool_calls.append(self._parse_tool_call(tc, len(tool_calls)))

                if chunk.get("done"):
                    # No native tool_calls — try to recover one from buffered content
                    if not tool_calls and buffering and buffered.strip():
                        recovered = self._extract_tool_calls_from_text(buffered, tool_names)
                        if recovered:
                            tool_calls = recovered
                            buffered = ""  # don't show the JSON
                        else:
                            # Real text after all — flush whatever we held back
                            yield StreamChunk(content=buffered)
                            yielded_any = True
                            buffered = ""
                    elif buffered:
                        # Had buffered content + native tool_calls arrived. The
                        # buffered text is likely the model's prelude; emit it.
                        yield StreamChunk(content=buffered)
                        yielded_any = True
                        buffered = ""

                    yield StreamChunk(
                        content="",
                        tool_calls=tool_calls,
                        is_complete=True,
                        finish_reason="stop" if not tool_calls else "tool_calls",
                    )

        except ollama.ResponseError as e:
            raise APIError(self.name, f"Streaming error: {e}") from e

    def _parse_response(
        self,
        response: dict[str, Any],
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> LLMResponse:
        """Parse Ollama response into LLMResponse.

        Falls back to recovering tool calls from `message.content` if the model
        embedded them as JSON instead of using the native `tool_calls` field.
        """
        msg = response.get("message", {})
        content = msg.get("content") or ""
        tool_calls: list[ToolCall] = []

        if msg.get("tool_calls"):
            for i, tc in enumerate(msg["tool_calls"]):
                tool_calls.append(self._parse_tool_call(tc, i))

        if not tool_calls and content.strip():
            recovered = self._extract_tool_calls_from_text(
                content, self._collect_tool_names(tools)
            )
            if recovered:
                tool_calls = recovered
                content = ""  # swallow the JSON; the tool call replaces it

        return LLMResponse(
            content=content or None,
            tool_calls=tool_calls,
            finish_reason="stop" if not tool_calls else "tool_calls",
        )

    @staticmethod
    def _collect_tool_names(tools: Optional[list[dict[str, Any]]]) -> set[str]:
        """Pull the registered tool names out of an OpenAI-format schema list."""
        names: set[str] = set()
        for t in tools or []:
            fn = (t.get("function") or {}) if isinstance(t, dict) else {}
            name = fn.get("name")
            if isinstance(name, str):
                names.add(name)
        return names

    @staticmethod
    def _looks_like_tool_call_start(buf: str) -> bool:
        """Cheap prefix test to decide whether to keep buffering content."""
        s = buf.lstrip()
        if not s:
            return True  # still empty, keep waiting
        if s.startswith("```"):
            return True  # fenced JSON block
        if s.startswith("{") or s.startswith("["):
            return True
        return False

    @classmethod
    def _extract_tool_calls_from_text(
        cls, text: str, tool_names: set[str]
    ) -> list[ToolCall]:
        """Try hard to find tool-call JSON inside free-form model output."""
        candidates = cls._candidate_json_blobs(text)
        out: list[ToolCall] = []
        for blob in candidates:
            try:
                parsed = json.loads(blob)
            except (json.JSONDecodeError, ValueError):
                continue
            for obj in parsed if isinstance(parsed, list) else [parsed]:
                tc = cls._tool_call_from_obj(obj, tool_names, len(out))
                if tc is not None:
                    out.append(tc)
            if out:
                return out  # first viable blob wins
        return out

    @staticmethod
    def _candidate_json_blobs(text: str) -> list[str]:
        """Extract JSON-shaped fragments from free-form text.

        Handles:
          - bare object/array at the start
          - fenced ```json ... ``` blocks
          - object/array embedded mid-paragraph
        """
        blobs: list[str] = []
        s = text.strip()

        # Strip code fences if present
        if s.startswith("```"):
            # ```json\n{...}\n```   or   ```\n{...}\n```
            inner = s.split("\n", 1)[1] if "\n" in s else ""
            if inner.endswith("```"):
                inner = inner[:-3]
            s = inner.strip()

        # Greedy balanced-bracket scan starting at each '{' or '['.
        for i, ch in enumerate(text):
            if ch not in "{[":
                continue
            open_ch, close_ch = ch, "}" if ch == "{" else "]"
            depth = 0
            in_str = False
            esc = False
            for j in range(i, len(text)):
                c = text[j]
                if esc:
                    esc = False
                    continue
                if c == "\\" and in_str:
                    esc = True
                    continue
                if c == '"':
                    in_str = not in_str
                    continue
                if in_str:
                    continue
                if c == open_ch:
                    depth += 1
                elif c == close_ch:
                    depth -= 1
                    if depth == 0:
                        blobs.append(text[i : j + 1])
                        break

        # Also try the fence-stripped version as a first-class candidate.
        if s and s not in blobs:
            blobs.insert(0, s)
        return blobs

    @staticmethod
    def _tool_call_from_obj(
        obj: Any, tool_names: set[str], idx: int
    ) -> Optional[ToolCall]:
        """Map a parsed JSON object to a ToolCall if it looks tool-shaped."""
        if not isinstance(obj, dict):
            return None

        # Shape 1: {"name": "...", "arguments": {...}}
        name = obj.get("name")
        args = obj.get("arguments")
        if isinstance(name, str):
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except (json.JSONDecodeError, ValueError):
                    args = {}
            if args is None:
                args = obj.get("parameters") or {}
            if not tool_names or name in tool_names:
                return ToolCall(
                    id=f"recovered_{idx}",
                    name=name,
                    arguments=args if isinstance(args, dict) else {},
                )

        # Shape 2: {"function": {"name": ..., "arguments": ...}}
        fn = obj.get("function")
        if isinstance(fn, dict):
            fname = fn.get("name")
            fargs = fn.get("arguments")
            if isinstance(fargs, str):
                try:
                    fargs = json.loads(fargs)
                except (json.JSONDecodeError, ValueError):
                    fargs = {}
            if isinstance(fname, str) and (not tool_names or fname in tool_names):
                return ToolCall(
                    id=obj.get("id", f"recovered_{idx}"),
                    name=fname,
                    arguments=fargs if isinstance(fargs, dict) else {},
                )
        return None

    def _parse_tool_call(self, tc: dict[str, Any], index: int) -> ToolCall:
        """Parse a single tool call from Ollama response."""
        func = tc.get("function", {})
        arguments = func.get("arguments", {})

        # Handle string arguments (need to parse as JSON)
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                arguments = {}

        return ToolCall(
            id=tc.get("id", f"call_{index}"),
            name=func.get("name", ""),
            arguments=arguments,
        )
