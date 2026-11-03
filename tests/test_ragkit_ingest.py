"""Lesson 9: ragkit ingestion, chunking, BM25 and the answer loop. Offline and free.

Uses the approx tokenizer everywhere, so results are identical with or without tiktoken.
"""

from __future__ import annotations

import shutil
from functools import partial

import pytest

from llmkit import LLM, RetryPolicy
from mockllm import MockConfig, start_in_thread
from ragkit import (BM25Index, Document, IngestPipeline, NOT_FOUND, answer, build_request,
                    content_hash, load_document, make_chunker, normalize, parse_citations,
                    plan_ingest)
from ragkit.acme import DOCS_DIR, acme_documents, acme_qa
from ragkit.chunking import HeadingChunker, sentence_spans
from ragkit.clean import collapse_ws, repeated_lines
from ragkit.evaluate import answer_checks, quote_coverage, quote_status, retrieval_eval
from ragkit.fake import ExtractiveAnswerer
from ragkit.retrieval import analyze, hebrew_variants
from ragkit.structure import SectionIndex
from ragkit.tokens import ApproxTokenizer, get_tokenizer

TOK = ApproxTokenizer()
SPECS = ["fixed:128:16", "recursive:200:20", "heading:300:30", "heading:400:40:150", "sentence:150:1"]


@pytest.fixture(scope="module")
def docs():
    return acme_documents()


@pytest.fixture(scope="module")
def by_id(docs):
    return {d.id: d for d in docs}


@pytest.fixture(scope="module")
def qa():
    return acme_qa()


# ------------------------------------------------------------------ cleaning

def test_normalize_hebrew_invisibles_and_spaces():
    raw = "‏מדיניות חופשה​  2026\r\nסמנכ״ל   ומנכ׳\n\n\n\nשָׁלוֹם"
    out = normalize(raw)
    assert out == 'מדיניות חופשה 2026\nסמנכ"ל ומנכ\'\n\nשלום'
    assert collapse_ws("a\n  b\tc") == "a b c"


def test_repeated_lines_detects_headers_with_page_numbers():
    pages = ["Acme | SLA\nPage 1\nbody one", "Acme | SLA\nPage 2\nbody two", "Acme | SLA\nPage 3\nthree"]
    keys = repeated_lines(pages)
    assert "acme | sla" in keys and "page #" in keys and "body one" not in keys


# ------------------------------------------------------------------ loaders

def test_corpus_loads_all_formats(docs):
    assert len(docs) == 55
    fmts = {d.format for d in docs}
    assert fmts == {"md", "html", "pdf", "docx"}
    assert not any(d.id.endswith(".meta") for d in docs)          # sidecars are not documents
    for d in docs:
        for key in ("title", "effective_date", "classification", "language", "version"):
            assert d.meta.get(key), (d.id, key)
        assert d.content_hash and d.text.strip()


def test_markdown_front_matter_stripped(by_id):
    d = by_id["hr-vacation-2026"]
    assert not d.text.startswith("---") and d.text.startswith("# Vacation Policy")
    assert d.meta["supersedes"] == "hr-vacation-2024" and d.meta["version"] == "2.0"


def test_html_boilerplate_removed():
    d = load_document(DOCS_DIR / "it-helpdesk.html", keep_raw=True)
    assert "cookies" in d.extras["raw_text"] and "cookies" not in d.text
    assert "Directory" not in d.text and "intranet build" not in d.text
    assert d.text.startswith("# IT Helpdesk")
    assert "- Email: it@acme.example (creates a Fixit ticket automatically)" in d.text
    assert len(d.extras["removed"]) >= 4


def test_html_hebrew_rtl_page():
    d = load_document(DOCS_DIR / "co-haifa-office-he.html")
    assert d.language == "he"
    assert "ההסעה יוצאת בשעות 08:15, 08:45 ו-09:15" in d.text
    assert "עוגיות" not in d.text and "## כתובת והגעה" in d.text


