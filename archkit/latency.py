"""Latency budget (lesson 19).

latency_budget(): the conservative way architects compose a budget. Sequential
stages add up; stages in the same parallel group cost only the slowest one.
Adding p95 values is USUALLY pessimistic: it matches the case where every stage
has its bad day on the same request. It is a heuristic, not a bound: quantiles
are not additive, so the p95 of a sum equals the sum of p95s only under perfect
positive dependence, and can EXCEED it with heavy tails (a stage that is fast
96% of the time and very slow 4% of the time). simulate() shows the gap for
independent stages, by sampling each stage from a log-normal distribution
fitted to its p50 and p95. Queue wait is not modeled: it is a stage whose p95
the author types in.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Iterable, Optional

Z95 = 1.6448536269514722  # standard normal quantile at 0.95


@dataclass
class Stage:
    name: str
    p95_ms: float
    p50_ms: Optional[float] = None   # default for simulate(): p95 / 2
    group: Optional[str] = None      # same group = run in parallel


def blocks(stages: Iterable[Stage]) -> list[tuple[str, float]]:
    """Collapse parallel groups: [(name, p95_ms)], in order of first appearance.
    An ungrouped stage is its own block; a group is one block named after the group,
    worth the max p95 of its members."""
    order: list[str] = []
    value: dict[str, float] = {}
    for s in stages:
        key = s.group or s.name
        if key not in value:
            order.append(key)
            value[key] = s.p95_ms
        else:
            value[key] = max(value[key], s.p95_ms)
    return [(k, value[k]) for k in order]


def latency_budget(stages: Iterable[Stage], budget_ms: float) -> dict:
    bl = blocks(stages)
    total = sum(v for _, v in bl)
    largest = max(bl, key=lambda kv: kv[1])[0] if bl else None
    return {
        "blocks": bl,
        "total_p95_ms": total,
        "budget_ms": budget_ms,
        "slack_ms": budget_ms - total,
        "within_budget": total <= budget_ms,
        "largest": largest,
        "shares": {k: (v / total if total else 0.0) for k, v in bl},
    }


def llm_stage_ms(ttft_ms: float, output_tokens: int, tokens_per_s: float) -> float:
    """Time of one non-streamed model call: time to first token + generation time."""
    return ttft_ms + 1000.0 * output_tokens / tokens_per_s


def simulate(stages: Iterable[Stage], n: int = 20000, seed: int = 0) -> dict:
    """Monte Carlo end-to-end latency. Each stage ~ log-normal with the given p50/p95."""
    stages = list(stages)
    rng = random.Random(seed)
    params = []
    for s in stages:
        p50 = s.p50_ms or s.p95_ms / 2
        p50 = min(p50, s.p95_ms)
        sigma = max(1e-9, math.log(s.p95_ms / p50) / Z95)
        params.append((s, math.log(p50), sigma))
    totals = []
    for _ in range(n):
        groups: dict[str, float] = {}
        order: list[str] = []
        for s, mu, sigma in params:
            x = rng.lognormvariate(mu, sigma)
            key = s.group or s.name
            if key not in groups:
                order.append(key)
                groups[key] = x
            else:
                groups[key] = max(groups[key], x)
        totals.append(sum(groups[k] for k in order))
    totals.sort()
    return {
        "p50_ms": totals[int(0.50 * (n - 1))],
        "p95_ms": totals[int(0.95 * (n - 1))],
        "p99_ms": totals[int(0.99 * (n - 1))],
        "sum_of_p95_ms": sum(v for _, v in blocks(stages)),
    }


def stages_from_spec(path_budget) -> list[Stage]:
    return [Stage(s.name, s.p95_ms, s.p50_ms, s.group) for s in path_budget.stages]
