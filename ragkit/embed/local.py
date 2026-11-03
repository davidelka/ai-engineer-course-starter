"""Local open embedding models through sentence-transformers (runs on a laptop CPU).

    emb = SentenceTransformerEmbedder.preset("e5-small")       # downloads ~470 MB once
    vecs = emb.embed_documents([c.context_text() for c in chunks])
    q = emb.embed_query("כמה ימי חופשה אפשר להעביר?")

The first use downloads the weights from Hugging Face into ~/.cache/huggingface; after that
it works offline. sentence-transformers needs PyTorch: on a Linux laptop without a GPU,
install the CPU wheel first (much smaller than the default CUDA build):
    uv pip install torch --index-url https://download.pytorch.org/whl/cpu
    uv pip install sentence-transformers

PRESETS (checked on the Hugging Face model cards, November 2026):
- e5-small   intfloat/multilingual-e5-small   ~118M params, 384 dims, 512 tokens, MIT.
             The default: fast on CPU, ~100 languages incl. Hebrew. Needs "query: " /
             "passage: " prefixes ("otherwise you will see a performance degradation").
- e5-base    intfloat/multilingual-e5-base    ~278M params, 768 dims, 512 tokens, MIT.
- bge-m3     BAAI/bge-m3                      ~568M params, 1024 dims, 8192 tokens, MIT.
             No prefixes needed. Strong multilingual model, ~2.3 GB download.
- qwen3-0.6b Qwen/Qwen3-Embedding-0.6B        0.6B params, up to 1024 dims, Apache-2.0.
             Trained with Matryoshka (any dims 32..1024); queries use the model's built-in
             "query" prompt (an instruction), documents use none.
Any other model: SentenceTransformerEmbedder("org/name", query_prefix=..., passage_prefix=...).
"""

from __future__ import annotations

from typing import Any, Optional

import numpy as np

from .base import BaseEmbedder

PRESETS: dict[str, dict[str, Any]] = {
    "e5-small": {"name": "intfloat/multilingual-e5-small", "query_prefix": "query: ",
                 "passage_prefix": "passage: ", "dim": 384},
    "e5-base": {"name": "intfloat/multilingual-e5-base", "query_prefix": "query: ",
                "passage_prefix": "passage: ", "dim": 768},
    "bge-m3": {"name": "BAAI/bge-m3", "dim": 1024},
    "qwen3-0.6b": {"name": "Qwen/Qwen3-Embedding-0.6B", "query_prompt_name": "query", "dim": 1024},
}


class SentenceTransformerEmbedder(BaseEmbedder):
    def __init__(self, name: str, *, query_prefix: str = "", passage_prefix: str = "",
                 query_prompt_name: Optional[str] = None, dim: Optional[int] = None,
                 device: Optional[str] = None, batch_size: int = 32, show_progress: bool = False,
                 model: Any = None):
        self.name = name
        self.query_prefix, self.passage_prefix = query_prefix, passage_prefix
        self.query_prompt_name = query_prompt_name
        self.device = device
        self.encode_batch_size = batch_size       # sentence-transformers' own batching
        self.batch_size = 100_000                 # so BaseEmbedder sends one encode() call
        self.show_progress = show_progress
        self.normalized = True
        self.dim = dim or 0
        self._model = model                       # tests inject a stub; normally lazy-loaded
        p = f"|q={query_prefix!r}|p={passage_prefix!r}" if (query_prefix or passage_prefix) else ""
        p += f"|qprompt={query_prompt_name}" if query_prompt_name else ""
        self.model_id = f"st:{name}{p}"

    @classmethod
    def preset(cls, key: str, **kw) -> "SentenceTransformerEmbedder":
        if key not in PRESETS:
            raise ValueError(f"unknown preset {key!r}; known: {sorted(PRESETS)}")
        return cls(**{**PRESETS[key], **kw})

    @property
    def model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer  # type: ignore
            except ImportError as exc:  # pragma: no cover - depends on the environment
                raise ImportError(
                    "local embeddings need sentence-transformers (and PyTorch):\n"
                    "  uv pip install torch --index-url https://download.pytorch.org/whl/cpu\n"
                    "  uv pip install sentence-transformers\n"
                    "or run with --model fake (offline, not semantic)") from exc
            self._model = SentenceTransformer(self.name, device=self.device)
        return self._model

    def _embed(self, texts: list[str], kind: str) -> np.ndarray:
        prefix = self.query_prefix if kind == "query" else self.passage_prefix
        kw: dict[str, Any] = {"batch_size": self.encode_batch_size, "normalize_embeddings": True,
                              "convert_to_numpy": True, "show_progress_bar": self.show_progress}
        if kind == "query" and self.query_prompt_name:
            kw["prompt_name"] = self.query_prompt_name
        out = self.model.encode([prefix + t for t in texts], **kw)
        return np.asarray(out, dtype=np.float32)
