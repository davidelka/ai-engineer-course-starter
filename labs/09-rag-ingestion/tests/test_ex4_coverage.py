"""Exercise 4: quote_status in mine.py."""

import mine
from ragkit.chunking import make_chunker
from ragkit.evaluate import quote_coverage


def test_covered_split_missing():
    doc = "Up to 5 unused days may be carried over to the next calendar year. Days expire on March 31."
    whole = [doc]
    halves = ["Up to 5 unused days may be carried", "over to the next calendar year. Days expire on March 31."]
    q = "carried over to the next calendar year"
    assert mine.quote_status(q, doc, whole) == "covered"
    assert mine.quote_status(q, doc, halves) == "split"
    assert mine.quote_status("expire on April 30", doc, whole) == "missing"


def test_whitespace_is_normalized():
    doc = "at least 99.95% of the time\nin each calendar   month"
    assert mine.quote_status("of the time in each calendar month", doc, [doc]) == "covered"
    assert mine.quote_status("the  time\n in each", "x the time in each y", ["x the time in each y"]) == "covered"


def test_no_chunks_means_split_not_missing():
    assert mine.quote_status("abc", "xx abc yy", []) == "split"


def test_overlapping_chunks_count_as_covered():
    doc = "one two three four five six"
    assert mine.quote_status("three four", doc, ["one two three", "three four five", "five six"]) == "covered"


def test_hebrew_quote():
    doc = "ההסעה יוצאת בשעות 08:15, 08:45 ו-09:15, וחוזרת לתחנה."
    assert mine.quote_status("ההסעה יוצאת בשעות 08:15, 08:45 ו-09:15", doc, [doc]) == "covered"
    assert mine.quote_status("ההסעה יוצאת בשעות 08:15, 08:45 ו-09:15", doc,
                             ["ההסעה יוצאת בשעות 08:15,", "08:45 ו-09:15, וחוזרת"]) == "split"


def test_matches_reference_on_the_corpus(docs, qa, tok):
    """On the whole corpus with fixed 128-token chunks (no overlap), your counts must match the
    reference exactly."""
    chunks = make_chunker("fixed:128:0", tok).split_all(docs.values())
    ref = quote_coverage(docs.values(), chunks, qa)
    by_doc = {}
    for c in chunks:
        by_doc.setdefault(c.doc_id, []).append(c.text)
    mine_status = [mine.quote_status(r.quote, docs[r.source_id].text, by_doc.get(r.source_id, []))
                   for r in ref.rows]
    assert mine_status == [r.status for r in ref.rows]
    assert mine_status.count("split") > 10
