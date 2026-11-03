"""Exercise 2: recall_at_k and pareto_frontier in mine.py."""

import random

import numpy as np
import pytest

import mine
from ragkit.vectors.bench import pareto_frontier as ref_frontier
from ragkit.vectors.bench import recall_ids as ref_recall


def test_recall_examples():
    assert mine.recall_at_k([1, 2, 9], [1, 2, 3], 3) == pytest.approx(2 / 3)
    assert mine.recall_at_k([3, 2, 1], [1, 2, 3], 3) == 1.0
    assert mine.recall_at_k([1, 2], [1, 2, 3, 4], 4) == 0.5


def test_recall_only_first_k_count():
    assert mine.recall_at_k([9, 8, 1], [1, 2], 2) == 0.0      # 1 is found, but at position 3
    assert mine.recall_at_k([1, 9], [1, 2, 3, 4, 5], 2) == 0.5


def test_recall_empty_truth_and_string_ids():
    assert mine.recall_at_k([], [], 10) == 1.0
    assert mine.recall_at_k(["a#1", "b#0"], ["b#0", "c#2"], 2) == 0.5


def test_recall_matches_reference_on_random_lists():
    rng = random.Random(1)
    for _ in range(200):
        truth = rng.sample(range(50), rng.randint(0, 15))
        found = rng.sample(range(50), rng.randint(0, 15))
        k = rng.randint(1, 12)
        assert mine.recall_at_k(found, truth, k) == pytest.approx(ref_recall(found, truth, k))


def test_frontier_docstring_example():
    pts = [(1.0, 0.80), (2.0, 0.95), (1.5, 0.70), (3.0, 0.95), (4.0, 0.99)]
    assert mine.pareto_frontier(pts) == [0, 1, 4]


def test_frontier_sorted_by_latency_not_input_order():
    pts = [(4.0, 0.99), (1.0, 0.80), (2.0, 0.95)]
    assert mine.pareto_frontier(pts) == [1, 2, 0]


def test_frontier_ties():
    # same latency: only the better recall survives; exact duplicates: first index only
    assert mine.pareto_frontier([(1.0, 0.9), (1.0, 0.8)]) == [0]
    assert mine.pareto_frontier([(1.0, 0.9), (1.0, 0.9), (0.5, 0.5)]) == [2, 0]
    assert mine.pareto_frontier([]) == []


def test_frontier_matches_reference_on_random_sweeps():
    rng = np.random.default_rng(7)
    for _ in range(100):
        n = int(rng.integers(1, 30))
        pts = [(float(round(rng.uniform(0.1, 5), 1)), float(round(rng.uniform(0.5, 1), 2))) for _ in range(n)]
        assert mine.pareto_frontier(pts) == ref_frontier(pts)


def test_frontier_on_a_realistic_ef_sweep():
    # recall@10 / latency measured for HNSW ef_search = 8, 16, 32, 64, 128, 256 (+ an IVF run)
    pts = [(0.05, 0.71), (0.07, 0.86), (0.11, 0.95), (0.19, 0.985), (0.35, 0.997), (0.66, 0.999),
           (0.40, 0.90)]
    front = mine.pareto_frontier(pts)
    assert 6 not in front, "the IVF point is slower than ef=32 and has lower recall"
    assert front == [0, 1, 2, 3, 4, 5]
