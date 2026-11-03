"""Exercise 5: the version-aware post-filter drop_superseded in mine.py."""

import pytest

import mine
from ragkit import versions as ref
from ragkit.types import Chunk, Hit


def hit(doc, rank, supersedes=None, i=0):
    meta = {"title": doc}
    if supersedes is not None:
        meta["supersedes"] = supersedes
    c = Chunk(id=f"{doc}#{i}", doc_id=doc, text=doc, start=0, end=len(doc), index=i, meta=meta)
    return Hit(chunk=c, score=1.0 / rank, rank=rank, scores={"rrf": 1.0 / rank})


def docs(hits):
    return [h.chunk.doc_id for h in hits]


def test_worked_example():
    hs = [hit("hr-vacation-2024", 1), hit("hr-vacation-2026", 2, "hr-vacation-2024"), hit("hr-sick-leave", 3)]
    out = mine.drop_superseded(hs)
    assert docs(out) == ["hr-vacation-2026", "hr-sick-leave"]
    assert [h.rank for h in out] == [1, 2]


def test_input_not_modified_and_new_objects():
    hs = [hit("old", 1), hit("new", 2, "old"), hit("other", 3)]
    before = [(h.chunk.doc_id, h.rank) for h in hs]
    out = mine.drop_superseded(hs)
    assert [(h.chunk.doc_id, h.rank) for h in hs] == before
    assert out[0] is not hs[1]
    assert out[0].scores == hs[1].scores and out[0].score == hs[1].score


def test_old_version_stays_when_new_not_retrieved():
    hs = [hit("hr-vacation-2024", 1), hit("hr-sick-leave", 2)]
    assert docs(mine.drop_superseded(hs)) == ["hr-vacation-2024", "hr-sick-leave"]


def test_all_chunks_of_the_old_doc_are_dropped():
    hs = [hit("old", 1, i=0), hit("new", 2, "old"), hit("old", 3, i=4)]
    assert docs(mine.drop_superseded(hs)) == ["new"]


def test_supersedes_as_list():
    hs = [hit("a", 1), hit("b", 2), hit("ab-merged", 3, ["a", "b"]), hit("c", 4)]
    assert docs(mine.drop_superseded(hs)) == ["ab-merged", "c"]


def test_two_new_versions_of_one_old_doc():
    # hr-vacation-2026 and hr-vacation-2026-he both supersede hr-vacation-2024
    hs = [hit("hr-vacation-2024", 1), hit("hr-vacation-2026-he", 2, "hr-vacation-2024"),
          hit("hr-vacation-2026", 3, "hr-vacation-2024")]
    assert docs(mine.drop_superseded(hs)) == ["hr-vacation-2026-he", "hr-vacation-2026"]


def test_three_versions_only_the_newest_survives():
    # C supersedes B, B supersedes A, all three retrieved
    hs = [hit("A", 1), hit("B", 2, "A"), hit("C", 3, "B")]
    assert docs(mine.drop_superseded(hs)) == ["C"]


def test_self_reference_and_cycle_terminate():
    assert docs(mine.drop_superseded([hit("x", 1, "x")])) == ["x"]
    out = mine.drop_superseded([hit("p", 1, "q"), hit("q", 2, "p"), hit("r", 3)])
    assert "r" in docs(out)


def test_empty():
    assert mine.drop_superseded([]) == []


def test_matches_reference_on_acme_version_questions(bm25, dense, qa):
    """Hybrid (BM25 + fake dense, RRF) top 30 for every version_conflict question."""
    from ragkit.hybrid import HybridRetriever
    h = HybridRetriever({"bm25": bm25, "dense": dense})
    n_dropped = 0
    for q in qa:
        if q["type"] != "version_conflict":
            continue
        hits = h.search(q["question"], k=30)
        m, r = mine.drop_superseded(hits), ref.drop_superseded(hits)
        assert [x.chunk.id for x in m] == [x.chunk.id for x in r], q["id"]
        assert [x.rank for x in m] == list(range(1, len(m) + 1))
        n_dropped += len(hits) - len(m)
    assert n_dropped > 0          # the corpus really has superseded versions in these results
