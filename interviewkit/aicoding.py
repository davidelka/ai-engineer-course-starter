"""Typical "AI coding round" tasks (lesson 28, reference for exercise 6).

Both are asked in real AI-engineer loops because they look trivial and hide
edge cases: zero vectors, ties and k > n for top-k; the system prompt, the
newest turn and conversation shape for context truncation.
"""

from __future__ import annotations

import math
from typing import Callable

import numpy as np

MESSAGE_OVERHEAD = 4  # tokens of role/formatting per message, a common rough figure


def approx_tokens(text: str) -> int:
    """About 4 characters per token for English. Hebrew is worse: see lesson 1."""
    return max(1, math.ceil(len(text) / 4))


def top_k_cosine(query: np.ndarray, matrix: np.ndarray, k: int) -> list[tuple[int, float]]:
    query = np.asarray(query, dtype=float)
    matrix = np.asarray(matrix, dtype=float)
    if query.ndim != 1 or matrix.ndim != 2 or matrix.shape[1] != query.shape[0]:
        raise ValueError(f"shape mismatch: query {query.shape}, matrix {matrix.shape}")
    if k <= 0 or matrix.shape[0] == 0:
        return []
    qn = np.linalg.norm(query)
    rn = np.linalg.norm(matrix, axis=1)
    denom = rn * qn
    sims = np.zeros(matrix.shape[0])
    ok = denom > 0
    sims[ok] = (matrix[ok] @ query) / denom[ok]
    order = np.argsort(-sims, kind="stable")[:k]
    return [(int(i), float(sims[i])) for i in order]


def fit_to_budget(messages: list[dict], budget: int,
                  count: Callable[[str], int] = approx_tokens) -> list[dict]:
    cost = lambda m: count(m["content"]) + MESSAGE_OVERHEAD  # noqa: E731
    systems = [m for m in messages if m["role"] == "system"]
    rest = [m for m in messages if m["role"] != "system"]
    if not rest:
        raise ValueError("no conversation messages")
    used = sum(cost(m) for m in systems) + cost(rest[-1])
    if used > budget:
        raise ValueError(f"system prompt + last message need {used} tokens, budget is {budget}")
    kept = [rest[-1]]
    for m in reversed(rest[:-1]):
        c = cost(m)
        if used + c > budget:
            break
        kept.append(m)
        used += c
    kept.reverse()
    if len(kept) > 1 and kept[0]["role"] == "assistant":
        kept = kept[1:]
    return [dict(m) for m in systems] + [dict(m) for m in kept]
