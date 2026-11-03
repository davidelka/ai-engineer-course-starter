"""Cohere Rerank over raw httpx (no SDK), like llmkit and the OpenAI embedder.

    rr = CohereReranker("rerank-v4.0-fast")         # COHERE_API_KEY from the environment / .env
    hits = rr.rerank(question, candidates, top_n=5)

POST https://api.cohere.com/v2/rerank   {"model", "query", "documents": [str], "top_n"}
-> {"results": [{"index", "relevance_score"}], "meta": {"billed_units": {...}}}
`index` points into the documents you sent; scores are 0..1 and only comparable within one
request. Retries on 429 and 5xx with backoff.

Models (docs.cohere.com/docs/rerank, checked November 2026): rerank-v5.0-pro / -fast (32k
context, launched October 2026), rerank-v4.0-pro / -fast (32k, multilingual), rerank-v3.5 (4k,
multilingual). Hebrew is not named in the language lists, so measure it on the Hebrew golden
questions before relying on it.

Pricing changed in October 2026: older models were billed per "search" (one query with up to
100 documents; Rerank 4 Fast $2.00 / Pro $2.50 per 1,000 searches), Rerank 5 per token
($0.02 / $0.05 per 1M tokens according to a pricing tracker; the API example now reports
billed_units.input_tokens). PRICES below follows that and is marked unverified: check
cohere.com/pricing before you rely on a number. A free trial key exists, with rate limits.
"""

from __future__ import annotations

import os
import time
from typing import Optional

import httpx

from .base import BaseReranker

URL = "https://api.cohere.com/v2/rerank"

# per_search: USD per search unit; per_mtok: USD per 1M billed input tokens. UNVERIFIED.
PRICES: dict[str, dict[str, float]] = {
    "rerank-v5.0-fast": {"per_mtok": 0.02},
    "rerank-v5.0-pro": {"per_mtok": 0.05},
    "rerank-v4.0-fast": {"per_search": 0.002},
    "rerank-v4.0-pro": {"per_search": 0.0025},
    "rerank-v3.5": {"per_search": 0.002},
}


class CohereReranker(BaseReranker):
    def __init__(self, model: str = "rerank-v4.0-fast", *, api_key: Optional[str] = None,
                 http: Optional[httpx.Client] = None, max_tokens_per_doc: int = 1024,
                 retries: int = 3, url: str = URL):
        super().__init__()
        self.model = model
        self.api_key = api_key or os.environ.get("COHERE_API_KEY", "")
        self.http = http or httpx.Client(timeout=httpx.Timeout(connect=5.0, read=30.0, write=30.0, pool=5.0))
        self.max_tokens_per_doc, self.retries, self.url = max_tokens_per_doc, retries, url
        self.name = f"cohere:{model}"

    def _cost(self, meta: dict, n_docs: int) -> float:
        p = PRICES.get(self.model, {})
        billed = (meta or {}).get("billed_units") or {}
        if "per_mtok" in p:
            return float(billed.get("input_tokens", 0)) * p["per_mtok"] / 1e6
        if "per_search" in p:
            units = billed.get("search_units") or max(1, -(-n_docs // 100))
            return float(units) * p["per_search"]
        return 0.0

    def score(self, query: str, texts: list[str]) -> list[float]:
        if not self.api_key:
            raise RuntimeError("COHERE_API_KEY is not set (add it to .env), or use another reranker")
        body = {"model": self.model, "query": query, "documents": texts,
                "max_tokens_per_doc": self.max_tokens_per_doc}
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json",
                   "X-Client-Name": "ai-engineer-course"}
        for attempt in range(self.retries + 1):
            r = self.http.post(self.url, json=body, headers=headers)
            if r.status_code == 200:
                break
            if r.status_code in (429, 500, 502, 503, 504) and attempt < self.retries:
                time.sleep(min(8.0, float(r.headers.get("retry-after") or 2 ** attempt)))
                continue
            raise RuntimeError(f"cohere rerank HTTP {r.status_code}: {r.text[:300]}")
        data = r.json()
        scores = [float("-inf")] * len(texts)
        for item in data.get("results", []):
            scores[int(item["index"])] = float(item["relevance_score"])
        meta = data.get("meta") or {}
        self.stats.calls = 1
        self.stats.cost_usd = self._cost(meta, len(texts))
        self.stats.estimated = True                    # prices above are unverified
        self.stats.extra = {"billed_units": meta.get("billed_units")}
        return scores


__all__ = ["CohereReranker", "PRICES", "URL"]
