"""Exercise 2: l2_normalize and cosine_top_k in mine.py."""

import numpy as np
import pytest

import mine
from ragkit.embed import HashingEmbedder
from ragkit.vectors import cosine_top_k as ref_top_k


def test_normalize_basic():
    out = mine.l2_normalize([3, 4])
    assert out.shape == (1, 2) and out.dtype == np.float32
    assert np.allclose(out, [[0.6, 0.8]])


def test_normalize_rows_and_zero_row():
    x = np.array([[3.0, 4.0], [0.0, 0.0], [0.0, -2.0]])
    out = mine.l2_normalize(x)
    assert np.allclose(out, [[0.6, 0.8], [0, 0], [0, -1]])
    assert not np.isnan(out).any()
    assert np.allclose(x, [[3, 4], [0, 0], [0, -2]]), "the input must not be modified"


def test_normalize_many_rows_have_unit_length():
    x = np.random.default_rng(0).normal(size=(100, 384))
    assert np.allclose(np.linalg.norm(mine.l2_normalize(x), axis=1), 1.0, atol=1e-5)


def test_top_k_ignores_length():
    idx, sc = mine.cosine_top_k([1, 0], np.array([[10, 0], [0.6, 0.8], [0, 1]], dtype=float), 2)
    assert list(idx) == [0, 1]
    assert np.allclose(sc, [1.0, 0.6], atol=1e-6)


def test_top_k_ties_lower_index_first():
    m = np.array([[1, 0], [0, 1], [1, 0], [2, 0]], dtype=float)
    idx, _ = mine.cosine_top_k([1, 0], m, 3)
    assert list(idx) == [0, 2, 3]


def test_top_k_bounds():
    m = np.eye(3)
    idx, sc = mine.cosine_top_k([1, 0, 0], m, 10)
    assert len(idx) == len(sc) == 3
    idx, sc = mine.cosine_top_k([1, 0, 0], np.zeros((0, 3)), 5)
    assert len(idx) == 0 and len(sc) == 0


def test_top_k_matches_reference_on_random_data():
    rng = np.random.default_rng(42)
    m = rng.normal(size=(2000, 64))
    for _ in range(5):
        q = rng.normal(size=64)
        a_idx, a_sc = mine.cosine_top_k(q, m, 10)
        b_idx, b_sc = ref_top_k(q, m, 10)
        assert list(a_idx) == list(b_idx)
        assert np.allclose(a_sc, b_sc, atol=1e-5)


def test_top_k_on_acme_chunks(chunks):
    """Embed the real chunks with the offline hashing embedder and search like a retriever."""
    emb = HashingEmbedder(256)
    m = emb.embed_documents([c.context_text() for c in chunks])
    q = emb.embed_query("How many unused vacation days can be carried over?")
    idx, sc = mine.cosine_top_k(q, m, 5)
    assert [chunks[i].doc_id for i in idx] == [chunks[i].doc_id for i in ref_top_k(q, m, 5)[0]]
    assert any(chunks[i].doc_id.startswith("hr-vacation") for i in idx)
    assert sc[0] == pytest.approx(float(m[idx[0]] @ q), abs=1e-5)
