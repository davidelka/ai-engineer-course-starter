"""Configuration from the environment (twelve-factor style), with secrets handled carefully.

Everything that changes between laptop, compose and AWS comes from environment
variables, never from the image:

  LLM_MODEL               "auto" (default), or any llmkit spec: "mock:claude-haiku-5-5",
                          "anthropic:claude-haiku-5-5", ...
                          auto = anthropic:claude-haiku-5-5 when a key is available,
                                 mock:claude-haiku-5-5 (the free local mockllm) otherwise
  ANTHROPIC_API_KEY       the key itself (ECS injects it from Secrets Manager this way)
  ANTHROPIC_API_KEY_FILE  OR a path to a file that holds the key (docker compose secrets
                          mount it at /run/secrets/<name>); the file wins over the variable
  MOCKLLM_URL             where mockllm listens (compose: http://mockllm:8765)
  MAX_TOKENS              cap for one answer (default 400)
  APP_VERSION             set at build time, shown by /healthz so you know what is running

The key is never logged, never returned by an endpoint, and hidden from repr().
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Optional

DEFAULT_REAL_MODEL = "anthropic:claude-haiku-5-5"
DEFAULT_MOCK_MODEL = "mock:claude-haiku-5-5"
SYSTEM_PROMPT = (
    "You are Company Brain, Acme Ltd.'s internal assistant. Answer briefly and factually. "
    "If you do not know, say so."
)


class SettingsError(ValueError):
    pass


@dataclass(frozen=True)
class Settings:
    llm_model: str
    api_key: Optional[str] = field(default=None, repr=False)  # repr=False: never printed
    key_source: str = "none"  # "file" | "env" | "none": safe to log
    mockllm_url: str = "http://127.0.0.1:8765"
    max_tokens: int = 400
    app_version: str = "dev"
    system_prompt: str = SYSTEM_PROMPT

    @property
    def is_mock(self) -> bool:
        return self.llm_model.split(":", 1)[0].startswith("mock")

    def describe(self) -> dict:
        """What is safe to log at startup."""
        return {"llm_model": self.llm_model, "key_source": self.key_source, "is_mock": self.is_mock,
                "mockllm_url": self.mockllm_url if self.is_mock else None,
                "max_tokens": self.max_tokens, "app_version": self.app_version}

    @classmethod
    def from_env(cls, env: Optional[Mapping[str, str]] = None) -> "Settings":
        env = os.environ if env is None else env
        key, source = None, "none"
        key_file = env.get("ANTHROPIC_API_KEY_FILE", "").strip()
        if key_file:
            p = Path(key_file)
            if not p.is_file():
                raise SettingsError(f"ANTHROPIC_API_KEY_FILE points to a missing file: {key_file}")
            key, source = p.read_text(encoding="utf-8").strip() or None, "file"
        elif env.get("ANTHROPIC_API_KEY", "").strip():
            key, source = env["ANTHROPIC_API_KEY"].strip(), "env"
        model = env.get("LLM_MODEL", "auto").strip() or "auto"
        if model == "auto":
            model = DEFAULT_REAL_MODEL if key else DEFAULT_MOCK_MODEL
        if ":" not in model:
            raise SettingsError(f"LLM_MODEL must look like provider:model, got {model!r}")
        if model.startswith("anthropic:") and not key:
            raise SettingsError("LLM_MODEL is an Anthropic model but no key was provided "
                                "(set ANTHROPIC_API_KEY or ANTHROPIC_API_KEY_FILE)")
        try:
            max_tokens = int(env.get("MAX_TOKENS", "400"))
        except ValueError:
            raise SettingsError("MAX_TOKENS must be an integer") from None
        if not 1 <= max_tokens <= 4096:
            raise SettingsError("MAX_TOKENS must be between 1 and 4096")
        return cls(llm_model=model, api_key=key, key_source=source,
                   mockllm_url=env.get("MOCKLLM_URL", "http://127.0.0.1:8765").rstrip("/"),
                   max_tokens=max_tokens, app_version=env.get("APP_VERSION", "dev"))