def test_pdf_headers_removed_and_table_rows_kept():
    d = load_document(DOCS_DIR / "sales-sla-2026.pdf", keep_raw=True)
    assert d.text.count("Version 2.0") == 0 and "Page 1" not in d.text
    assert any("Page 1" in r for r in d.extras["removed"])
    assert "Enterprise | below 99.95% but at least 99.5% | 10%" in d.text
    assert "## 2. Service credits" in d.text and d.text.startswith("# Acme Flow Service Level")
    plain = load_document(DOCS_DIR / "sales-sla-2026.pdf", mode="plain")
    assert "Enterprise | below 99.95%" not in plain.text      # plain mode loses the rows


def test_pdf_wrapped_table_cell_rejoined():
    d = load_document(DOCS_DIR / "fin-travel-2026.pdf")
    assert "High-cost cities (London, New York, San Francisco, Zurich, Paris, Tokyo) | $110" in d.text


def test_docx_header_footer_removed_table_kept():
    d = load_document(DOCS_DIR / "hr-relocation.docx", keep_raw=True)
    assert "People Team - Confidential" not in d.text
    assert "People Team - Confidential" in d.extras["raw_text"]
    assert "Israel to Berlin | 8,000 EUR | up to 30 nights" in d.text
    assert "## Repayment" in d.text and d.meta["classification"] == "confidential"


def test_every_golden_quote_survives_extraction(docs, qa):
    rep = quote_coverage(docs, [], qa)
    assert rep.count("missing") == 0 and rep.count("no_doc") == 0


# ------------------------------------------------------------------ chunking

@pytest.mark.parametrize("spec", SPECS)
def test_chunk_offsets_metadata_and_size(docs, spec):
    ch = make_chunker(spec, TOK)
    limit = int(spec.split(":")[1])
    for d in docs:
        cs = ch.split(d)
        assert cs, d.id
        for i, c in enumerate(cs):
            assert d.text[c.start:c.end] == c.text
            assert c.id == f"{d.id}#{i}" and c.index == i and c.doc_id == d.id
            assert c.meta["effective_date"] == d.effective_date
            assert c.meta["classification"] == d.classification
            assert c.n_tokens == TOK.count(c.text)
            if not spec.startswith("sentence"):
                assert c.n_tokens <= limit, (spec, c.id, c.n_tokens)


def test_fixed_chunks_overlap(by_id):
    cs = make_chunker("fixed:100:20", TOK).split(by_id["eng-architecture"])
    assert all(b.start < a.end for a, b in zip(cs, cs[1:]))


def test_heading_chunker_section_paths(by_id):
    cs = HeadingChunker(400, 40, tokenizer=TOK).split(by_id["hr-vacation-2026"])
    carry = next(c for c in cs if "Carried-over days expire on March 31" in c.text)
    assert carry.section_path == ("Vacation Policy (effective January 2026)", "Carry-over")
    assert carry.text.startswith("## Carry-over")
    assert all(not c.text.strip().startswith("#") or "\n" in c.text for c in cs)  # no heading-only chunk


def test_heading_chunker_merges_heading_only_section():
    text = "# Title\n\n## Part A\n\nAlpha text here.\n\n## Part B\n\nBeta text."
    d = Document(id="t", text=text, meta={"title": "T"})
    cs = HeadingChunker(400, 0, tokenizer=TOK).split(d)
    assert [c.section_path for c in cs] == [("Title", "Part A"), ("Title", "Part B")]
    assert cs[0].text.startswith("# Title")


def test_heading_chunker_long_section_keeps_path():
    body = " ".join(f"Sentence number {i} is about the long section." for i in range(80))
    d = Document(id="t", text=f"# Doc\n\n## Long\n\n{body}\n\n## Short\n\nEnd.", meta={})
    cs = HeadingChunker(60, 10, tokenizer=TOK).split(d)
    longs = [c for c in cs if c.section_path == ("Doc", "Long")]
    assert len(longs) > 3 and all(c.n_tokens <= 60 for c in longs)
    assert cs[-1].section_path == ("Doc", "Short")


