"""Settings from the environment (and the repo's .env), with an offline default for everything.

    MODE=offline   (default) fake embedder, offline extractive answerer, recorded SQL plans,
                   lexical groundedness judge. Free, no key, no download.
    MODE=mock      the REAL Anthropic adapter of llmkit over HTTP against mockllm (start it with
                   `python -m mockllm`): streaming, prompt caching usage fields, retries. Free.
    MODE=live      Claude Haiku 5.5 for answers, SQL plans and the judge; e5-small embeddings
                   (downloaded once by sentence-transformers, ~470 MB, cached on disk).

Every knob can be overridden on its own (EMBEDDER=e5-small with MODE=offline is fine: real
retrieval, free answers). Nothing here prints a key.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

PROJECT = Path(__file__).resolve().parent.parent
ROOT = PROJECT.parents[1]
DOCS_DIR = ROOT / "data" / "acme" / "corpus" / "docs"
QA_PATH = ROOT / "data" / "acme" / "corpus" / "golden" / "qa.jsonl"
DATA_QUESTIONS = PROJECT / "data" / "data_questions.jsonl"

DEFAULT_MODEL = "anthropic:claude-haiku-5-5"


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


@dataclass
class Settings:
    mode: str = "offline"                     # offline | mock | live
    embedder: str = "fake"                    # fake | e5-small | e5-base | bge-m3 | openai:...
    llm_model: str = DEFAULT_MODEL
    judge_model: str = DEFAULT_MODEL
    mock_url: str = "http://127.0.0.1:8765"
    rerank: str = ""                          # "" (off) | fake | ce:bge-m3 | llm:anthropic:claude-haiku-5-5
    version_mode: str = "retrieved"           # retrieved | corpus | recent | off
    chunker: str = "heading:400:40"
    k: int = 6                                # max chunks in the prompt
    fetch_k: int = 30                         # candidates before packing
    context_tokens: int = 1800                # budget of the sources block
    max_per_doc: int = 2
    docs_dir: Path = DOCS_DIR
    index_dir: Optional[Path] = None          # default: PROJECT/.index/<embedder>
    cache_dir: Path = field(default_factory=lambda: ROOT / ".cache" / "embeddings")
    results_dir: Path = field(default_factory=lambda: PROJECT / "results")
    trace_file: Optional[Path] = None         # JSONL of spans (obskit); None = in memory only
    replay_file: Optional[Path] = None        # answers recorded from a live run (eval --record)
    reference: bool = False                   # force the reference implementations (ignore mine.py)

    @classmethod
    def from_env(cls, **overrides: Any) -> "Settings":
        try:
            from llmkit import load_dotenv
            load_dotenv(str(ROOT / ".env"))
        except Exception:  # noqa: BLE001  (no .env is fine)
            pass
        mode = _env("MODE", "offline") or "offline"
        s = cls(
            mode=mode,
            embedder=_env("EMBEDDER") or ("e5-small" if mode == "live" else "fake"),
            llm_model=_env("LLM_MODEL", DEFAULT_MODEL),
            judge_model=_env("JUDGE_MODEL", DEFAULT_MODEL),
            mock_url=_env("MOCK_URL", "http://127.0.0.1:8765"),
            rerank=_env("RERANK", ""),
            version_mode=_env("VERSION_MODE", "retrieved"),
            k=int(_env("TOP_K", "6")),
            trace_file=Path(_env("TRACE_FILE")) if _env("TRACE_FILE") else None,
        )
        for k, v in overrides.items():
            setattr(s, k, v)
        return s

    # ---------------------------------------------------------------- derived
    @property
    def index_path(self) -> Path:
        if self.index_dir:
            return Path(self.index_dir)
        safe = self.embedder.replace(":", "_").replace("/", "_")
        return PROJECT / ".index" / safe

    def describe(self) -> str:
        return (f"mode={self.mode} embedder={self.embedder} llm={self.answer_model_name} "
                f"rerank={self.rerank or 'off'} versions={self.version_mode} k={self.k}")

    @property
    def answer_model_name(self) -> str:
        if self.replay_file:
            return f"replay:{Path(self.replay_file).name}"
        return {"offline": "offline-extractive", "mock": "mockllm"}.get(self.mode, self.llm_model)

    # ---------------------------------------------------------------- factories
    def make_embedder(self):
        from ragkit.embed import make_embedder
        return make_embedder(self.embedder, cache_dir=None if self.embedder.startswith("fake") else self.cache_dir)

    def make_llm(self):
        """The answer model: anything with complete(ChatRequest) and stream(ChatRequest)."""
        from .answer import OfflineAnswerer, ReplayAnswerer
        if self.replay_file:
            return ReplayAnswerer(self.replay_file)
        if self.mode == "offline":
            return OfflineAnswerer()
        from llmkit import LLM, RetryPolicy
        if self.mode == "mock":
            return LLM("anthropic:claude-haiku-5-5", api_key="mock", base_url=self.mock_url,
                       retry=RetryPolicy(max_attempts=3))
        return LLM(self.llm_model, retry=RetryPolicy(max_attempts=3))

    def make_data_llm(self):
        """The text-to-SQL model. Offline and mock: recorded plans (datakit's replay_llm)."""
        if self.mode == "live":
            from llmkit import LLM, RetryPolicy
            return LLM(self.llm_model, retry=RetryPolicy(max_attempts=3))
        from .router import offline_data_llm
        return offline_data_llm()

    def make_judge_llm(self):
        """The groundedness judge (ragkit.diagnose.check_claims). Offline: a lexical stand-in."""
        if self.mode == "live":
            from llmkit import LLM, RetryPolicy
            return LLM(self.judge_model, retry=RetryPolicy(max_attempts=3))
        from ragkit.diagnose import heuristic_judge_llm
        return heuristic_judge_llm()
