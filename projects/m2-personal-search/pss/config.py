"""Settings: one YAML file, every privacy decision in one place.

Lookup order: --config PATH, then $PSS_CONFIG, then ~/.config/pss/config.yaml, then the
built-in defaults below (which point at the project's sample folder). config.example.yaml in
the project shows every field with a comment.

The defaults are the privacy-safe ones: cloud disabled, redaction on, a list of folders that
never go to the cloud even when cloud is enabled, and excludes for secrets and hidden files.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional, Union

PROJECT = Path(__file__).resolve().parent.parent
SAMPLE = PROJECT / "data" / "sample"

DEFAULT_EXCLUDES = [
    ".*",                 # hidden files and folders (.git, .cache, .ssh, .env ...)
    "private/",           # any folder named private
    "node_modules/",
    "__pycache__/",
    "*.key", "*.pem", "*.kdbx", "*.gpg",      # keys and password databases
    "*password*", "*secret*",
    "*.tmp", "~$*",       # editor temp files, Office lock files
]


@dataclass
class CloudSettings:
    enabled: bool = False                   # the master switch: nothing leaves the machine unless True
    model: str = "anthropic:claude-haiku-5-5"
    redact: bool = True                     # redact_for_cloud on every byte that is sent
    never_send: list[str] = field(default_factory=lambda: ["health/", "finance/"])
    max_sources: int = 5
    max_chars_per_source: int = 1200


@dataclass
class Settings:
    roots: list[str] = field(default_factory=lambda: [str(SAMPLE)])
    index_dir: str = str(PROJECT / "state" / "sample")
    exclude: list[str] = field(default_factory=lambda: list(DEFAULT_EXCLUDES))
    max_file_mb: float = 25.0
    embedder: str = "fake"                  # e5-small on your machine (ragkit.embed spec)
    embed_cache_dir: str = str(Path.home() / ".cache" / "pss" / "embeddings")
    store: str = "numpy"                    # numpy (exact, saved to disk) | faiss (HNSW32 built at load)
    chunker: str = "recursive:220:30"       # ragkit.chunking spec, approx tokens
    ocr: str = "auto"                       # auto (if tesseract is installed) | on | off
    ocr_langs: str = "heb+eng"
    local_model: str = "ollama:qwen3.5:4b"  # or ollama:gemma4:e4b, ollama:gemma3:4b, extractive
    ollama_host: str = "http://localhost:11434"
    ollama_think: Optional[bool] = False    # thinking models (qwen3.x) answer faster without it
    answer_k: int = 5
    cloud: CloudSettings = field(default_factory=CloudSettings)
    host: str = "127.0.0.1"
    port: int = 8765

    # ---------------------------------------------------------------- derived
    @property
    def index_path(self) -> Path:
        return Path(self.index_dir).expanduser()

    @property
    def egress_log(self) -> Path:
        return self.index_path / "egress.jsonl"

    def index_signature(self) -> str:
        """What the index content depends on. If it changes, every file is re-indexed."""
        from .extract import ocr_status

        try:
            ocr_on, langs, _ = ocr_status(self.ocr, self.ocr_langs)
        except RuntimeError:
            ocr_on, langs = False, ""
        # the EFFECTIVE OCR languages: installing tesseract-ocr-heb later re-reads the images
        sig = {"embedder": self.embedder, "chunker": self.chunker, "ocr": langs if ocr_on else "off", "v": 1}
        return hashlib.sha256(json.dumps(sig, sort_keys=True).encode()).hexdigest()[:12]

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Settings":
        d = dict(d or {})
        cloud = CloudSettings(**(d.pop("cloud", None) or {}))
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        s = cls(**known)
        s.cloud = cloud
        return s


def config_path(explicit: Optional[Union[str, Path]] = None) -> Optional[Path]:
    for cand in (explicit, os.environ.get("PSS_CONFIG"), Path.home() / ".config" / "pss" / "config.yaml"):
        if cand and Path(cand).expanduser().exists():
            return Path(cand).expanduser()
    if explicit:
        raise FileNotFoundError(f"config file not found: {explicit}")
    return None


def load_settings(path: Optional[Union[str, Path]] = None, **overrides) -> Settings:
    p = config_path(path)
    data: dict = {}
    if p is not None:
        import yaml

        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    s = Settings.from_dict(data)
    for k, v in overrides.items():
        if v is not None:
            setattr(s, k, v)
    return s
