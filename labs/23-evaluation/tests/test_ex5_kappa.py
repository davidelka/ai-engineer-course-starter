"""Exercise 5: cohen_kappa in mine.py."""

import json
from pathlib import Path

import pytest

import mine
from evalkit import calibration as ref

LABELS = Path(__file__).resolve().parents[1] / "data" / "human_labels.jsonl"


def test_docstring_example():
    assert mine.cohen_kappa(list("gggn"), list("ggnn")) == pytest.approx(0.5)


def test_perfect_and_chance():
    assert mine.cohen_kappa(list("gngn"), list("gngn")) == pytest.approx(1.0)
    # the judge always says "g": agreement 75% but no information -> kappa 0
    assert mine.cohen_kappa(list("gggn"), list("gggg")) == pytest.approx(0.0)
    # systematically opposite -> negative
    assert mine.cohen_kappa(list("gngn"), list("ngng")) < 0


def test_single_label_everywhere():
    assert mine.cohen_kappa(["g"] * 5, ["g"] * 5) == 1.0


def test_three_labels_matches_reference():
    h = ["grounded", "partially_grounded", "not_grounded", "grounded", "grounded", "not_grounded", "partially_grounded"]
    j = ["grounded", "grounded", "not_grounded", "grounded", "partially_grounded", "not_grounded", "not_grounded"]
    assert mine.cohen_kappa(h, j) == pytest.approx(ref.cohen_kappa(h, j))


def test_on_the_lab_labels():
    """The heuristic judge vs the 30 human labels of data/human_labels.jsonl."""
    from evalkit import HeuristicJudgeLLM, Judge, binary_groundedness
    rows = [json.loads(x) for x in LABELS.read_text(encoding="utf-8").splitlines() if x.strip()]
    judge = Judge(HeuristicJudgeLLM())
    human = [r["human"] for r in rows]
    got = [binary_groundedness(judge.groundedness(r["question"], r["answer"], r["contexts"]).label) for r in rows]
    assert mine.cohen_kappa(human, got) == pytest.approx(ref.cohen_kappa(human, got))


def test_errors():
    with pytest.raises(ValueError):
        mine.cohen_kappa(["g"], ["g", "n"])
    with pytest.raises(ValueError):
        mine.cohen_kappa([], [])