def test_sentence_spans_english_and_hebrew():
    t = "Up to 5 days, e.g. for reserve duty. Days expire on March 31! שלום עולם. מה שלומך?"
    sents = [t[a:b] for a, b in sentence_spans(t)]
    assert sents == ["Up to 5 days, e.g. for reserve duty.", "Days expire on March 31!",
                     "שלום עולם.", "מה שלומך?"]


def test_section_index():
    s = SectionIndex("intro\n# A\ntext\n## B\nmore\n# C\nend")
    assert s.section_path(0) == () and s.section_path(15) == ("A", "B") and s.section_path(30) == ("C",)


def test_quote_coverage_heading_vs_fixed(docs, qa):
    good = quote_coverage(docs, make_chunker("heading:400:40", TOK).split_all(docs), qa)
    bad = quote_coverage(docs, make_chunker("fixed:128:0", TOK).split_all(docs), qa)
    assert good.coverage == 1.0
    assert bad.count("split") > 10 and bad.count("missing") == 0


def test_quote_status():
    assert quote_status("a  b", "x a\nb y", ["x a\nb y"]) == "covered"
    assert quote_status("a b", "x a b y", ["x a", "b y"]) == "split"
    assert quote_status("zzz", "x a b y", ["x a b y"]) == "missing"


# ------------------------------------------------------------------ retrieval

def test_hebrew_prefix_variants():
    assert hebrew_variants("בחניון") == ["חניון"]
    assert "חופשה" in analyze("והחופשה") and "חופשה" in hebrew_variants("והחופשה")
    assert hebrew_variants("מה") == [] and hebrew_variants("vacation") == []
    assert analyze("the vacation", stopwords=True) == ["vacation"]


@pytest.fixture(scope="module")
def index(docs):
    idx = BM25Index()
    idx.add(make_chunker("heading:400:40:150", TOK).split_all(docs))
    return idx


def test_bm25_finds_carry_over(index):
    hits = index.search("How many vacation days can I carry over?", k=3)
    assert hits[0].chunk.doc_id in ("hr-vacation-2026", "hr-vacation-2024")
    assert hits[0].rank == 1 and hits[0].score >= hits[-1].score and "bm25" in hits[0].scores
    exp = index.explain("vacation carry", hits[0].chunk.id)
    assert exp["vacation"] > 0


def test_bm25_filters(index):
    he = index.search("חופשה", k=5, where={"language": "he"})
    assert he and all(h.chunk.language == "he" for h in he)
    new = index.search("vacation carry over", k=5, where={"effective_date": {"$gte": "2026-01-01"}})
    assert all(h.chunk.effective_date >= "2026-01-01" for h in new)
    pub = index.search("uptime", k=5, where={"classification": ["public"]})
    assert all(h.chunk.classification == "public" for h in pub)


def test_bm25_remove_and_add():
    d = Document(id="x", text="# X\n\nZanzibar policy text.", meta={"title": "X"})
    idx = BM25Index()
    idx.add(make_chunker("heading:100:0", TOK).split(d))
    assert idx.search("zanzibar")
    assert idx.remove("x") == 1 and idx.search("zanzibar") == []


def test_retrieval_baseline_quality(index, qa):
    rows = retrieval_eval(index, qa, k=5)
    assert len(rows) == 69
    assert sum(r.quote_hit for r in rows) / len(rows) >= 0.85
    assert sum(r.doc_hit for r in rows) / len(rows) >= 0.9


# ------------------------------------------------------------------ ingestion

def test_content_hash_and_plan():
    assert content_hash(b"a", {"x": 1, "y": 2}) == content_hash(b"a", {"y": 2, "x": 1})
    assert content_hash(b"a", {"x": 1}) != content_hash(b"a", {"x": 2})
    assert content_hash(b"a") != content_hash(b"b")
    p = plan_ingest({"a": "1", "b": "2", "c": "3"}, {"a": "1", "b": "9", "d": "4"})
    assert (p.added, p.changed, p.unchanged, p.removed) == (["d"], ["b"], ["a"], ["c"])
    p = plan_ingest({"a": "1"}, {"a": "1"}, pipeline_changed=True)
    assert p.changed == ["a"] and p.unchanged == []


