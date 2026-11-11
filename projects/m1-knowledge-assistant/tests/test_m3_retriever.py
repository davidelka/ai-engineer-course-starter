"""M3: build_retriever (mine.py). A fake IngestJob with marked retrievers, so every layer is visible."""

from types import SimpleNamespace

from mine import build_retriever
from ragkit.rerank import RerankingRetriever
from ragkit.types import Chunk, Hit
from ragkit.versions import VersionAwareRetriever


class Marked:
    """A first-stage retriever that returns fixed hits and remembers what it was asked."""

    def __init__(self, name, hits=()):
        self.name, self.hits, self.calls = name, list(hits), []

    def search(self, query, k=5, where=None):
        self.calls.append({"query": query, "k": k, "where": where})
        return self.hits[:k]


def C(doc, version="", date=""):
    return Chunk(id=f"{doc}#0", doc_id=doc, text=f"text of {doc}", start=0, end=10,
                 meta={"version": version, "effective_date": date, "supersedes": []})


def job(version_mode="retrieved", rerank=None, hits=()):
    s = SimpleNamespace(version_mode=version_mode, rerank=rerank)
    return SimpleNamespace(s=s, bm25=Marked("bm25"), dense=Marked("dense"), index=Marked("hybrid", hits),
                           all_chunks=lambda: [h.chunk for h in hits])


def test_first_stages_are_the_jobs_retrievers():
    j = job()
    assert build_retriever(j, upto="bm25") is j.bm25
    assert build_retriever(j, upto="dense") is j.dense
    assert build_retriever(j, upto="hybrid") is j.index


def test_versions_layer_wraps_the_hybrid():
    j = job()
    r = build_retriever(j, upto="versions")
    assert isinstance(r, VersionAwareRetriever)
    assert r.base is j.index and r.mode == "retrieved" and r.fetch_k == 50


def test_versions_off_returns_the_hybrid():
    j = job(version_mode="off")
    assert build_retriever(j, upto="versions") is j.index
    assert build_retriever(j) is j.index                     # full, no rerank


def test_corpus_mode_gets_a_supersedes_map():
    hits = [Hit(C("hr-vacation-2026"), 1.0, 1), Hit(C("hr-vacation-2024"), 0.9, 2)]
    j = job(version_mode="corpus", hits=hits)
    r = build_retriever(j, upto="versions")
    assert isinstance(r, VersionAwareRetriever) and r.mode == "corpus" and r.superseded_by is not None


def test_full_without_rerank_is_the_versions_layer():
    r = build_retriever(job())
    assert isinstance(r, VersionAwareRetriever)


def test_full_with_rerank_wraps_versions():
    j = job(rerank="fake")
    r = build_retriever(j)
    assert isinstance(r, RerankingRetriever) and r.fetch_k == 30
    assert isinstance(r.base, VersionAwareRetriever) and r.base.base is j.index


def test_settings_argument_wins_over_job_settings():
    j = job(rerank=None)
    other = SimpleNamespace(version_mode="off", rerank="fake")
    r = build_retriever(j, other)
    assert isinstance(r, RerankingRetriever) and r.base is j.index


def test_where_reaches_the_first_stage():
    hits = [Hit(C("a"), 1.0, 1)]
    j = job(hits=hits)
    where = lambda chunk: True  # noqa: E731
    build_retriever(j).search("q", k=5, where=where)
    assert j.index.calls and j.index.calls[-1]["where"] is where      # the ACL runs before ranking
