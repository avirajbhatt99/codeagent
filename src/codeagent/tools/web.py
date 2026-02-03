"""Web fetching and HTTP tools."""

import json
import re
from typing import Any
from urllib.parse import urlparse

import httpx

from codeagent.core.exceptions import ToolExecutionError
from codeagent.tools.base import Tool, ToolParameter


class WebFetchTool(Tool):
    """Tool for fetching content from URLs."""

    # Maximum content size to return (in characters)
    MAX_CONTENT_SIZE = 50000

    # Request timeout in seconds
    DEFAULT_TIMEOUT = 30

    # User agent to use for requests
    USER_AGENT = "CodeAgent/1.0 (https://github.com/avirajbhatt99/codeagent)"

    def __init__(self, timeout: int = DEFAULT_TIMEOUT) -> None:
        """Initialize the web fetch tool."""
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "web_fetch"

    @property
    def description(self) -> str:
        return (
            "Fetch content from a URL. Returns the text content of the page. "
            "Useful for reading documentation, API responses, or any web content. "
            "Supports HTML (converted to readable text), JSON, and plain text."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="url",
                type="string",
                description="The URL to fetch content from",
                required=True,
            ),
            ToolParameter(
                name="timeout",
                type="integer",
                description="Request timeout in seconds (default: 30, max: 120)",
                required=False,
                default=30,
            ),
        ]

    def _strip_html_tags(self, html: str) -> str:
        """Convert HTML to readable plain text."""
        # Remove script and style elements
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)

        # Convert common block elements to newlines
        html = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
        html = re.sub(r'</(p|div|h[1-6]|li|tr)>', '\n', html, flags=re.IGNORECASE)
        html = re.sub(r'<(p|div|h[1-6]|li|tr)[^>]*>', '\n', html, flags=re.IGNORECASE)

        # Remove all remaining HTML tags
        html = re.sub(r'<[^>]+>', '', html)

        # Decode common HTML entities
        html = html.replace('&nbsp;', ' ')
        html = html.replace('&lt;', '<')
        html = html.replace('&gt;', '>')
        html = html.replace('&amp;', '&')
        html = html.replace('&quot;', '"')
        html = html.replace('&#39;', "'")

        # Clean up whitespace
        html = re.sub(r'\n\s*\n', '\n\n', html)
        html = re.sub(r' +', ' ', html)

        return html.strip()

    def _is_json_response(self, content_type: str) -> bool:
        """Check if the response is JSON."""
        return 'application/json' in content_type.lower()

    def _is_html_response(self, content_type: str) -> bool:
        """Check if the response is HTML."""
        return 'text/html' in content_type.lower()

    def execute(
        self,
        url: str,
        timeout: int | None = None,
        **kwargs: Any,
    ) -> str:
        """
        Fetch content from a URL.

        Args:
            url: The URL to fetch
            timeout: Optional timeout override

        Returns:
            The fetched content as text
        """
        # Validate URL
        try:
            parsed = urlparse(url)
            if not parsed.scheme:
                url = f"https://{url}"
                parsed = urlparse(url)
            if parsed.scheme not in ('http', 'https'):
                raise ValueError("Only HTTP(S) URLs are supported")
        except Exception as e:
            raise ToolExecutionError(self.name, f"Invalid URL: {e}")

        effective_timeout = min(timeout or self._timeout, 120)

        try:
            with httpx.Client(
                timeout=effective_timeout,
                follow_redirects=True,
                headers={"User-Agent": self.USER_AGENT},
            ) as client:
                response = client.get(url)
                response.raise_for_status()

                content_type = response.headers.get('content-type', '')
                content = response.text

                # Format based on content type
                if self._is_json_response(content_type):
                    try:
                        data = response.json()
                        content = json.dumps(data, indent=2)
                    except json.JSONDecodeError:
                        pass  # Keep as raw text
                elif self._is_html_response(content_type):
                    content = self._strip_html_tags(content)

                # Truncate if too large
                if len(content) > self.MAX_CONTENT_SIZE:
                    content = content[:self.MAX_CONTENT_SIZE] + "\n\n... (content truncated)"

                return f"URL: {url}\nStatus: {response.status_code}\n\n{content}"

        except httpx.TimeoutException:
            raise ToolExecutionError(
                self.name,
                f"Request timed out after {effective_timeout} seconds",
            )
        except httpx.HTTPStatusError as e:
            raise ToolExecutionError(
                self.name,
                f"HTTP error {e.response.status_code}: {e.response.reason_phrase}",
            )
        except httpx.RequestError as e:
            raise ToolExecutionError(
                self.name,
                f"Request failed: {e}",
            )


