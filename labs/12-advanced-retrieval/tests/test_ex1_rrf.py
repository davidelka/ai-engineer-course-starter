"""Exercise 1: Reciprocal Rank Fusion in mine.py."""

import random

import pytest

import mine
from ragkit import fusion as ref


def ids(result):
    return [d for d, _ in result]


def test_worked_example():
    out = mine.rrf([["a", "b", "c"], ["c", "a"]], k=60)
    assert ids(out) == ["a", "c", "b"]
    s = dict(out)
    assert s["a"] == pytest.approx(1 / 61 + 1 / 62)
    assert s["c"] == pytest.approx(1 / 63 + 1 / 61)
    assert s["b"] == pytest.approx(1 / 62)


def test_missing_item_contributes_nothing():
    # "z" is only in the second list: it gets exactly one term, no penalty from the first
    out = dict(mine.rrf([["a", "b"], ["z"]], k=60))
    assert out["z"] == pytest.approx(1 / 61)
    assert out["a"] == pytest.approx(1 / 61)
    assert set(out) == {"a", "b", "z"}


def test_found_by_both_beats_first_in_one():
    # the point of RRF with k=60: 3rd + 3rd beats 1st in a single list
    out = mine.rrf([["a", "x", "both"], ["b", "y", "both"]], k=60)
    assert ids(out)[0] == "both"


def test_exact_tie_broken_by_best_rank_then_id():
    out = mine.rrf([["x", "y"], ["y", "x"]])
    assert ids(out) == ["x", "y"]                     # same score, both best rank 1: str order
    assert out[0][1] == out[1][1]
    # same score, different best rank: "m" was 1st somewhere, "n" never was
    #   m: ranks 1 and 3 -> 1/(k+1) + 1/(k+3);   n: ranks 2 and 2 -> 2/(k+2)
    #   with k=0 these are 1.333 vs 1.0 (no tie), so use weights to make an exact tie:
    #   m: 1/1 (w=1) ; n: 2 * (0.5 / 1) = 1.0 with n first in two half-weight lists
    out = mine.rrf([["m", "z"], ["n"], ["n"]], k=0, weights=[1.0, 0.5, 0.5])
    s = dict(out)
    assert s["m"] == s["n"] == pytest.approx(1.0)
    assert ids(out)[:2] == ["m", "n"]                 # both best rank 1 -> str order
    out = mine.rrf([["z", "b"], ["a", "q"], ["c", "b"]], k=0, weights=[1.0, 0.5, 1.0])
    # a: 0.5/1 = 0.5 (best rank 1);  b: 1/2 + 1/2 = 1.0;  z: 1.0 (best rank 1)
    # z and c tie with b at 1.0: z and c reached rank 1, b only rank 2 -> b after both
    assert ids(out)[:3] == ["c", "z", "b"]


def test_tie_order_independent_of_list_order():
    lists = [["a", "b", "c", "d"], ["d", "c", "b", "a"], ["b", "d", "a", "c"]]
    first = mine.rrf(lists)
    for perm in ([lists[2], lists[0], lists[1]], [lists[1], lists[2], lists[0]]):
        assert mine.rrf(perm) == first


def test_duplicates_in_one_list_count_once():
    out = dict(mine.rrf([["a", "b", "a"]], k=60))
    assert out["a"] == pytest.approx(1 / 61)
    assert out["b"] == pytest.approx(1 / 62)


def test_k_changes_the_shape():
    lists = [["a", "x1", "x2", "x3", "both"], ["b", "y1", "y2", "y3", "both"]]
    assert ids(mine.rrf(lists, k=60))[0] == "both"     # flat: agreement wins
    assert ids(mine.rrf(lists, k=0))[0] in ("a", "b")  # steep: 1/1 beats 1/5 + 1/5


def test_weights():
    out = mine.rrf([["a"], ["b"]], weights=[1.0, 2.0])
    assert ids(out) == ["b", "a"]
    assert dict(out)["b"] == pytest.approx(2 / 61)


def test_errors_and_empty():
    with pytest.raises(ValueError):
        mine.rrf([["a"], ["b"]], weights=[1.0])
    with pytest.raises(ValueError):
        mine.rrf([["a"]], k=-1)
    assert mine.rrf([]) == []
    assert mine.rrf([[], []]) == []


def test_matches_reference_on_random_rankings():
    rnd = random.Random(12)
    for _ in range(200):
        pool = [f"d{i}" for i in range(rnd.randint(1, 30))]
        lists = [rnd.sample(pool, rnd.randint(0, len(pool))) for _ in range(rnd.randint(1, 4))]
        k = rnd.choice([0, 1, 10, 60])
        mine_out, ref_out = mine.rrf(lists, k=k), ref.rrf(lists, k=k)
        assert ids(mine_out) == ids(ref_out)
        assert [s for _, s in mine_out] == pytest.approx([s for _, s in ref_out])


def test_matches_reference_on_acme(bm25, dense, qa):
    """BM25 and (fake) dense chunk rankings for every golden question, fused both ways."""
    for q in qa[:40]:
        a = [h.chunk.id for h in bm25.search(q["question"], k=30)]
        b = [h.chunk.id for h in dense.search(q["question"], k=30)]
        assert ids(mine.rrf([a, b])) == ids(ref.rrf([a, b])), q["id"]
