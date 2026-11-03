"""Exercise 6: two classic "AI coding round" tasks."""

import warnings

import numpy as np
import pytest

from mine import fit_to_budget, top_k_cosine


# ---------------------------------------------------------------- top_k_cosine
M = np.array([[1.0, 0.0], [0.0, 1.0], [1.0, 1.0], [-1.0, 0.0], [2.0, 0.0]])


def test_basic_order_and_types():
    res = top_k_cosine(np.array([1.0, 0.0]), M, 3)
    assert [i for i, _ in res] == [0, 4, 2]          # 0 and 4 tie at 1.0 -> lower index first
    assert res[0][1] == pytest.approx(1.0) and res[2][1] == pytest.approx(1 / np.sqrt(2))
    assert all(type(i) is int and type(s) is float for i, s in res)


def test_k_larger_than_n_and_zero_k():
    assert len(top_k_cosine(np.array([1.0, 0.0]), M, 99)) == 5
    assert top_k_cosine(np.array([1.0, 0.0]), M, 0) == []
    assert top_k_cosine(np.array([1.0, 0.0]), np.zeros((0, 2)), 3) == []


def test_zero_vectors_no_nan_no_warning():
    m = np.array([[0.0, 0.0], [1.0, 0.0]])
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        res = top_k_cosine(np.array([1.0, 0.0]), m, 2)
        assert res == [(1, pytest.approx(1.0)), (0, 0.0)]
        res = top_k_cosine(np.zeros(2), m, 2)
        assert [s for _, s in res] == [0.0, 0.0] and [i for i, _ in res] == [0, 1]


def test_negative_similarity_last():
    res = top_k_cosine(np.array([1.0, 0.0]), M, 5)
    assert res[-1] == (3, pytest.approx(-1.0))


@pytest.mark.parametrize("q,m", [(np.ones(3), M), (np.ones((1, 2)), M), (np.ones(2), np.ones(2))])
def test_shape_errors(q, m):
    with pytest.raises(ValueError):
        top_k_cosine(q, m, 1)


def test_matches_bruteforce_on_random_data():
    rng = np.random.default_rng(0)
    m = rng.normal(size=(500, 32))
    q = rng.normal(size=32)
    sims = m @ q / (np.linalg.norm(m, axis=1) * np.linalg.norm(q))
    expect = list(np.argsort(-sims, kind="stable")[:10])
    assert [i for i, _ in top_k_cosine(q, m, 10)] == expect


# ---------------------------------------------------------------- fit_to_budget
def words(text):  # a predictable counter for tests: 1 token per word
    return len(text.split())


def msg(role, n):
    return {"role": role, "content": " ".join(["w"] * n)}


# cost of each = words + 4
CHAT = [msg("system", 6),      # 10
        msg("user", 16),       # 20
        msg("assistant", 16),  # 20
        msg("user", 6),        # 10
        msg("assistant", 26),  # 30
        msg("user", 6)]        # 10 (current turn)


def test_everything_fits():
    out = fit_to_budget(CHAT, 1000, count=words)
    assert out == CHAT and out is not CHAT and all(a is not b for a, b in zip(out, CHAT))


def test_drops_oldest_first_and_keeps_system():
    out = fit_to_budget(CHAT, 60, count=words)  # system 10 + last 10 + assistant 30 + user 10 = 60
    assert [m["role"] for m in out] == ["system", "user", "assistant", "user"]
    assert out[1] is not CHAT[3] and out[1] == CHAT[3]


def test_starts_with_user_after_trimming():
    out = fit_to_budget(CHAT, 50, count=words)  # system + last + assistant(30) = 50 -> drop that assistant
    assert [m["role"] for m in out] == ["system", "user"]
    assert out[-1] == CHAT[-1]


def test_contiguous_history():
    chat = [msg("user", 6), msg("assistant", 96), msg("user", 1), msg("assistant", 1), msg("user", 1)]
    out = fit_to_budget(chat, 25, count=words)  # 5+5+5 = 15 fits; the 100 one does not -> stop there
    assert len(out) == 3 and out[0] == chat[2]


def test_system_messages_go_first():
    chat = [msg("user", 1), msg("system", 1), msg("user", 1)]
    out = fit_to_budget(chat, 100, count=words)
    assert [m["role"] for m in out] == ["system", "user", "user"]


def test_too_small_budget():
    with pytest.raises(ValueError):
        fit_to_budget(CHAT, 19, count=words)
    with pytest.raises(ValueError):
        fit_to_budget([msg("system", 1)], 100, count=words)


def test_default_counter_and_no_mutation():
    chat = [{"role": "user", "content": "x" * 400}, {"role": "user", "content": "hi"}]
    before = [dict(m) for m in chat]
    out = fit_to_budget(chat, 10)  # approx_tokens("hi") = 1, + 4 overhead = 5; the long one needs 104
    assert out == [{"role": "user", "content": "hi"}]
    assert chat == before