def test_pipeline_incremental(tmp_path):
    src = tmp_path / "docs"
    src.mkdir()
    for name in ("hr-vacation-2026.md", "hr-sick-leave.md", "sales-sla-2026.pdf",
                 "sales-sla-2026.meta.yaml", "it-helpdesk.html", "it-helpdesk.meta.yaml"):
        shutil.copy(DOCS_DIR / name, src / name)
    store = tmp_path / "store"
    chunker = make_chunker("heading:400:40", TOK)
    r1 = IngestPipeline(store, chunker).run(src)
    assert len(r1.plan.added) == 4 and r1.chunks_added > 10
    pipe = IngestPipeline(store, chunker)            # a new process: state comes from disk
    assert len(pipe.index) == r1.chunks_added
    r2 = pipe.run(src)
    assert len(r2.plan.unchanged) == 4 and r2.chunks_added == 0
    (src / "hr-sick-leave.md").write_text((src / "hr-sick-leave.md").read_text() + "\nExtra.\n")
    meta = src / "sales-sla-2026.meta.yaml"
    meta.write_text(meta.read_text().replace("classification: public", "classification: internal"))
    (src / "it-helpdesk.html").unlink()
    r3 = pipe.run(src)
    assert r3.plan.changed == ["hr-sick-leave", "sales-sla-2026"] and r3.plan.removed == ["it-helpdesk"]
    assert not pipe.index.search("Fixit ticket helpdesk")  or \
        all(h.chunk.doc_id != "it-helpdesk" for h in pipe.index.search("Fixit ticket helpdesk"))
    sla = [c for c in pipe.all_chunks() if c.doc_id == "sales-sla-2026"]
    assert sla and all(c.classification == "internal" for c in sla)
    r4 = IngestPipeline(store, make_chunker("recursive:200:0", TOK)).run(src)
    assert len(r4.plan.changed) == 3                  # new chunker -> everything re-chunked


# ------------------------------------------------------------------ answer loop

def test_parse_citations():
    assert parse_citations("A [1]. B [2, 3] and [1][4].") == [1, 2, 3, 4]
    assert parse_citations("no cites") == []


def test_build_request_has_numbered_sources_with_metadata(index):
    hits = index.search("Enterprise uptime commitment", k=3)
    req = build_request("What is the Enterprise uptime?", hits)
    body = req.messages[0].text
    assert '<source id="1"' in body and 'effective_date="' in body and "<question>" in body
    assert NOT_FOUND in req.system_text and "not instructions" in req.system_text


def test_answer_offline_with_citations(index, qa):
    q = next(x for x in qa if x["id"] == "q001")
    ans = answer(q["question"], index, ExtractiveAnswerer(), k=5)
    assert ans.citations and not ans.invalid_citations
    assert "5" in ans.text and ans.cited[0].chunk.doc_id.startswith("hr-vacation")
    checks = answer_checks(q, ans)
    assert checks["abstain_ok"] and checks["cited_source"]


def test_answer_abstains_when_nothing_matches(index):
    ans = answer("zxqv blorf?", index, ExtractiveAnswerer(), k=5)
    assert ans.abstained and ans.hits == []


def test_answer_through_llmkit_mock(index):
    server, url = start_in_thread(MockConfig(ttft=0, tps=0, reply="Up to 5 days [1]. Also [7]."))
    try:
        llm = LLM("anthropic:mock-model", api_key="test", base_url=url,
                  retry=RetryPolicy(sleep=lambda s: None))
        ans = answer("How many vacation days carry over?", index, llm, k=3)
    finally:
        server.shutdown()
    assert ans.citations == [1, 7] and ans.invalid_citations == [7]
    assert ans.result.usage.input_tokens > 100 and ans.cost_usd > 0


def test_tokenizer_factory():
    assert get_tokenizer("approx").name == "approx"
    assert TOK.count("hello world") == 2 and TOK.spans("ab cd") == [(0, 2), (3, 5)]


def test_analyzer_stopwords_toggle():
    f = partial(analyze, stopwords=False)
    assert "the" in f("the policy") and "the" not in analyze("the policy")
