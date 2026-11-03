"""Is this difference real? Statistics for small eval sets, standard library only.

The core problem: an eval set of 79 questions is a SAMPLE. Run the same system on a different
79 questions of the same kind and the score moves. A 3-point "improvement" can be noise.

bootstrap_ci        confidence interval of a mean by resampling the examples with replacement
paired_compare      two system versions on the SAME examples: bootstrap the per-example
                    differences. Pairing removes the "some questions are just hard" variance,
                    so it detects much smaller differences than comparing two separate CIs.
mcnemar_exact       the exact test for paired pass/fail outcomes: only the discordant
                    examples (one version passes, the other fails) carry information
min_detectable_diff the smallest true difference a set of n examples can reliably detect
sample_size         how many examples you need to detect a given difference

All resampling uses a seeded random.Random, so a report is reproducible.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from statistics import NormalDist
from typing import Callable, Optional, Sequence

_Z = NormalDist()


def mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else float("nan")


def percentile(sorted_xs: Sequence[float], q: float) -> float:
    """Linear interpolation between closest ranks (numpy's default), q in [0, 1]."""
    if not sorted_xs:
        return float("nan")
    pos = q * (len(sorted_xs) - 1)
    lo, hi = math.floor(pos), math.ceil(pos)
    return sorted_xs[lo] + (sorted_xs[hi] - sorted_xs[lo]) * (pos - lo)


@dataclass
class CI:
    estimate: float
    low: float
    high: float
    n: int
    level: float = 0.95

    def __str__(self) -> str:
        return f"{self.estimate:.3f} [{self.low:.3f}, {self.high:.3f}] (n={self.n}, {self.level:.0%} CI)"

    @property
    def width(self) -> float:
        return self.high - self.low


def bootstrap_ci(values: Sequence[float], *, n_resamples: int = 2000, level: float = 0.95, seed: int = 0,
                 stat: Callable[[Sequence[float]], float] = mean) -> CI:
    """Percentile bootstrap: draw len(values) items with replacement, n_resamples times,
    compute `stat` each time, and take the (1-level)/2 and 1-(1-level)/2 percentiles."""
    xs = list(values)
    if not xs:
        raise ValueError("bootstrap_ci needs at least one value")
    rng = random.Random(seed)
    n = len(xs)
    boots = sorted(stat([xs[rng.randrange(n)] for _ in range(n)]) for _ in range(n_resamples))
    a = (1 - level) / 2
    return CI(stat(xs), percentile(boots, a), percentile(boots, 1 - a), n, level)


@dataclass
class PairedResult:
    mean_a: float
    mean_b: float
    diff: float                 # mean(b - a): positive = B is better
    low: float
    high: float
    p_value: float              # two-sided bootstrap p-value for "no difference"
    n: int
    wins: int                   # examples where b > a
    losses: int                 # examples where b < a
    ties: int
    level: float = 0.95

    @property
    def significant(self) -> bool:
        """The CI of the difference excludes 0."""
        return self.low > 0 or self.high < 0

    def verdict(self) -> str:
        if not self.significant:
            return "no significant difference"
        return "B is better" if self.diff > 0 else "B is worse"

    def __str__(self) -> str:
        return (f"A={self.mean_a:.3f} B={self.mean_b:.3f} diff={self.diff:+.3f} "
                f"[{self.low:+.3f}, {self.high:+.3f}] p={self.p_value:.3f} "
                f"(+{self.wins} -{self.losses} ={self.ties}, n={self.n}): {self.verdict()}")


def paired_compare(a: Sequence[float], b: Sequence[float], *, n_resamples: int = 2000, level: float = 0.95,
                   seed: int = 0) -> PairedResult:
    """Paired bootstrap over per-example differences d_i = b_i - a_i (same examples, same
    order). The CI is the percentile interval of the resampled mean difference. The p-value
    is 2 * min(share of resampled means <= 0, share >= 0), capped at 1."""
    if len(a) != len(b):
        raise ValueError(f"paired_compare needs the same examples in both runs ({len(a)} != {len(b)})")
    if not a:
        raise ValueError("paired_compare needs at least one pair")
    d = [y - x for x, y in zip(a, b)]
    rng = random.Random(seed)
    n = len(d)
    boots = sorted(mean([d[rng.randrange(n)] for _ in range(n)]) for _ in range(n_resamples))
    alpha = (1 - level) / 2
    le = sum(1 for v in boots if v <= 0) / n_resamples
    ge = sum(1 for v in boots if v >= 0) / n_resamples
    p = min(1.0, 2 * min(le, ge))
    return PairedResult(mean(a), mean(b), mean(d), percentile(boots, alpha), percentile(boots, 1 - alpha), p, n,
                        sum(1 for v in d if v > 0), sum(1 for v in d if v < 0), sum(1 for v in d if v == 0), level)


def mcnemar_exact(a: Sequence[bool], b: Sequence[bool]) -> float:
    """Two-sided exact McNemar p-value for paired pass/fail results. With n01 = A passes and B
    fails, n10 = the reverse: under "no difference" each discordant pair is a fair coin, so
    p = P(Binomial(n01+n10, 0.5) <= min(n01, n10)) * 2, capped at 1."""
    n01 = sum(1 for x, y in zip(a, b) if x and not y)
    n10 = sum(1 for x, y in zip(a, b) if y and not x)
    n = n01 + n10
    if n == 0:
        return 1.0
    k = min(n01, n10)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def min_detectable_diff(n: int, p: float = 0.7, *, alpha: float = 0.05, power: float = 0.8,
                        paired: bool = False, discordant: Optional[float] = None) -> float:
    """Smallest true difference in a pass rate that n examples detect with the given power.

    Unpaired (two independent sets of n): MDD = (z_{1-a/2} + z_{power}) * sqrt(2 p (1-p) / n).
    Paired (same n examples, McNemar normal approximation): the variance of the per-example
    difference is about `discordant` (the share of examples whose outcome flips between
    versions, default 2 p (1-p) * 0.5), so MDD = (z_{1-a/2} + z_{power}) * sqrt(discordant / n)."""
    if n <= 0:
        raise ValueError("n must be positive")
    z = _Z.inv_cdf(1 - alpha / 2) + _Z.inv_cdf(power)
    if paired:
        disc = discordant if discordant is not None else p * (1 - p)
        return z * math.sqrt(disc / n)
    return z * math.sqrt(2 * p * (1 - p) / n)


def sample_size(diff: float, p: float = 0.7, *, alpha: float = 0.05, power: float = 0.8,
                paired: bool = False, discordant: Optional[float] = None) -> int:
    """Examples needed to detect `diff` (the inverse of min_detectable_diff), rounded up."""
    if diff <= 0:
        raise ValueError("diff must be positive")
    z = _Z.inv_cdf(1 - alpha / 2) + _Z.inv_cdf(power)
    if paired:
        disc = discordant if discordant is not None else p * (1 - p)
        return math.ceil(disc * (z / diff) ** 2)
    return math.ceil(2 * p * (1 - p) * (z / diff) ** 2)


def wilson_ci(passed: int, n: int, level: float = 0.95) -> CI:
    """Closed-form CI for a pass rate; better than the normal approximation at small n or
    near 0%/100%. Handy for a quick check without resampling."""
    if n == 0:
        return CI(float("nan"), 0.0, 1.0, 0, level)
    z = _Z.inv_cdf(1 - (1 - level) / 2)
    ph = passed / n
    denom = 1 + z * z / n
    centre = (ph + z * z / (2 * n)) / denom
    half = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / denom
    return CI(ph, max(0.0, centre - half), min(1.0, centre + half), n, level)
