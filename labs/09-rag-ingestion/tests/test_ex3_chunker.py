"""Exercise 3: heading_chunks in mine.py."""

import json
from pathlib import Path

import pytest

import mine
from ragkit.clean import collapse_ws
from ragkit.types import Document

GOLDEN = json.loads((Path(__file__).parent / "golden_sections.json").read_text(encoding="utf-8"))
SAMPLE_IDS = ["hr-vacation-2026", "eng-architecture", "co-haifa-office-he", "sales-sla-2026",
              "hr-relocation", "it-helpdesk", "sales-pricing-2026", "hr-onboarding-he"]


def test_offsets_ids_and_metadata(docs, tok):
    for doc_id in SAMPLE_IDS:
        d = docs[doc_id]
        cs = mine.heading_chunks(d, 400, 40, tok)
        assert cs, doc_id
        for i, c in enumerate(cs):
            assert d.text[c.start:c.end] == c.text, f"{c.id}: text does not match its offsets"
            assert c.text == c.text.strip() and c.text
            assert c.id == f"{doc_id}#{i}" and c.index == i and c.doc_id == doc_id
            assert isinstance(c.section_path, tuple)
            assert c.n_tokens == tok.count(c.text)
            for key in ("title", "effective_date", "classification", "language", "version"):
                assert c.meta.get(key) == d.meta.get(key), (c.id, key)


@pytest.mark.parametrize("max_tokens", [120, 400])
def test_max_tokens_respected_everywhere(docs, tok, max_tokens):
    for d in docs.values():
        for c in mine.heading_chunks(d, max_tokens, 20, tok):
            assert c.n_tokens <= max_tokens, (c.id, c.n_tokens)


def test_every_golden_quote_lands_in_the_right_section(docs, tok):
    """golden_sections.json: for each golden source quote, the acceptable section paths."""
    chunks = {i: mine.heading_chunks(d, 400, 40, tok) for i, d in docs.items()}
    wrong, split = [], []
    for row in GOLDEN:
        quote = collapse_ws(row["quote"])
        holders = [c for c in chunks[row["source_id"]] if quote in collapse_ws(c.text)]
        if not holders:
            split.append(row["qid"])
            continue
        ok = {tuple(p) for p in row["paths"]}
        if not any(c.section_path in ok for c in holders):
            wrong.append((row["qid"], holders[0].section_path, row["paths"]))
    assert not split, f"quotes cut between chunks: {split}"
    assert not wrong, f"wrong section paths: {wrong[:3]}"


def test_heading_only_section_joins_the_next(tok):
    """'### Deep' has no body: its heading line joins Part B's chunk, which keeps Part B's path."""
    d = Document(id="t", text="# Title\n\n## Part A\n\nAlpha text here.\n\n### Deep\n\n## Part B\n\nBeta.",
                 meta={"title": "T"})
    cs = mine.heading_chunks(d, 400, 0, tok)
    assert [c.section_path for c in cs] == [("Title", "Part A"), ("Title", "Part B")]
    assert cs[0].text.startswith("# Title") and "Alpha" in cs[0].text
    assert cs[1].text == "### Deep\n\n## Part B\n\nBeta."


def test_heading_only_section_joins_the_next_simple(tok):
    d = Document(id="t", text="# Title\n\n## Part A\n\nAlpha text here.\n\n## Part B\n\nBeta.", meta={})
    cs = mine.heading_chunks(d, 400, 0, tok)
    assert [c.section_path for c in cs] == [("Title", "Part A"), ("Title", "Part B")]
    assert cs[0].text == "# Title\n\n## Part A\n\nAlpha text here."


def test_preamble_has_empty_path(tok):
    d = Document(id="t", text="Some intro.\n\n# A\n\nBody.", meta={})
    cs = mine.heading_chunks(d, 400, 0, tok)
    assert cs[0].section_path == () and cs[0].text == "Some intro."
    assert cs[1].section_path == ("A",)


def test_long_section_split_with_overlap_keeps_path(tok):
    body = " ".join(f"Rule {i} says that requests are reviewed in order." for i in range(60))
    d = Document(id="t", text=f"# Doc\n\n## Long\n\n{body}\n\n## Short\n\nEnd.", meta={})
    cs = mine.heading_chunks(d, 60, 15, tok)
    longs = [c for c in cs if c.section_path == ("Doc", "Long")]
    assert len(longs) >= 4
    assert all(c.n_tokens <= 60 for c in longs)
    assert all(b.start < a.end for a, b in zip(longs, longs[1:])), "consecutive pieces should overlap"
    assert cs[-1].section_path == ("Doc", "Short") and cs[-1].text.startswith("## Short")
