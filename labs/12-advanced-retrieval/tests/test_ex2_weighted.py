"""Exercise 2: min-max normalization and weighted score fusion in mine.py."""

import random

import pytest

import mine
from ragkit import fusion as ref


def test_minmax_basic():
    assert mine.minmax_normalize({"a": 12.0, "b": 7.0, "c": 2.0}) == pytest.approx({"a": 1.0, "b": 0.5, "c": 0.0})


def test_minmax_equal_and_single_and_empty():
    assert mine.minmax_normalize({"a": 3.0, "b": 3.0}) == {"a": 1.0, "b": 1.0}
    assert mine.minmax_normalize({"only": 0.42}) == {"only": 1.0}
    assert mine.minmax_normalize({}) == {}


def test_minmax_does_not_modify_input():
    s = {"a": 2.0, "b": 4.0}
    mine.minmax_normalize(s)
    assert s == {"a": 2.0, "b": 4.0}


def test_worked_example_and_the_missing_pitfall():
    out = mine.weighted_fusion([{"a": 10, "b": 5, "c": 0}, {"b": 0.9, "c": 0.8}], [0.5, 0.5])
    assert [d for d, _ in out] == ["b", "a", "c"]
    assert dict(out) == pytest.approx({"b": 0.75, "a": 0.5, "c": 0.0})


def test_scales_do_not_matter_after_normalization():
    # BM25 in the tens, cosine in 0.7-0.9: multiply a list by 1000 and nothing changes
    bm25 = {"a": 14.2, "b": 9.1, "c": 3.3}
    cos = {"a": 0.81, "c": 0.86, "d": 0.79}
    out1 = mine.weighted_fusion([bm25, cos], [0.4, 0.6])
    out2 = mine.weighted_fusion([{k: v * 1000 for k, v in bm25.items()}, cos], [0.4, 0.6])
    assert [d for d, _ in out1] == [d for d, _ in out2]


def test_one_outlier_squashes_the_rest():
    # one huge BM25 score: every other BM25 score lands near 0 after min-max
    norm = mine.minmax_normalize({"a": 100.0, "b": 6.0, "c": 5.0, "d": 4.0})
    assert norm["b"] < 0.03


def test_missing_value_parameter():
    out = dict(mine.weighted_fusion([{"a": 1.0, "b": 0.0}, {"b": 1.0}], missing=0.5))
    assert out["a"] == pytest.approx(1.5)
    assert out["b"] == pytest.approx(1.0)


def test_ties_and_errors():
    out = mine.weighted_fusion([{"y": 1.0}, {"x": 1.0}])
    assert [d for d, _ in out] == ["x", "y"]          # same score, both rank 1: str order
    with pytest.raises(ValueError):
        mine.weighted_fusion([{"a": 1.0}], weights=[1.0, 2.0])
    assert mine.weighted_fusion([]) == []


def test_matches_reference_on_random_scores():
    rnd = random.Random(7)
    for _ in range(200):
        pool = [f"d{i}" for i in range(rnd.randint(1, 25))]
        lists = [{d: round(rnd.uniform(0, rnd.choice([1, 30])), 3) for d in rnd.sample(pool, rnd.randint(0, len(pool)))}
                 for _ in range(rnd.randint(1, 3))]
        w = [rnd.choice([0.2, 0.5, 1.0]) for _ in lists]
        m, r = mine.weighted_fusion(lists, w), ref.weighted_fusion(lists, w)
        assert [d for d, _ in m] == [d for d, _ in r]
        assert [s for _, s in m] == pytest.approx([s for _, s in r])


def test_matches_reference_on_acme(bm25, dense, qa):
    for q in qa[:40]:
        a = {h.chunk.id: h.score for h in bm25.search(q["question"], k=30)}
        b = {h.chunk.id: h.score for h in dense.search(q["question"], k=30)}
        m = mine.weighted_fusion([a, b], [0.5, 0.5])
        r = ref.weighted_fusion([a, b], [0.5, 0.5])
        assert [d for d, _ in m] == [d for d, _ in r], q["id"]
