"""mockllm: a local fake of the Anthropic, OpenAI and Gemini HTTP APIs, with faults on demand."""

from .server import MockConfig, serve, start_in_thread

__all__ = ["MockConfig", "serve", "start_in_thread"]
