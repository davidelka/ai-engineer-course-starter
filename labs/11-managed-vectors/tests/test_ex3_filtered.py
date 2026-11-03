"""Exercise 3: exact_filtered_top_k and filtered_recall in mine.py."""

import numpy as np
import pytest

import mine
from ragkit.vectors.bench import exact_filtered_top_k as ref_exact
from ragkit.vectors.bench import post_filter


def test_docstring_example():
    m = np.array([[1, 0], [0, 1], [0.9, 0.1], [-1, 0]], dtype=float)
    out = mine.exact_filtered_top_k([1, 0], m, [False, True, True, True], 2)
    assert list(out) == [2, 1]
    assert np.issubdtype(np.asarray(out).dtype, np.integer)


def test_indices_refer_to_the_full_matrix():
    m = np.eye(6)
    mask = [False, False, False, False, True, True]
    out = mine.exact_filtered_top_k(m[5], m, mask, 3)
    assert list(out) == [5, 4], "fewer rows pass than k: return all of them, as full-matrix indices"


def test_cosine_not_dot():
    m = np.array([[10, 10], [1, 0]], dtype=float)       # row 0 long but 45 degrees off
    assert list(mine.exact_filtered_top_k([1, 0], m, [True, True], 1)) == [1]


def test_ties_lower_index_first_and_empty():
    m = np.array([[1, 0], [0, 1], [1, 0], [2, 0]], dtype=float)
    assert list(mine.exact_filtered_top_k([1, 0], m, [True, True, True, True], 3)) == [0, 2, 3]
    assert len(mine.exact_filtered_top_k([1, 0], m, [False] * 4, 3)) == 0


def test_matches_reference_on_random_data():
    rng = np.random.default_rng(3)
    m = rng.normal(size=(3000, 64))
    for sel in (0.5, 0.05, 0.002):
        mask = rng.random(3000) < sel
        for _ in range(5):
            q = rng.normal(size=64)
            assert list(mine.exact_filtered_top_k(q, m, mask, 10)) == list(ref_exact(q, m, mask, 10))


def test_filtered_recall_examples():
    assert mine.filtered_recall([5, 7], [5, 7, 9], 10) == pytest.approx(2 / 3)
    assert mine.filtered_recall([5, 7, 9], [9, 5, 7], 10) == 1.0
    assert mine.filtered_recall([], [], 10) == 1.0
    assert mine.filtered_recall([1, 2, 3, 4], [1, 2, 3, 4, 5, 6], 2) == 1.0   # only top k count
    assert mine.filtered_recall([3, 1], [1, 2, 3], 2) == 0.5


def test_post_filtering_pitfall_is_visible_in_your_recall():
    """1,000 rows, 1% pass the filter. Post-filtering the ANN top-50 keeps almost nothing."""
    rng = np.random.default_rng(0)
    m = rng.normal(size=(1000, 32))
    mask = np.zeros(1000, dtype=bool)
    mask[rng.choice(1000, 10, replace=False)] = True
    q = rng.normal(size=32)
    exact = mine.exact_filtered_top_k(q, m, mask, 10)
    assert len(exact) == 10
    unfiltered = list(ref_exact(q, m, np.ones(1000, dtype=bool), 50))   # a perfect ANN, top 50
    post = post_filter(unfiltered, mask, 10)
    assert len(post) < 10
    assert mine.filtered_recall(post, exact, 10) == pytest.approx(len(post) / 10)
    assert mine.filtered_recall(list(exact), exact, 10) == 1.0          # pre-filtering is exact
