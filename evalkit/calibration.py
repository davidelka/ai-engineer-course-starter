"""Calibrating a judge against human labels.

An LLM judge is itself a classifier, and its verdicts are only worth something once you know
how often it agrees with a careful human. Three numbers:

agreement      share of items where judge == human. Misleading when one label dominates:
               if 80% of answers are good, a judge that always says "good" agrees 80%.
cohen_kappa    agreement corrected for chance: (p_o - p_e) / (1 - p_e), where p_e is the
               agreement two raters with these label frequencies would reach by luck.
               1 = perfect, 0 = no better than chance, < 0 = worse than chance.
               Rough reading often quoted (Landis & Koch): 0.41-0.60 moderate,
               0.61-0.80 substantial, above 0.80 almost perfect.
confusion      counts of (human, judge) pairs. For a pass/fail judge the two error cells
               matter differently: a judge that passes bad answers (false pass) hides
               regressions; a judge that fails good answers (false fail) wastes your time.

    rep = calibrate(human_labels, judge_labels, positive="grounded")
    rep.kappa, rep.confusion[("not_grounded", "grounded")]   # false passes
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Hashable, Optional, Sequence


def agreement(human: Sequence[Hashable], judge: Sequence[Hashable]) -> float:
    if len(human) != len(judge) or not human:
        raise ValueError("need two label lists of the same, non-zero length")
    return sum(h == j for h, j in zip(human, judge)) / len(human)


def cohen_kappa(human: Sequence[Hashable], judge: Sequence[Hashable]) -> float:
    """kappa = (p_o - p_e) / (1 - p_e); p_e = sum over labels of P_human(l) * P_judge(l).
    When p_e == 1 (both raters always use the same single label) kappa is defined as 1.0
    if they agree everywhere, else 0.0."""
    p_o = agreement(human, judge)
    n = len(human)
    ch, cj = Counter(human), Counter(judge)
    p_e = sum((ch[l] / n) * (cj[l] / n) for l in set(ch) | set(cj))
    if p_e >= 1.0:
        return 1.0 if p_o == 1.0 else 0.0
    return (p_o - p_e) / (1 - p_e)


def confusion(human: Sequence[Hashable], judge: Sequence[Hashable]) -> dict[tuple, int]:
    """{(human_label, judge_label): count} over every pair of labels that occurs."""
    labels = sorted(set(human) | set(judge), key=str)
    c = Counter(zip(human, judge))
    return {(h, j): c.get((h, j), 0) for h in labels for j in labels}


@dataclass
class CalibrationReport:
    n: int
    agreement: float
    kappa: float
    confusion: dict[tuple, int]
    positive: Optional[str] = None
    precision: Optional[float] = None     # of the judge's "positive" verdicts, how many humans agree
    recall: Optional[float] = None        # of the human positives, how many the judge found
    false_pass: int = 0                   # human negative, judge positive
    false_fail: int = 0                   # human positive, judge negative
    disagreements: list[int] = field(default_factory=list)   # indexes, for error analysis

    def summary(self) -> str:
        s = f"n={self.n} agreement={self.agreement:.1%} kappa={self.kappa:.2f}"
        if self.positive is not None:
            s += f" false_pass={self.false_pass} false_fail={self.false_fail}"
        return s


def calibrate(human: Sequence[Hashable], judge: Sequence[Hashable], *, positive: Optional[str] = None) -> CalibrationReport:
    rep = CalibrationReport(len(human), agreement(human, judge), cohen_kappa(human, judge), confusion(human, judge),
                            positive, disagreements=[i for i, (h, j) in enumerate(zip(human, judge)) if h != j])
    if positive is not None:
        tp = sum(1 for h, j in zip(human, judge) if h == positive and j == positive)
        jp = sum(1 for j in judge if j == positive)
        hp = sum(1 for h in human if h == positive)
        rep.precision = tp / jp if jp else None
        rep.recall = tp / hp if hp else None
        rep.false_pass = sum(1 for h, j in zip(human, judge) if h != positive and j == positive)
        rep.false_fail = sum(1 for h, j in zip(human, judge) if h == positive and j != positive)
    return rep


def kappa_band(k: float) -> str:
    """The Landis & Koch descriptive bands (a convention, not a law)."""
    if k < 0:
        return "worse than chance"
    for limit, name in ((0.2, "slight"), (0.4, "fair"), (0.6, "moderate"), (0.8, "substantial")):
        if k <= limit:
            return name
    return "almost perfect"
