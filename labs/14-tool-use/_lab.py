"""Shared bits for the lesson 14 scripts: paths, .env, model choice, the mock server."""

from __future__ import annotations

import os
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
ROOT = LAB.parents[1]
sys.path[:0] = [str(ROOT), str(LAB)]

from llmkit import LLM, load_dotenv  # noqa: E402

DEFAULT_MODEL = "anthropic:claude-haiku-5-5"
RESULTS = LAB / "results"


def make_llm(spec: str, mock_cfg: dict | None = None) -> LLM:
    """'mock' (or mock-openai / mock-gemini) starts an in-process mock server: free, no key."""
    load_dotenv(str(ROOT / ".env"))
    if spec.startswith("mock"):
        from mockllm import MockConfig, start_in_thread
        cfg = MockConfig(ttft=0, tps=0, seed=1, **(mock_cfg or {}))
        server, url = start_in_thread(cfg)
        provider = spec.split("-", 1)[1] if "-" in spec else "anthropic"
        llm = LLM(f"{provider}:mock-model", api_key="mock", base_url=url)
        llm._mock_server = server  # keep a reference; daemon thread dies with the process
        return llm
    return LLM(spec)


def requests_db() -> Path:
    return Path(os.environ.get("ACME_REQUESTS_DB") or RESULTS / "requests.db")
