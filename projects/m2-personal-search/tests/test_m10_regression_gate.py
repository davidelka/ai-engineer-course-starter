"""M10: the regression gate. The whole system (your mine.py functions where implemented, the
references elsewhere) on the sample folder and the 52 golden queries, offline and free.

The floors sit a little below what the reference reaches with the FAKE embedder (hashing, not
semantic) and the extractive answerer (not a language model). They protect the plumbing:
parsing, Hebrew PDF fixes, chunking, filters, privacy excludes, citations. Two more gates turn on
when you have the real thing:
- PSS_GATE_EMBEDDER=e5-small   rebuilds the index with real local embeddings and asserts that
                               hybrid is at least as good as BM25 and better on the semantic and
                               cross-lingual queries (the reason dense retrieval exists).
- data/recorded/*.jsonl        answers recorded from a real model (python -m pss eval --llm
                               ollama:qwen3.5:4b --record) are scored against answer floors.
"""

import os
from pathlib import Path

import pytest

from pss import hooks
from pss.evaluate import (build_index, eval_answers, eval_recorded, eval_retrieval, eval_settings,
                          load_golden)

GOLDEN = load_golden()


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    idx, build = build_index(eval_settings(index_dir=str(tmp_path_factory.mktemp("gate")), ocr="off"))
    return idx, build


def test_golden_set_shape():
    assert 40 <= len(GOLDEN) <= 60
    kinds = {q["kind"] for q in GOLDEN}
    assert {"keyword", "semantic", "cross-lingual", "filter", "ocr", "negative"} <= kinds
    assert sum(q["lang"] == "he" for q in GOLDEN) >= 20 and sum(q["lang"] == "en" for q in GOLDEN) >= 20
    from pss.config import SAMPLE
    for q in GOLDEN:
        for f in q["relevant"] + list(q.get("pages", {})):
            assert (SAMPLE / f).exists(), (q["id"], f)


def test_index_shape(built):
    idx, build = built
    assert build["files"] == 43                      # 45 files minus private/ and .cache/
    assert not any(f.startswith(("private/", ".cache/")) for f in idx.manifest.files)
    assert idx.manifest.files["home/lease-2026.pdf"]["pages"] == 3
    assert len(idx.dups) == 3


def test_hebrew_pdf_text_is_logical(built):
    idx, _ = built
    text = idx.doc_texts()["home/lease-2026.pdf"]
    assert "ערבות בנקאית בסך 12,600" in text           # visual order fixed, number in place
    assert "תוריכש" not in text                       # no reversed words left


def test_retrieval_gate(built):
    idx, _ = built
    r = eval_retrieval(idx, GOLDEN, kinds={"keyword", "semantic", "cross-lingual", "filter"})
    bm, hy = r["modes"]["bm25"], r["modes"]["hybrid"]
    assert bm["all"]["recall@5"] >= 0.80 and hy["all"]["recall@5"] >= 0.80
    assert hy["all"]["mrr"] >= 0.72
    assert bm["by_kind"]["keyword"]["recall@5"] >= 0.95
    assert hy["by_kind"]["filter"]["recall@5"] >= 0.95
    assert bm["all"]["page@1"] >= 0.60
    assert all(m["must_not_violations"] == 0 for m in r["modes"].values())


def test_answer_gate(built):
    from ragkit.fake import ExtractiveAnswerer

    idx, _ = built
    a = eval_answers(idx, GOLDEN, ExtractiveAnswerer(), kinds={"keyword", "semantic", "cross-lingual", "filter"})
    s = a["summary"]
    assert s["invalid_citations"] == 0
    assert s["grounded"] >= 0.90                      # every cited sentence's numbers are in its source
    assert s["fact_coverage"] >= 0.25 and s["cited_relevant"] >= 0.50


@pytest.mark.skipif(not os.environ.get("PSS_GATE_EMBEDDER"), reason="set PSS_GATE_EMBEDDER=e5-small to run")
def test_real_embedder_gate(tmp_path):
    idx, _ = build_index(eval_settings(index_dir=str(tmp_path / "e5"), ocr="off",
                                       embedder=os.environ["PSS_GATE_EMBEDDER"]))
    r = eval_retrieval(idx, GOLDEN, kinds={"keyword", "semantic", "cross-lingual", "filter"})
    bm, hy = r["modes"]["bm25"], r["modes"]["hybrid"]
    assert hy["all"]["recall@5"] >= bm["all"]["recall@5"]
    assert hy["by_kind"]["cross-lingual"]["recall@5"] > bm["by_kind"]["cross-lingual"]["recall@5"]
    assert hy["by_kind"]["semantic"]["recall@5"] >= bm["by_kind"]["semantic"]["recall@5"]


RECORDED = sorted((Path(__file__).resolve().parent.parent / "data" / "recorded").glob("*.jsonl"))


@pytest.mark.skipif(not RECORDED, reason="no recorded model answers (python -m pss eval --llm ollama:... --record)")
@pytest.mark.parametrize("path", RECORDED, ids=[p.stem for p in RECORDED])
def test_recorded_answers_gate(path):
    r = eval_recorded(GOLDEN, path)
    assert not r["stale"], "the golden set changed since this recording: record again"
    s = r["summary"]
    assert s["invalid_citations"] <= 1
    assert s["cited_relevant"] >= 0.70 and s["fact_coverage"] >= 0.60
    assert s["abstain_accuracy"] is None or s["abstain_accuracy"] >= 0.5


def test_notice_when_mine_is_not_implemented():
    hooks._cache.clear()
    fn = hooks.get("is_excluded")
    assert callable(fn)
