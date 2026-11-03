"""Regression gates: rules a candidate run must pass before it ships, runnable in pytest/CI.

Two kinds of rule, because each catches what the other misses:

Threshold          an absolute floor: "answer_ok on version_conflict >= 0.70". Simple, and it
                   protects the things you promised. It cannot see a drop from 0.95 to 0.75.
NoSignificantDrop  relative to a baseline run on the SAME examples: fail if the paired
                   comparison says the candidate is significantly worse (McNemar exact for
                   0/1 metrics, paired bootstrap otherwise), OR if the observed
                   drop exceeds `max_drop` (a practical limit, for slices too small for any
                   test to reach significance: 11 version-conflict questions cannot).

    gates = [Threshold("answer_ok", 0.55),
             Threshold("answer_ok", 0.70, slice="version_conflict"),
             NoSignificantDrop("answer_ok"),
             NoSignificantDrop("answer_ok", slice="version_conflict", max_drop=0.10)]
    results = check_gates(candidate, dataset, gates, baseline=baseline)
    assert_gates(results)      # raises AssertionError listing every failed rule

A gate result always says WHY: the observed value, the threshold, the CI, the wins/losses.
A red CI job that only says "eval failed" gets disabled within a week.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Union

from .dataset import Dataset
from .runner import Run
from .stats import bootstrap_ci, mcnemar_exact, paired_compare


@dataclass
class GateResult:
    rule: str
    passed: bool
    detail: str
    value: Optional[float] = None
    data: dict = field(default_factory=dict)

    def __str__(self) -> str:
        return f"[{'PASS' if self.passed else 'FAIL'}] {self.rule}: {self.detail}"


def _ids(dataset: Dataset, slice: Optional[str]) -> list[str]:
    if not slice:
        return dataset.ids()
    if ":" in slice:                       # "tag:format:pdf" style
        return dataset.filter(tag=slice.split(":", 1)[1]).ids()
    return dataset.filter(type=slice).ids()


@dataclass
class Threshold:
    metric: str
    min: float
    slice: Optional[str] = None            # a question type, or "tag:<tag>"

    @property
    def name(self) -> str:
        return f"{self.metric}{'[' + self.slice + ']' if self.slice else ''} >= {self.min:.2f}"

    def check(self, run: Run, dataset: Dataset, baseline: Optional[Run] = None) -> GateResult:
        vals = run.values(self.metric, _ids(dataset, self.slice))
        if not vals:
            return GateResult(self.name, False, "no values (metric missing or empty slice)")
        ci = bootstrap_ci(vals)
        ok = ci.estimate >= self.min
        return GateResult(self.name, ok, f"observed {ci.estimate:.3f} (95% CI {ci.low:.3f}-{ci.high:.3f}, n={ci.n})",
                          ci.estimate, {"ci": [ci.low, ci.high], "n": ci.n})


@dataclass
class NoSignificantDrop:
    metric: str
    slice: Optional[str] = None
    max_drop: Optional[float] = None       # also fail when the observed drop is larger than this
    level: float = 0.95
    test: str = "auto"                     # "auto": McNemar exact for 0/1 metrics, else paired bootstrap

    @property
    def name(self) -> str:
        extra = f", max drop {self.max_drop:.2f}" if self.max_drop is not None else ""
        return f"no significant drop in {self.metric}{'[' + self.slice + ']' if self.slice else ''}{extra}"

    def check(self, run: Run, dataset: Dataset, baseline: Optional[Run] = None) -> GateResult:
        if baseline is None:
            return GateResult(self.name, False, "no baseline run given")
        ids = [i for i in _ids(dataset, self.slice)
               if run.by_id().get(i) and baseline.by_id().get(i)
               and run.by_id()[i].scores.get(self.metric) is not None
               and baseline.by_id()[i].scores.get(self.metric) is not None]
        if not ids:
            return GateResult(self.name, False, "no paired values")
        a, b = baseline.values(self.metric, ids), run.values(self.metric, ids)
        pr = paired_compare(a, b, level=self.level)
        binary = all(v in (0.0, 1.0) for v in a + b)
        use_mcnemar = self.test == "mcnemar" or (self.test == "auto" and binary)
        if use_mcnemar:
            # With few discordant pairs the bootstrap is optimistic (it can resample away every
            # flipped question); the exact test is the honest one for pass/fail outcomes.
            p = mcnemar_exact([x >= 1 for x in a], [y >= 1 for y in b])
            sig_drop = p < (1 - self.level) and pr.diff < 0
        else:
            p = pr.p_value
            sig_drop = pr.significant and pr.diff < 0
        too_big = self.max_drop is not None and -pr.diff > self.max_drop + 1e-9
        ok = not sig_drop and not too_big
        why = []
        if sig_drop:
            why.append("significant drop")
        if too_big:
            why.append(f"drop {-pr.diff:.3f} > max {self.max_drop:.2f}")
        detail = (f"baseline {pr.mean_a:.3f} -> candidate {pr.mean_b:.3f}, diff {pr.diff:+.3f} "
                  f"(CI {pr.low:+.3f}..{pr.high:+.3f}, {'McNemar' if use_mcnemar else 'bootstrap'} p={p:.3f}, "
                  f"better on {pr.wins}, worse on {pr.losses}, n={pr.n})" + (f" -> {', '.join(why)}" if why else ""))
        return GateResult(self.name, ok, detail, pr.diff,
                          {"p": p, "test": "mcnemar" if use_mcnemar else "bootstrap", "ci": [pr.low, pr.high], "wins": pr.wins, "losses": pr.losses,
                           "worse_ids": [i for i, x, y in zip(ids, a, b) if y < x]})


Gate = Union[Threshold, NoSignificantDrop]


def check_gates(run: Run, dataset: Dataset, gates: list[Gate], *, baseline: Optional[Run] = None) -> list[GateResult]:
    if run.dataset_ref != dataset.ref and not run.dataset_ref.startswith(dataset.name):
        raise ValueError(f"run was made on {run.dataset_ref}, not {dataset.ref}")
    if baseline is not None and baseline.dataset_ref != run.dataset_ref:
        raise ValueError(f"baseline ({baseline.dataset_ref}) and candidate ({run.dataset_ref}) used different "
                         "datasets; re-run the baseline on the current golden set first")
    return [g.check(run, dataset, baseline) for g in gates]


def assert_gates(results: list[GateResult]) -> None:
    failed = [r for r in results if not r.passed]
    if failed:
        raise AssertionError("regression gate failed:\n" + "\n".join(f"  {r}" for r in failed)
                             + "\npassed:\n" + "\n".join(f"  {r}" for r in results if r.passed))
