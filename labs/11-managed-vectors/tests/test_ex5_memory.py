"""Exercise 5: index_ram_bytes in mine.py."""

import math

import pytest

import mine
from ragkit.vectors.sizing import hnsw_ram_bytes


def ref(n, dim, m=16, q=None, orig=None):
    return hnsw_ram_bytes(n, dim, m=m, quantization=q, originals_in_ram=orig)["total_ram"]


def test_docstring_examples():
    assert mine.index_ram_bytes(1_000_000, 384) == pytest.approx(1.536e9 + 1e6 * (132 + 68 / 15))
    assert mine.index_ram_bytes(1_000_000, 384, quantization="binary") == pytest.approx(48e6 + 1e6 * (132 + 68 / 15))


def test_graph_grows_with_m():
    g8 = mine.index_ram_bytes(1000, 0, m=8)
    g32 = mine.index_ram_bytes(1000, 0, m=32)
    assert g8 == pytest.approx(1000 * (68 + 36 / 7))
    assert g32 == pytest.approx(1000 * (260 + 132 / 31))
    assert mine.index_ram_bytes(1000, 0, m=0) == 0


@pytest.mark.parametrize("q", [None, "float32", "float16", "int8", "scalar", "binary"])
@pytest.mark.parametrize("orig", [None, True, False])
def test_matches_reference(q, orig):
    for n, dim, m in [(1_000_000, 384, 16), (10_000_000, 1024, 32), (12345, 1536, 8), (7, 1001, 16)]:
        assert mine.index_ram_bytes(n, dim, m, q, orig) == pytest.approx(ref(n, dim, m, q, orig))


def test_binary_rounds_up_and_unknown_raises():
    assert mine.index_ram_bytes(1, 1001, m=0, quantization="binary") == math.ceil(1001 / 8)
    with pytest.raises(ValueError):
        mine.index_ram_bytes(10, 10, quantization="int4")


def test_the_10m_question():
    """10M chunks x 1024 dims: float32 HNSW needs ~40 GB of RAM; int8 + originals on disk ~11.6 GB."""
    full = mine.index_ram_bytes(10_000_000, 1024)
    sq = mine.index_ram_bytes(10_000_000, 1024, quantization="int8")
    assert 40e9 < full < 43e9
    assert 11e9 < sq < 12e9
