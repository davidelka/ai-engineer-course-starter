"""M9: the regression gate. The whole system (your mine.py functions where implemented, the
references elsewhere) on the labeled set, offline and free. If a change to the prompt, the
preferences or the code makes any of these numbers drop below its floor, this test fails.

The floors are set a little below what the reference reaches with the HEURISTIC extractor
(see README, milestone 9). With a recording of a real model (data/recorded/*.jsonl) the
second test checks the LLM floors too.
"""

from pathlib import Path

import pytest

from jobagent.__main__ import pick_hooks
from jobagent.evaluate import evaluate_digests, evaluate_extractor, load_posts
from jobagent.extract import HeuristicExtractor, ReplayExtractor

POSTS = load_posts()
HOOKS = pick_hooks(reference=False)

HEURISTIC_FLOORS = {"title": 0.85, "location": 0.90, "work_mode": 0.90, "years_required": 0.85,
                    "primary_category": 0.90, "apply": 0.90}
LLM_FLOORS = {"title": 0.85, "company": 0.85, "location": 0.90, "work_mode": 0.85, "seniority": 0.85,
              "years_required": 0.85, "primary_category": 0.85, "hardware_oriented": 0.85, "apply": 0.90}


def test_dataset_shape():
    assert 60 <= len(POSTS) <= 80
    tags = {t for p in POSTS for t in p["tags"]}
    assert {"he", "en", "multi", "injection", "dup", "noise", "airtable"} <= tags


def test_heuristic_gate():
    r = evaluate_extractor(HeuristicExtractor(), POSTS, scorer=HOOKS.score_job)
    for f, floor in HEURISTIC_FLOORS.items():
        assert r.field_accuracy[f] >= floor, f"{f}: {r.field_accuracy[f]:.3f} < {floor}"
    assert r.relevance_gold_facts["match"]["precision"] >= 0.95      # the rules themselves
    assert r.relevance_gold_facts["match"]["recall"] >= 0.95
    assert r.relevance_predicted["match"]["recall"] >= 0.85          # end to end
    assert r.relevance_predicted["shown"]["recall"] >= 0.85
    assert r.injection["precision"] >= 0.99                          # no false alarms on this set


def test_digest_gate():
    d = evaluate_digests(HeuristicExtractor, POSTS, hooks=HOOKS)
    assert d["groups_delivered_twice"] == 0
    assert d["rerun_skipped"] is True
    assert all(s["shown_recall"] >= 0.85 for s in d["slots"].values())
    assert all(s["error"] is None for s in d["slots"].values())


RECORDED = sorted((Path(__file__).resolve().parent.parent / "data" / "recorded").glob("*.jsonl"))


@pytest.mark.skipif(not RECORDED, reason="no recorded LLM run (python -m jobagent eval --extractor llm --record)")
def test_recorded_llm_gate():
    r = evaluate_extractor(ReplayExtractor(RECORDED[-1]), POSTS, scorer=HOOKS.score_job)
    assert not [e for e in r.errors if "not_recorded" in e], "recording is older than the dataset: record again"
    for f, floor in LLM_FLOORS.items():
        assert r.field_accuracy[f] >= floor, f"{f}: {r.field_accuracy[f]:.3f} < {floor}"
    assert r.relevance_predicted["match"]["recall"] >= 0.90
