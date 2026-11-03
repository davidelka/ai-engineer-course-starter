"""OpenAI embeddings over raw httpx (no SDK), like llmkit's providers.

    emb = OpenAIEmbedder("text-embedding-3-small")              # 1536 dims
    emb = OpenAIEmbedder("text-embedding-3-small", dims=512)    # Matryoshka: API shortens
    vecs = emb.embed_documents(texts); print(emb.tokens, emb.cost_usd)

POST https://api.openai.com/v1/embeddings  {"model", "input": [..], "dimensions"?}
-> {"data": [{"index": i, "embedding": [...]}, ...], "usage": {"prompt_tokens": n}}

Facts checked November 2026 (developers.openai.com model pages and embeddings guide):
- text-embedding-3-small: 1536 dims, $0.02 / 1M tokens. text-embedding-3-large: 3072 dims,
  $0.13 / 1M tokens. Max input 8192 tokens per text.
- `dimensions` shortens the vector (the guide: "remove some numbers from the end"); if you
  shorten manually instead, you must re-normalize. We L2-normalize every result anyway, so
  dot == cosine regardless of what the API returns.
- The models are symmetric: no query/passage prefixes.
The whole Acme corpus (~42K tokens of chunk text with titles) costs about $0.001 with -small.

The key comes from OPENAI_API_KEY (call llmkit.load_dotenv(".env") first). It is sent only in
the Authorization header and never printed.
"""

from __future__ import annotations

import os
import time
from typing import Optional

import httpx
import numpy as np

from .base import BaseEmbedder
from ..vectors.vecmath import l2_normalize

# USD per 1M input tokens, and default dimensions (checked November 2026)
PRICES = {"text-embedding-3-small": 0.02, "text-embedding-3-large": 0.13, "text-embedding-ada-002": 0.10}
DEFAULT_DIMS = {"text-embedding-3-small": 1536, "text-embedding-3-large": 3072, "text-embedding-ada-002": 1536}


class OpenAIEmbedder(BaseEmbedder):
    URL = "https://api.openai.com/v1/embeddings"

    def __init__(self, model: str = "text-embedding-3-small", dims: Optional[int] = None, *,
                 api_key: Optional[str] = None, batch_size: int = 128, timeout: float = 60.0,
                 max_retries: int = 4, transport: Optional[httpx.BaseTransport] = None,
                 base_url: Optional[str] = None):
        self.model = model
        self.dims = dims
        self.dim = dims or DEFAULT_DIMS.get(model, 0)
        self.batch_size = batch_size      # OpenAI allows up to 2048 inputs/request; 128 keeps requests small
        self.max_retries = max_retries
        self.normalized = True
        self.model_id = f"openai:{model}" + (f":{dims}" if dims else "")
        self._api_key = api_key
        self._client = httpx.Client(timeout=timeout, transport=transport)
        self.url = (base_url.rstrip("/") + "/embeddings") if base_url else self.URL
        self.tokens = 0                   # prompt tokens billed so far
        self.requests = 0

    @property
    def cost_usd(self) -> float:
        return self.tokens * PRICES.get(self.model, 0.0) / 1e6

    def _key(self) -> str:
        key = self._api_key or os.environ.get("OPENAI_API_KEY", "")
        if not key:
            raise RuntimeError("OPENAI_API_KEY is not set (put it in .env; llmkit.load_dotenv reads it)")
        return key

    def _embed(self, texts: list[str], kind: str) -> np.ndarray:
        body: dict = {"model": self.model, "input": [t if t.strip() else " " for t in texts],
                      "encoding_format": "float"}
        if self.dims:
            body["dimensions"] = self.dims
        headers = {"Authorization": f"Bearer {self._key()}", "Content-Type": "application/json"}
        for attempt in range(self.max_retries + 1):
            r = self._client.post(self.url, json=body, headers=headers)
            self.requests += 1
            if r.status_code == 200:
                break
            retryable = r.status_code == 429 or r.status_code >= 500
            if not retryable or attempt == self.max_retries:
                msg = r.text[:300]
                raise RuntimeError(f"OpenAI embeddings HTTP {r.status_code}: {msg}")
            wait = float(r.headers.get("retry-after", 0) or 0) or min(2 ** attempt, 20)
            time.sleep(wait)
        data = r.json()
        rows = sorted(data["data"], key=lambda d: d["index"])     # order is by index, not arrival
        self.tokens += int(data.get("usage", {}).get("prompt_tokens", 0))
        return l2_normalize(np.array([d["embedding"] for d in rows], dtype=np.float32))


def estimate_cost(n_tokens: int, model: str = "text-embedding-3-small") -> float:
    return n_tokens * PRICES.get(model, 0.0) / 1e6
