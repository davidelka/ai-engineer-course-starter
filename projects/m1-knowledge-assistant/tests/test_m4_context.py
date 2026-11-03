"""M4: pack_context (mine.py). Small hand-made hits, so every rule is tested on its own."""

from mine import pack_context
from ragkit.types import Chunk, Hit


def H(doc, i, text, rank=None):
    c = Chunk(id=f"{doc}#{i}", doc_id=doc, text=text, start=0, end=len(text), index=i)
    return Hit(chunk=c, score=1.0 / (rank or i + 1), rank=rank or i + 1, scores={"rrf": 0.1})


def words(n, tag="w"):
    return " ".join(f"{tag}{i}" for i in range(n))


COUNT = lambda t: len(t.split())  # noqa: E731  (1 word = 1 token, so budgets are easy to read)


def test_empty():
    assert pack_context([]) == []


def test_keeps_order_and_renumbers():
    hits = [H("a", 0, "alpha one", 3), H("b", 0, "beta two", 7), H("c", 0, "gamma three", 9)]
    out = pack_context(hits, count=COUNT)
    assert [h.chunk.id for h in out] == ["a#0", "b#0", "c#0"]
    assert [h.rank for h in out] == [1, 2, 3]
    assert [h.rank for h in hits] == [3, 7, 9]           # input untouched
    assert out[0] is not hits[0] and out[0].scores == hits[0].scores and out[0].scores is not hits[0].scores


def test_duplicate_text_is_skipped():
    hits = [H("it-laptop-policy", 0, "Report a  stolen laptop\nwithin 1 hour."),
            H("it-laptop-faq", 0, "report a stolen laptop within 1 hour."),
            H("x", 0, "something else")]
    out = pack_context(hits, count=COUNT)
    assert [h.chunk.doc_id for h in out] == ["it-laptop-policy", "x"]


def test_max_per_doc():
    hits = [H("a", 0, "a zero"), H("a", 1, "a one"), H("a", 2, "a two"), H("b", 0, "b zero")]
    out = pack_context(hits, count=COUNT, max_per_doc=2)
    assert [h.chunk.id for h in out] == ["a#0", "a#1", "b#0"]
    out1 = pack_context(hits, count=COUNT, max_per_doc=1)
    assert [h.chunk.id for h in out1] == ["a#0", "b#0"]


def test_budget_skips_and_continues():
    hits = [H("a", 0, words(60, "a")), H("b", 0, words(50, "b")), H("c", 0, words(30, "c"))]
    out = pack_context(hits, count=COUNT, max_tokens=100)
    assert [h.chunk.doc_id for h in out] == ["a", "c"]      # b would exceed 100, c still fits


def test_first_hit_kept_even_over_budget():
    hits = [H("a", 0, words(500, "a")), H("b", 0, words(10, "b"))]
    out = pack_context(hits, count=COUNT, max_tokens=100)
    assert [h.chunk.doc_id for h in out] == ["a"]


def test_max_chunks():
    hits = [H(f"d{i}", 0, f"text number {i}") for i in range(10)]
    assert len(pack_context(hits, count=COUNT, max_chunks=4)) == 4


def test_default_counter_runs():
    hits = [H("a", 0, "Up to 5 unused days may be carried over."), H("b", 0, "They expire on March 31.")]
    assert len(pack_context(hits)) == 2
