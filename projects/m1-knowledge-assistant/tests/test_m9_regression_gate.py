"""M9: the regression gate. The whole assistant (your mine.py functions where implemented, the
references elsewhere) on the golden set, offline and free. If a change to the prompt, the
retrieval, the packing or the router makes a number drop below its floor, this test fails.

Floors are set a little below what the reference reaches OFFLINE (fake embedder + extractive
answerer). They guard the plumbing and the retrieval, not the quality of a model. With a recorded
live run (data/recorded/*.jsonl from `eval --mode live --record`) the last test replays the real
Haiku answers for free and checks the live floors too.
"""

import json
from pathlib import Path

import pytest

from acmeqa.assistant import Assistant
from acmeqa.config import PROJECT, Settings
from acmeqa.evaluate import evaluate

OFFLINE_FLOORS = {"answer_ok": 0.45, "context_recall": 0.80, "abstain_ok": 0.70}
LIVE_FLOORS = {"answer_ok": 0.60, "context_recall": 0.80, "abstain_ok": 0.80}


@pytest.fixture(scope="module")
def report(tmp_path_factory):
    s = Settings(index_dir=tmp_path_factory.mktemp("index"))
    a = Assistant(s, tracing=False)
    return evaluate(a, judge=True)


def test_answers_gate(report):
    m = report["answers"]["ALL"]
    for k, floor in OFFLINE_FLOORS.items():
        assert m[k] >= floor, f"{k}: {m[k]:.3f} < {floor}"
    assert m["invalid_citations"] == 0
    assert m["stale_cited"] <= 2
    assert report["answers"]["version_conflict"]["context_recall"] >= 0.75


def test_router_gate(report):
    r = report["router"]
    assert r["golden_to_docs"] >= 74, r["golden_misrouted"]
    assert r["data_to_data"] == r["data_n"]
    assert r["execution_accuracy"] == 1.0          # offline plans are the gold plans: plumbing check
    assert r["denied_leaks"] == 0


def test_acl_gate(report):
    for role, m in report["acl"].items():
        assert m["leaks"] == 0, role
    assert report["acl"]["contractor"]["visible_docs"] == 4
    assert report["acl"]["security"]["visible_docs"] == 55


def test_versions_reduce_stale(report):
    by = {st["stage"]: st for st in report["ablation"]}
    assert by["+ versions"]["stale5"] <= 0.25 < by["hybrid (RRF)"]["stale5"]


RECORDED = sorted((PROJECT / "data" / "recorded").glob("*.meta.json"))


@pytest.mark.skipif(not RECORDED, reason="no recorded live run (python -m acmeqa --mode live eval --record)")
def test_recorded_live_gate(tmp_path_factory):
    meta = json.loads(RECORDED[-1].read_text())
    if not meta["embedder"].startswith(("fake", "openai")):
        pytest.importorskip("sentence_transformers")
    s = Settings(embedder=meta["embedder"], k=meta["k"], rerank=meta.get("rerank", ""),
                 version_mode=meta.get("version_mode", "retrieved"),
                 replay_file=Path(str(RECORDED[-1]).replace(".meta.json", ".jsonl")))
    a = Assistant(s, tracing=False)
    rep = evaluate(a, judge=False, parts=("answers",))
    misses = a.llm.misses if hasattr(a.llm, "misses") else 0
    assert misses <= 0.1 * rep["n_questions"], f"{misses} answers not recorded: record again"
    m = rep["answers"]["ALL"]
    for k, floor in LIVE_FLOORS.items():
        assert m[k] >= floor, f"{k}: {m[k]:.3f} < {floor}"
    assert m["invalid_citations"] <= 2
