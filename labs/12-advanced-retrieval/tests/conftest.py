import sys
from pathlib import Path

import pytest

LAB = Path(__file__).resolve().parent.parent
ROOT = LAB.parents[1]
sys.path[:0] = [str(LAB), str(ROOT)]  # so tests can `import mine` and `ragkit`

from ragkit.acme import acme_chunks, acme_qa  # noqa: E402


@pytest.fixture(scope="session")
def qa():
    return acme_qa()


@pytest.fixture(scope="session")
def chunks():
    """The same chunks the lab scripts use (lesson 9's baseline chunker)."""
    from ragkit.chunking import make_chunker
    return acme_chunks(make_chunker("heading:400:40:150", "approx"))


@pytest.fixture(scope="session")
def bm25(chunks):
    from ragkit.retrieval import BM25Index
    idx = BM25Index()
    idx.add(chunks)
    return idx


@pytest.fixture(scope="session")
def dense(chunks):
    """Dense retriever with the FAKE (hashing) embedder: offline, lexical, not semantic."""
    pytest.importorskip("numpy")
    from ragkit.dense import DenseRetriever
    from ragkit.embed import make_embedder
    d = DenseRetriever(make_embedder("fake"))
    d.add(chunks)
    return d
