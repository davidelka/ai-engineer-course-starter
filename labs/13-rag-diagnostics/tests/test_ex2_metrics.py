"""Exercise 2: stage-wise metrics from golden quotes."""
import math

import pytest

import mine


def close(a, b):
    return a is not None and math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)


def test_context_recall_docstring():
    assert close(mine.context_recall(["Up to 5 days.", "Expire  on March 31."],
                                     ["... up to 5 days. Carried ...", "nothing"]), 0.5)


def test_context_recall_normalizes_whitespace_and_case():
    quotes = ["Carried-over days expire on March 31."]
    assert close(mine.context_recall(quotes, ["- Up to 5.\n  Carried-over   days EXPIRE on\nMarch 31."]), 1.0)
    assert close(mine.context_recall(quotes, ["Carried-over days expire on March"]), 0.0)   # must be WHOLE


def test_context_recall_counts_each_quote_once_and_none_when_empty():
    assert close(mine.context_recall(["a b"], ["a b", "x a b"]), 1.0)
    assert close(mine.context_recall(["a b", "c d", "e f"], ["c d e f"]), 2 / 3)
    assert mine.context_recall([], ["anything"]) is None
    assert close(mine.context_recall(["a"], []), 0.0)


@pytest.mark.parametrize("rel,expected", [
    ([True, False, True], (1 / 1 + 2 / 3) / 2),
    ([False, True], 0.5),
    ([True, True, True], 1.0),
    ([False, False, True], 1 / 3),
    ([False, False], 0.0),
    ([True], 1.0),
])
def test_context_precision(rel, expected):
    assert close(mine.context_precision(rel), expected)


def test_context_precision_is_rank_aware_and_none_when_empty():
    assert mine.context_precision([True, False]) > mine.context_precision([False, True])
    assert mine.context_precision([]) is None


def test_citation_precision():
    assert close(mine.citation_precision([1, 3, 1], {1, 2}), 0.5)
    assert close(mine.citation_precision([2], {1, 2}), 1.0)
    assert close(mine.citation_precision([9], {1, 2}), 0.0)          # invented [9]
    assert mine.citation_precision([], {1}) is None
    assert close(mine.citation_precision([1, 2, 3, 4], set()), 0.0)


def test_citation_recall():
    assert close(mine.citation_recall([1], [{1}, {2, 3}]), 0.5)
    assert close(mine.citation_recall([2], [{1}, set()]), 0.0)
    assert close(mine.citation_recall([3, 1], [{1}, {2, 3}]), 1.0)
    assert close(mine.citation_recall([1, 1, 1], [{1}, {1}, {4}]), 2 / 3)
    assert mine.citation_recall([1], []) is None


def test_matches_reference_on_a_real_trace():
    """The same numbers as ragkit.diagnose on trace T3 (fixtures/traces.jsonl)."""
    import json
    from pathlib import Path
    from ragkit import diagnose as ref
    tr = [json.loads(x) for x in (Path(__file__).resolve().parent.parent / "fixtures" / "traces.jsonl")
          .read_text(encoding="utf-8").splitlines() if x.strip()][2]
    texts = [c["text"] for c in tr["context"]]
    locs = ref.quote_locations(tr["quotes"], texts)
    rel = ref.relevance_from_quotes(tr["quotes"], texts)
    sup = {i for s in locs for i in s}
    assert mine.context_recall(tr["quotes"], texts) == ref.context_recall(tr["quotes"], texts)
    assert mine.context_precision(rel) == ref.context_precision(rel)
    assert mine.citation_precision(tr["citations"], sup) == ref.citation_precision(tr["citations"], sup)
    assert mine.citation_recall(tr["citations"], locs) == ref.citation_recall(tr["citations"], locs)
