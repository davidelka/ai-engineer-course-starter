"""M4: retrieval_row (mine.py). The per-question numbers behind recall@k, MRR and page@1."""

import pytest

from mine import retrieval_row

KEYS = {"r1", "r5", "r10", "rr", "page_ok", "must_not_hit"}


def test_keys_and_first_hit():
    q = {"relevant": ["home/lease-2026.pdf"]}
    row = retrieval_row(q, [("home/lease-2026.pdf", 1), ("x", None)])
    assert set(row) == KEYS
    assert row["r1"] == row["r5"] == row["r10"] == 1.0 and row["rr"] == 1.0 and row["page_ok"] is None


def test_recall_at_k_and_rr():
    q = {"relevant": ["a", "b"]}
    ranked = [(f, None) for f in ["x1", "a", "x2", "x3", "x4", "x5", "b"]]
    row = retrieval_row(q, ranked)
    assert row["r1"] == 0.0 and row["r5"] == pytest.approx(0.5) and row["r10"] == 1.0
    assert row["rr"] == pytest.approx(0.5)


def test_not_found():
    row = retrieval_row({"relevant": ["a"]}, [("x", None)])
    assert row["rr"] == 0.0 and row["r10"] == 0.0


def test_page_ok_uses_the_first_paged_file():
    q = {"relevant": ["home/lease-2026.pdf", "home/lease-2026 (1).pdf"], "pages": {"home/lease-2026.pdf": [2]}}
    assert retrieval_row(q, [("home/lease-2026 (1).pdf", 1), ("home/lease-2026.pdf", 2)])["page_ok"] is True
    assert retrieval_row(q, [("home/lease-2026.pdf", 1)])["page_ok"] is False
    assert retrieval_row(q, [("other", 2)])["page_ok"] is False


def test_negative_question():
    q = {"relevant": [], "must_not": ["private/passwords-DO-NOT-INDEX.txt"]}
    row = retrieval_row(q, [("home/a.md", None)])
    assert row["r1"] == row["r5"] == row["r10"] == 0.0 and row["must_not_hit"] == []
    leak = retrieval_row(q, [("private/passwords-DO-NOT-INDEX.txt", None), ("home/a.md", None)])
    assert leak["must_not_hit"] == ["private/passwords-DO-NOT-INDEX.txt"]
