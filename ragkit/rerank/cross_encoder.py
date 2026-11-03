"""Local cross-encoder rerankers through sentence-transformers (runs on a laptop CPU).

    rr = CrossEncoderReranker.preset("bge-m3")          # BAAI/bge-reranker-v2-m3
    hits = rr.rerank("כמה ימי חופשה אפשר להעביר?", first_stage_hits, top_n=5)

A cross-encoder is a transformer that reads "[query] [SEP] [passage]" as ONE input and outputs
one relevance number. Because every query token can attend to every passage token, it sees
negation, which entity a number belongs to, and whether the passage answers THIS question;
a bi-encoder compressed each side into a vector before they ever met. The price: one forward
pass per (query, passage) pair at query time, nothing can be precomputed.

PRESETS (checked on the Hugging Face model cards, November 2026):
- bge-m3     BAAI/bge-reranker-v2-m3                 ~568M params (0.6B), Apache-2.0, built on
             bge-m3 (multilingual, 100+ languages; Hebrew is not singled out on the card, so
             the lab measures it on the Hebrew golden questions), ~2.3 GB download (F32).
             The default. Raw scores are logits (the card shows -5.65 for an irrelevant pair);
             sigmoid maps them to 0..1 without changing the order. Latency on a CPU was NOT
             measured in the course sandbox (no Hugging Face access): rerank_eval.py prints
             yours, per query and per passage.
- mmarco     cross-encoder/mmarco-mMiniLMv2-L12-H384-v1   ~118M params, Apache-2.0, trained on
             MS MARCO machine-translated to 14 languages (Hebrew is NOT one of them, so test it
             on Hebrew before trusting it). ~5x faster than bge-m3.
Any other: CrossEncoderReranker("org/name"). Licences differ: jina-reranker-v2-base-multilingual
is CC-BY-NC (not for commercial use), so read the card before shipping.

The first use downloads the weights into ~/.cache/huggingface (needs internet once; the course
sandbox cannot reach Hugging Face, so tests use a stub model and the lab has a fake reranker).
"""

from __future__ import annotations

import time
from typing import Any, Optional

from .base import BaseReranker

PRESETS: dict[str, dict[str, Any]] = {
    "bge-m3": {"name": "BAAI/bge-reranker-v2-m3", "max_length": 512},
    "mmarco": {"name": "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1", "max_length": 512},
}


class CrossEncoderReranker(BaseReranker):
    def __init__(self, name: str, *, max_length: int = 512, batch_size: int = 16,
                 device: Optional[str] = None, model: Any = None):
        super().__init__()
        self.model_name = name
        self.max_length, self.batch_size, self.device = max_length, batch_size, device
        self._model = model                     # tests inject a stub with .predict(pairs)
        self.name = f"ce:{name.split('/')[-1]}"
        self.load_s = 0.0

    @classmethod
    def preset(cls, key: str, **kw) -> "CrossEncoderReranker":
        if key not in PRESETS:
            raise ValueError(f"unknown preset {key!r}; known: {sorted(PRESETS)}")
        return cls(**{**PRESETS[key], **kw})

    @property
    def model(self):
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder  # type: ignore
            except ImportError as exc:  # pragma: no cover - depends on the environment
                raise ImportError(
                    "local rerankers need sentence-transformers (and PyTorch):\n"
                    "  uv pip install torch --index-url https://download.pytorch.org/whl/cpu\n"
                    "  uv pip install sentence-transformers\n"
                    "or use --reranker fake (offline, lexical, not a model)") from exc
            t0 = time.perf_counter()
            self._model = CrossEncoder(self.model_name, max_length=self.max_length, device=self.device)
            self.load_s = time.perf_counter() - t0
        return self._model

    def score(self, query: str, texts: list[str]) -> list[float]:
        scores = self.model.predict([(query, t) for t in texts], batch_size=self.batch_size,
                                    show_progress_bar=False)
        self.stats.calls = 1
        return [float(s) for s in scores]


__all__ = ["CrossEncoderReranker", "PRESETS"]