class HttpRequestTool(Tool):
    """Tool for making HTTP requests (API testing)."""

    DEFAULT_TIMEOUT = 30
    MAX_BODY_SIZE = 50000

    def __init__(self, timeout: int = DEFAULT_TIMEOUT) -> None:
        """Initialize the HTTP request tool."""
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "http_request"

    @property
    def description(self) -> str:
        return (
            "Make an HTTP request to an API endpoint. Supports GET, POST, PUT, PATCH, DELETE methods. "
            "Useful for testing APIs, making webhook calls, or interacting with REST services. "
            "Returns status code, headers, and response body."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="url",
                type="string",
                description="The URL to send the request to",
                required=True,
            ),
            ToolParameter(
                name="method",
                type="string",
                description="HTTP method (GET, POST, PUT, PATCH, DELETE)",
                required=False,
                default="GET",
                enum=["GET", "POST", "PUT", "PATCH", "DELETE"],
            ),
            ToolParameter(
                name="headers",
                type="object",
                description="Request headers as key-value pairs (e.g., {\"Authorization\": \"Bearer token\"})",
                required=False,
            ),
            ToolParameter(
                name="body",
                type="string",
                description="Request body (for POST, PUT, PATCH). Can be JSON string or form data.",
                required=False,
            ),
            ToolParameter(
                name="timeout",
                type="integer",
                description="Request timeout in seconds (default: 30, max: 120)",
                required=False,
                default=30,
            ),
        ]

    def execute(
        self,
        url: str,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        body: str | None = None,
        timeout: int | None = None,
        **kwargs: Any,
    ) -> str:
        """
        Make an HTTP request.

        Args:
            url: The URL to request
            method: HTTP method
            headers: Request headers
            body: Request body
            timeout: Optional timeout override

        Returns:
            Response details including status, headers, and body
        """
        method = method.upper()
        if method not in ("GET", "POST", "PUT", "PATCH", "DELETE"):
            raise ToolExecutionError(self.name, f"Unsupported HTTP method: {method}")

        # Validate URL
        try:
            parsed = urlparse(url)
            if not parsed.scheme:
                url = f"https://{url}"
            if parsed.scheme not in ('http', 'https'):
                raise ValueError("Only HTTP(S) URLs are supported")
        except Exception as e:
            raise ToolExecutionError(self.name, f"Invalid URL: {e}")

        effective_timeout = min(timeout or self._timeout, 120)
        request_headers = {"User-Agent": "CodeAgent/1.0"}

        if headers:
            request_headers.update(headers)

        # Parse body - try JSON first
        content = None
        json_data = None
        if body:
            try:
                json_data = json.loads(body)
                if "Content-Type" not in request_headers:
                    request_headers["Content-Type"] = "application/json"
            except json.JSONDecodeError:
                content = body

        try:
            with httpx.Client(
                timeout=effective_timeout,
                follow_redirects=True,
            ) as client:
                response = client.request(
                    method=method,
                    url=url,
                    headers=request_headers,
                    json=json_data,
                    content=content,
                )

                # Format response
                result_parts = [
                    f"Status: {response.status_code} {response.reason_phrase}",
                    f"URL: {response.url}",
                    "",
                    "Response Headers:",
                ]

                for key, value in response.headers.items():
                    result_parts.append(f"  {key}: {value}")

                result_parts.append("")
                result_parts.append("Response Body:")

                # Try to format JSON responses
                content_type = response.headers.get('content-type', '')
                body_text = response.text

                if 'application/json' in content_type:
                    try:
                        body_text = json.dumps(response.json(), indent=2)
                    except json.JSONDecodeError:
                        pass

                if len(body_text) > self.MAX_BODY_SIZE:
                    body_text = body_text[:self.MAX_BODY_SIZE] + "\n\n... (body truncated)"

                result_parts.append(body_text if body_text else "(empty body)")

                return "\n".join(result_parts)

        except httpx.TimeoutException:
            raise ToolExecutionError(
                self.name,
                f"Request timed out after {effective_timeout} seconds",
            )
        except httpx.RequestError as e:
            raise ToolExecutionError(
                self.name,
                f"Request failed: {e}",
            )
