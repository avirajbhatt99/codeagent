"""
CodeAgent - AI-powered coding assistant CLI.

A flexible CLI tool that works with multiple LLM providers:
- Ollama (local models)
- OpenRouter (cloud models)
- HuggingFace (inference API)
"""

__version__ = "0.1.0"
__author__ = "Your Name"

from codeagent.core.agent import Agent
from codeagent.core.types import Message, Role

__all__ = ["Agent", "Message", "Role", "__version__"]
