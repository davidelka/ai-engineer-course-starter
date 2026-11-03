"""Exercise 3: recall_at_k and reciprocal_rank in mine.py, checked by hand and on the golden set."""

import pytest

import mine
from ragkit import metrics as ref
from ragkit.retrieval import BM25Index


def test_recall_dedupes_documents():
    r = ["x", "a", "x", "b", "c"]
    assert mine.recall_at_k(r, ["a", "b"], 1) == 0.0
    assert mine.recall_at_k(r, ["a", "b"], 2) == 0.5
    assert mine.recall_at_k(r, ["a", "b"], 3) == 1.0
    assert mine.recall_at_k(r, {"a", "b", "zz"}, 10) == pytest.approx(2 / 3)


def test_recall_empty_relevant_raises():
    with pytest.raises(ValueError):
        mine.recall_at_k(["a"], [], 5)


def test_reciprocal_rank():
    r = ["x", "a", "x", "b"]
    assert mine.reciprocal_rank(r, ["x"]) == 1.0
    assert mine.reciprocal_rank(r, ["b"]) == pytest.approx(1 / 3)
    assert mine.reciprocal_rank(r, ["b"], k=2) == 0.0
    assert mine.reciprocal_rank(r, ["b"], k=3) == pytest.approx(1 / 3)
    assert mine.reciprocal_rank(r, ["nope"]) == 0.0
    assert mine.reciprocal_rank([], ["a"]) == 0.0


def test_multi_hop_partial_credit():
    # q040-like: two source documents, only one retrieved in the top 5
    r = ["eng-pm-2026-08-api", "eng-runbook-api", "sales-sla-2025", "eng-pm-2026-06-billing", "co-glossary"]
    assert mine.recall_at_k(r, ["eng-pm-2026-08-api", "eng-service-catalog"], 5) == 0.5
    assert mine.reciprocal_rank(r, ["eng-pm-2026-08-api", "eng-service-catalog"]) == 1.0


def test_matches_reference_on_golden_set(chunks, qa):
    """BM25 on the 69 answerable golden questions: your numbers must equal ragkit's."""
    idx = BM25Index()
    idx.add(chunks)
    for q in qa:
        if not q["source_ids"]:
            continue
        ranked = [h.chunk.doc_id for h in idx.search(q["question"], k=30)]
        for k in (1, 5, 10):
            assert mine.recall_at_k(ranked, q["source_ids"], k) == pytest.approx(
                ref.recall_at_k(ranked, q["source_ids"], k)), (q["id"], k)
        assert mine.reciprocal_rank(ranked, q["source_ids"], 10) == pytest.approx(
            ref.reciprocal_rank(ranked, q["source_ids"], 10)), q["id"]
