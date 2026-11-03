"""Exercise 4: cache_key and embed_with_cache in mine.py."""

import numpy as np
import pytest

import mine
from ragkit.embed import cache_key as ref_key


class Counting:
    """An "embedding model" that records every call."""

    def __init__(self):
        self.calls = []

    def __call__(self, texts):
        self.calls.append(list(texts))
        return np.array([[len(t), t.count("a"), 1.0] for t in texts], dtype=np.float32)


def test_cache_key_format_and_reference():
    k = mine.cache_key("st:intfloat/multilingual-e5-small", "document", "חופשה שנתית")
    assert isinstance(k, str) and len(k) == 64 and int(k, 16) >= 0
    assert k == ref_key("st:intfloat/multilingual-e5-small", "document", "חופשה שנתית")


def test_cache_key_separates_fields():
    keys = {mine.cache_key("m", "document", "t"), mine.cache_key("m", "query", "t"),
            mine.cache_key("m2", "document", "t"), mine.cache_key("m", "document", "t "),
            mine.cache_key("m\x1fdocument", "", "t")}
    assert len(keys) == 5


def test_first_call_embeds_distinct_texts_once_in_order():
    fn, cache = Counting(), {}
    out = mine.embed_with_cache(["bb", "a", "bb", "ccc"], fn, cache, "m")
    assert fn.calls == [["bb", "a", "ccc"]]
    assert out.shape == (4, 3) and out.dtype == np.float32
    assert np.array_equal(out[0], out[2]) and out[3][0] == 3
    assert len(cache) == 3


def test_second_call_only_misses_and_none_when_all_cached():
    fn, cache = Counting(), {}
    mine.embed_with_cache(["x", "y"], fn, cache, "m")
    out = mine.embed_with_cache(["y", "z", "x"], fn, cache, "m")
    assert fn.calls[-1] == ["z"]
    assert [v[0] for v in out] == [1, 1, 1]
    n = len(fn.calls)
    mine.embed_with_cache(["z", "x"], fn, cache, "m")
    assert len(fn.calls) == n, "nothing was missing: embed_fn must not be called"


def test_kind_and_model_are_part_of_the_key():
    fn, cache = Counting(), {}
    mine.embed_with_cache(["x"], fn, cache, "m", "document")
    mine.embed_with_cache(["x"], fn, cache, "m", "query")
    mine.embed_with_cache(["x"], fn, cache, "m2", "document")
    assert len(fn.calls) == 3


def test_uses_the_shared_key_so_ragkit_cache_files_work():
    fn, cache = Counting(), {}
    mine.embed_with_cache(["hello"], fn, cache, "m", "query")
    assert ref_key("m", "query", "hello") in cache


def test_wrong_number_of_vectors_raises():
    assert mine.embed_with_cache(["a"], Counting(), {}, "m").shape == (1, 3)
    with pytest.raises(RuntimeError):
        mine.embed_with_cache(["a", "b"], lambda ts: np.zeros((1, 3)), {}, "m")


def test_works_with_ragkit_sqlite_cache(tmp_path):
    from ragkit.embed import SqliteVectorCache
    cache = SqliteVectorCache(tmp_path / "c.sqlite")
    fn = Counting()
    a = mine.embed_with_cache(["one", "two"], fn, cache, "m")
    cache2 = SqliteVectorCache(tmp_path / "c.sqlite")      # reopened, like a new run
    b = mine.embed_with_cache(["two", "one"], fn, cache2, "m")
    assert len(fn.calls) == 1 and np.array_equal(a[0], b[1])
