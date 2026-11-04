"""Offline tests: a fake provider stands in for the APIs, so these run free and fast."""

import json
import random
from pathlib import Path

import pytest

from promptlab.providers import CallSpec, Result
from promptlab.runner import load_experiment, load_jsonl, predict_label, render, run_experiment, summarize

ROOT = Path(__file__).resolve().parent.parent
EXP = ROOT / "labs" / "01-prompting" / "experiments"


def test_render_leaves_unknown_braces():
    assert render('{"a": 1} {name}', {"name": "Dana"}) == '{"a": 1} Dana'


@pytest.mark.parametrize(
    "text,expected",
    [
        ("needs_security", "needs_security"),
        ("Label: needs_manager. Not auto_approve.", "needs_manager"),
        ("I cannot decide", None),
    ],
)
def test_predict_label_first_hit(text, expected):
    assert predict_label(text, ["auto_approve", "needs_manager", "needs_security"]) == expected


@pytest.mark.parametrize("name", sorted(p.name for p in EXP.glob("*.yaml")))
def test_every_experiment_loads(name):
    exp = load_experiment(EXP / name)
    assert exp.cases and exp.variants
    for v in exp.variants:
        assert "{examples}" not in v.system
        assert "{policy}" not in v.system and "{documents}" not in v.user_template
        assert v.params["provider"] in {"anthropic", "openai", "gemini", "ollama"}


def test_fewshot_variants_differ_only_in_examples():
    exp = load_experiment(EXP / "ex6_fewshot.yaml")
    by = {v.name: v for v in exp.variants}
    assert "<example>" not in by["zero-shot"].system
    assert by["balanced-3"].system.count("<example>") == 3
    assert by["balanced-6"].system.count("<example>") == 6
    # the first 3 balanced examples cover all three labels
    first3 = load_jsonl(ROOT / "data/acme/saas_examples_balanced.jsonl")[:3]
    assert {e["label"] for e in first3} == {"auto_approve", "needs_manager", "needs_security"}
    # no example request leaks into the test set
    test_reqs = {c["request"] for c in exp.cases}
    for f in ("saas_examples_balanced.jsonl", "saas_examples_unbalanced.jsonl"):
        assert not test_reqs & {e["request"] for e in load_jsonl(ROOT / "data/acme" / f)}


def fake_call(provider: str, spec: CallSpec) -> Result:
    if spec.temperature == 0.2:
        return Result(error="BadRequestError: temperature is not supported")
    rng = random.Random(hash((spec.user, spec.temperature)))
    if "<request>" in spec.user:
        label = "needs_security" if "production" in spec.user or "Admin" in spec.user else "auto_approve"
        return Result(text=label, in_tokens=100, out_tokens=3)
    word = rng.choice(["Oasis", "Dune Cafe", "Mirage"]) if (spec.temperature or 0) > 0 else "Oasis"
    return Result(text=word, in_tokens=20, out_tokens=2, latency_s=0.1)


def test_runner_end_to_end_with_fake_provider(tmp_path):
    exp = load_experiment(EXP / "ex6_fewshot.yaml")
    exp.repeats = 2
    out = run_experiment(exp, tmp_path, only=["zero-shot"], call=fake_call, progress=False)
    rows = load_jsonl(out)
    assert len(rows) == 20 * 2
    s = summarize(rows)[0]
    assert s["errors"] == 0 and 0 < s["pass_rate"] < 1 and s["consistency"] == 1.0


def test_errors_are_recorded_not_raised(tmp_path):
    exp = load_experiment(EXP / "ex2_temperature.yaml")
    exp.repeats = 3
    out = run_experiment(exp, tmp_path, only=["haiku55-t0.2-expect-400", "ollama-t0.0"], call=fake_call, progress=False)
    summary = {s["variant"]: s for s in summarize(load_jsonl(out))}
    assert summary["haiku55-t0.2-expect-400"]["errors"] == 9
    assert "not supported" in summary["haiku55-t0.2-expect-400"]["first_error"]
    assert summary["ollama-t0.0"]["distinct_per_case"] == 1


def test_openai_stop_reason_uses_incomplete_details():
    from types import SimpleNamespace

    from promptlab.providers import _openai_stop_reason

    done = SimpleNamespace(status="completed", incomplete_details=None)
    cut = SimpleNamespace(status="incomplete", incomplete_details=SimpleNamespace(reason="max_output_tokens"))
    bare = SimpleNamespace(status="incomplete", incomplete_details=None)
    assert _openai_stop_reason(done) == "completed"
    assert _openai_stop_reason(cut) == "max_output_tokens"
    assert _openai_stop_reason(bare) == "incomplete"


def test_injection_ladder_adds_one_thing_per_variant():
    exp = load_experiment(EXP / "ex5_injection.yaml")
    by = {v.name: v for v in exp.variants}
    assert list(by) == ["no-delimiters", "tagged-only", "tagged-and-ruled"]
    # tags alone: same system prompt as the baseline, only the user template changes
    assert by["tagged-only"].system == by["no-delimiters"].system
    assert "<documents>" in by["tagged-only"].user_template
    assert "<documents>" not in by["no-delimiters"].user_template
    # the rule: same user template as tagged-only, only the system prompt changes
    assert by["tagged-and-ruled"].user_template == by["tagged-only"].user_template
    assert by["tagged-and-ruled"].system != by["tagged-only"].system
