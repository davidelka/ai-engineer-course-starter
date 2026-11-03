"""Settings from the environment (and the repo's .env). Every default is the free offline path.

    MODE=offline   (default) acmeqa's extractive answerer + fake embedder, flowkit's FakeLLM for the
                   workflow, the rule-based router stand-in. Free, no key, no download.
    MODE=mock      the knowledge answers go through llmkit's real Anthropic adapter to mockllm
                   (streaming, prompt-cache usage fields); the workflow and router stay offline.
    MODE=live      Claude Haiku 5.5 for answers, router, intake and risk summary; e5-small embeddings.
    MODE=sim       the obedient SIMULATED model from guardkit answers questions (security evaluation
                   only: it follows any instruction it finds, so the guard layers have work to do).

    LLM_PATH=direct    (default, "dev") the brain calls llmkit directly.
    LLM_PATH=gateway   ("production") every model call goes through gatewaykit: virtual key per
                   intent, budget, data-classification policy, redaction, audit. GATEWAY_URL set:
                   a running gateway over HTTP. Not set: an in-process Gateway (tests, demo).

    STATE_DIR      checkpoints.db, requests.db, index/, traces.jsonl, gateway audit (default: results/state)
    GUARDS         on (default) | off   (off = the M1 behavior: ACL only, for the security ladder)
    SQLITE_EXCLUSIVE=1  open checkpoints.db in EXCLUSIVE locking mode (AWS, state on EFS): LangGraph's
                   SqliteSaver turns on WAL, and WAL's shared-memory index does not work on a network file
                   system (sqlite.org/wal.html); in EXCLUSIVE mode SQLite keeps it in heap memory instead.
                   Only ONE process may then open the file: the API process (seed through POST /admin/seed).
    STRICT_OUTPUT  1 = hold streamed tokens until the output validator passed (no unsafe text ever
                   reaches the browser, at the price of time-to-first-token). Default 0: stream, then
                   replace the answer if the validator objects (the UI swaps the text).
    BRAIN_API_KEYS JSON {"user_id": "key", ...} (from Secrets Manager in AWS). Hashed at load.
    BRAIN_DEMO_KEYS=1  also accept the demo keys "demo-<user_id>" (local only, never in production)
    TRACE_FILE     JSONL of spans (default: STATE_DIR/traces.jsonl), OTLP_ENDPOINT optional (Phoenix)
Nothing here prints a key.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from . import PROJECT, ROOT

DEFAULT_MODEL = "anthropic:claude-haiku-5-5"
DATA = PROJECT / "data"
RESULTS = PROJECT / "results"


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


FILE_SECRETS = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "BRAIN_API_KEYS", "GATEWAY_KEY_ANSWER", "GATEWAY_KEY_FLOW",
                "GATEWAY_KEY_ROUTER")


def load_file_secrets() -> None:
    """NAME_FILE=/run/secrets/name -> NAME (compose secrets, ECS secrets mounted as files). The value is
    put in this process's environment and never printed."""
    for name in FILE_SECRETS:
        path = os.environ.get(f"{name}_FILE", "").strip()
        if path and not os.environ.get(name) and Path(path).is_file():
            os.environ[name] = Path(path).read_text(encoding="utf-8").strip()


def _flag(name: str, default: bool = False) -> bool:
    v = _env(name)
    return default if not v else v.lower() in ("1", "true", "yes", "on")


@dataclass
class BrainSettings:
    mode: str = "offline"                  # offline | mock | live | sim
    llm_path: str = "direct"               # direct | gateway
    llm_model: str = DEFAULT_MODEL
    mock_url: str = "http://127.0.0.1:8765"
    gateway_url: str = ""                  # "" = in-process gateway when llm_path == gateway
    gateway_config: Path = field(default_factory=lambda: DATA / "gateway" / "gateway.yaml")
    state_dir: Path = field(default_factory=lambda: RESULTS / "state")
    guards: bool = True
    strict_output: bool = False
    demo_keys: bool = False
    users_file: Path = field(default_factory=lambda: DATA / "users.json")
    trace_file: Optional[Path] = None
    otlp_endpoint: str = ""
    tracing: bool = True
    router_llm: str = "auto"               # auto (LLM only when the rules are unsure) | always | never
    embedder: str = ""                     # "" = acmeqa's default for the mode
    reference: bool = False                # force the reference functions (ignore mine.py)
    index_path: Optional[Path] = None      # share one built index between state dirs (evaluation, tests)
    sqlite_exclusive: bool = False         # SQLITE_EXCLUSIVE=1 on EFS: WAL without shared memory (one process only)

    @classmethod
    def from_env(cls, **overrides: Any) -> "BrainSettings":
        try:
            from llmkit import load_dotenv
            load_dotenv(str(ROOT / ".env"))
        except Exception:  # noqa: BLE001  (no .env is fine)
            pass
        load_file_secrets()
        s = cls(
            mode=_env("MODE", "offline") or "offline",
            llm_path=_env("LLM_PATH", "direct") or "direct",
            llm_model=_env("LLM_MODEL", DEFAULT_MODEL),
            mock_url=_env("MOCK_URL", "http://127.0.0.1:8765"),
            gateway_url=_env("GATEWAY_URL"),
            state_dir=Path(_env("STATE_DIR") or RESULTS / "state"),
            guards=_env("GUARDS", "on").lower() != "off",
            strict_output=_flag("STRICT_OUTPUT"),
            demo_keys=_flag("BRAIN_DEMO_KEYS"),
            trace_file=Path(_env("TRACE_FILE")) if _env("TRACE_FILE") else None,
            otlp_endpoint=_env("OTLP_ENDPOINT"),
            router_llm=_env("ROUTER_LLM", "auto") or "auto",
            embedder=_env("EMBEDDER"),
            reference=_flag("BRAIN_REFERENCE"),
            sqlite_exclusive=_flag("SQLITE_EXCLUSIVE"),
        )
        if _env("GATEWAY_CONFIG"):
            s.gateway_config = Path(_env("GATEWAY_CONFIG"))
        if _env("BRAIN_USERS_FILE"):
            s.users_file = Path(_env("BRAIN_USERS_FILE"))
        for k, v in overrides.items():
            setattr(s, k, v)
        s.state_dir = Path(s.state_dir)
        if s.mode not in ("offline", "mock", "live", "sim"):
            raise ValueError(f"MODE must be offline, mock, live or sim (got {s.mode!r})")
        if s.llm_path not in ("direct", "gateway"):
            raise ValueError(f"LLM_PATH must be direct or gateway (got {s.llm_path!r})")
        return s

    # ------------------------------------------------------------ derived paths
    @property
    def checkpoints_db(self) -> Path:
        return self.state_dir / "checkpoints.db"

    @property
    def requests_db(self) -> Path:
        return self.state_dir / "requests.db"

    @property
    def index_dir(self) -> Path:
        return Path(self.index_path) if self.index_path else self.state_dir / "index"

    @property
    def traces_path(self) -> Path:
        return self.trace_file or (self.state_dir / "traces.jsonl")

    @property
    def gateway_audit(self) -> Path:
        return self.state_dir / "gateway_audit.jsonl"

    def describe(self) -> str:
        return (f"mode={self.mode} llm_path={self.llm_path} guards={'on' if self.guards else 'off'} "
                f"router_llm={self.router_llm} state={self.state_dir}")
