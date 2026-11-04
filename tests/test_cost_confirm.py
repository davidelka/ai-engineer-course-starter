"""Live scripts ask before spending (lessons 1 and 4), and token counts say which tokenizer made them."""

import io

import pytest

from ctxkit import confirm as C
from ctxkit.tokens import count_tokens, tokenizer_name
from promptlab.__main__ import confirm_cost, plan_cost
from promptlab.runner import load_experiment


def test_tokenizer_name_is_honest():
    name = tokenizer_name()
    assert name == "o200k_base" or name.startswith("estimate: chars/4")
    assert count_tokens("hello world") >= 1


def test_promptlab_plan_counts_calls_and_prices_local_models_free():
    exp = load_experiment("labs/01-prompting/experiments/ex2_temperature.yaml")
    rows, calls, usd, unknown = plan_cost(exp)
    assert calls == sum(n for _, _, n, _ in rows)
    assert all(u == 0 for name, model, _, u in rows if model.startswith("ollama:"))
    assert usd > 0  # the Haiku variants cost something


def test_promptlab_refuses_without_an_answer(monkeypatch, capsys):
    exp = load_experiment("labs/01-prompting/experiments/ex3_effort.yaml")
    monkeypatch.setattr("sys.stdin", io.StringIO(""))  # EOF, as in a non-interactive run
    assert confirm_cost(exp, yes=False, max_cost=10) is False
    assert confirm_cost(exp, yes=True, max_cost=10) is True
    assert confirm_cost(exp, yes=True, max_cost=0.0001) is False  # over the cap even with --yes
    assert "Refusing" in capsys.readouterr().out


def test_ctxkit_confirm_exits_over_the_cap_and_on_no(monkeypatch):
    with pytest.raises(SystemExit):
        C.confirm_paid("x", 1.0, yes=True, max_cost=0.5)
    monkeypatch.setattr("sys.stdin", io.StringIO("n\n"))
    with pytest.raises(SystemExit):
        C.confirm_paid("x", 0.01, yes=False, max_cost=0.5)
    C.confirm_paid("x", 0.01, yes=True, max_cost=0.5)  # returns
    C.confirm_paid("x", 99, yes=False, max_cost=0.5, paid=False)  # free: no question, no cap


def test_price_lookup():
    assert C.price_for("fake") is None
    assert C.price_for("anthropic:claude-haiku-5-5") is not None
    assert C.usd(C.price_for("anthropic:claude-haiku-5-5"), 1_000_000, 0) > 0
