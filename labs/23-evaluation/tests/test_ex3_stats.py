"""Exercise 3: bootstrap_ci and paired_compare in mine.py."""

import random

import pytest

import mine
from evalkit import stats as ref


def test_bootstrap_matches_reference():
    vals = [1.0] * 38 + [0.0] * 41
    m, lo, hi = mine.bootstrap_ci(vals)
    r = ref.bootstrap_ci(vals)
    assert m == pytest.approx(r.estimate)
    assert lo == pytest.approx(r.low)
    assert hi == pytest.approx(r.high)


def test_bootstrap_properties():
    rng = random.Random(3)
    vals = [rng.random() for _ in range(60)]
    m, lo, hi = mine.bootstrap_ci(vals, n_resamples=1000, seed=7)
    assert lo <= m <= hi
    m2, lo2, hi2 = mine.bootstrap_ci(vals, n_resamples=1000, level=0.8, seed=7)
    assert hi2 - lo2 < hi - lo           # a lower confidence level gives a narrower interval
    assert mine.bootstrap_ci([0.5] * 10)[1:] == (0.5, 0.5)
    with pytest.raises(ValueError):
        mine.bootstrap_ci([])


def test_bootstrap_more_data_narrower():
    small = [1.0, 0.0] * 10
    big = [1.0, 0.0] * 200
    _, l1, h1 = mine.bootstrap_ci(small)
    _, l2, h2 = mine.bootstrap_ci(big)
    assert (h2 - l2) < (h1 - l1) / 3      # about sqrt(20) = 4.5 times narrower


def test_paired_matches_reference():
    rng = random.Random(1)
    a = [float(rng.random() < 0.55) for _ in range(79)]
    b = [x if rng.random() < 0.85 else 1.0 - x for x in a]
    got = mine.paired_compare(a, b)
    r = ref.paired_compare(a, b)
    assert got["diff"] == pytest.approx(r.diff)
    assert got["low"] == pytest.approx(r.low)
    assert got["high"] == pytest.approx(r.high)
    assert got["p_value"] == pytest.approx(r.p_value)
    assert (got["wins"], got["losses"], got["ties"]) == (r.wins, r.losses, r.ties)


def test_paired_detects_consistent_improvement():
    a = [0.0] * 20 + [1.0] * 59
    b = [1.0] * 20 + [1.0] * 59           # B fixes 20 questions, breaks none
    got = mine.paired_compare(a, b)
    assert got["low"] > 0 and got["p_value"] < 0.01 and got["wins"] == 20 and got["losses"] == 0


def test_paired_no_difference():
    a = [1.0, 0.0] * 30
    got = mine.paired_compare(a, list(a))
    assert got["diff"] == 0 and got["low"] == 0 and got["high"] == 0 and got["p_value"] == 1.0 and got["ties"] == 60


def test_paired_errors():
    with pytest.raises(ValueError):
        mine.paired_compare([1.0], [1.0, 0.0])
    with pytest.raises(ValueError):
        mine.paired_compare([], [])
