"""M5: resolve_citations (mine.py)."""

from mine import resolve_citations
from ragkit.types import Chunk, Hit


def ctx():
    out = []
    for i, (doc, sec, date) in enumerate([("hr-vacation-2026", "Vacation Policy > Carry-over", "2026-01-01"),
                                          ("co-glossary", "", ""), ("eng-service-catalog", "Services", "2026-09-01")], 1):
        text = f"text of {doc} " * 30
        c = Chunk(id=f"{doc}#{i}", doc_id=doc, text=text, start=100 * i, end=100 * i + len(text), index=i,
                  section_path=tuple(s for s in sec.split(" > ") if s),
                  meta={"title": doc.upper(), "effective_date": date})
        out.append(Hit(chunk=c, score=1.0, rank=i))
    return out


def test_no_markers():
    assert resolve_citations("not in the documents", ctx()) == []


def test_single_and_fields():
    cs = resolve_citations("Up to 5 days carry over [1].", ctx())
    assert len(cs) == 1
    c = cs[0]
    assert (c.n, c.valid, c.doc_id, c.chunk_id) == (1, True, "hr-vacation-2026", "hr-vacation-2026#1")
    assert c.title == "HR-VACATION-2026" and c.section == "Vacation Policy > Carry-over"
    assert c.effective_date == "2026-01-01" and (c.start, c.end) == (100, 100 + len(ctx()[0].chunk.text))
    assert c.snippet.endswith("…") and len(c.snippet) <= 240


def test_empty_section_and_date_are_none():
    c = resolve_citations("Blue Room is a meeting room [2].", ctx())[0]
    assert c.section is None and c.effective_date is None


def test_groups_order_and_duplicates():
    cs = resolve_citations("A [3]. B [1, 3]. C [2;1]. D [3][2].", ctx())
    assert [c.n for c in cs] == [3, 1, 2]


def test_invalid_numbers():
    cs = resolve_citations("Made up [4] and [0], real [2].", ctx())
    assert [(c.n, c.valid) for c in cs] == [(4, False), (0, False), (2, True)]
    bad = cs[0]
    assert bad.doc_id is None and bad.start is None and bad.snippet is None


def test_hebrew_text():
    cs = resolve_citations("עובד מקבל 14 ימי חופשה [1]. הימים נצברים מדי חודש [1].", ctx())
    assert [c.n for c in cs] == [1]
