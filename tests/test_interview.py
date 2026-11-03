"""interviewkit (lesson 28): question bank, reference scorer/SM-2/coding tasks, mock interviewer."""

import subprocess
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pytest

from interviewkit import fit_to_budget, grade_from_score, pick_session, score_answer, sm2_review, top_k_cosine
from interviewkit.bank import CATEGORIES, load_bank, validate_question
from interviewkit.interviewer import (CriterionVerdict, grade_answer, project_question, run_interview,
                                      weighted_score)
from interviewkit.rubric import term_in
from llmkit import LLM
from mockllm import MockConfig, start_in_thread

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "labs" / "28-interview-prep"


@pytest.fixture(scope="module")
def _server():
    server, url = start_in_thread(MockConfig())
    yield server, url
    server.shutdown()


@pytest.fixture
def mock(_server):
    server, url = _server
    server.state.cfg = MockConfig(ttft=0, tps=0, seed=1)
    server.state.rng.seed(1)
    server.state.reset()
    return server, url


# ---------------------------------------------------------------- the bank
def test_bank_size_and_coverage():
    bank = load_bank()
    assert len(bank) >= 80
    ids = [q["id"] for q in bank]
    assert len(ids) == len(set(ids))
    for c in CATEGORIES:
        assert sum(q["category"] == c for q in bank) >= 6, c


def test_bank_valid():
    problems = {q["id"]: p for q in load_bank() if (p := validate_question(q))}
    assert not problems


def test_reference_answers_cover_their_rubric():
    low = {q["id"]: score_answer(q["answer"], q)["missing"] for q in load_bank()
           if score_answer(q["answer"], q)["coverage"] < 1.0}
    assert not low


def test_bank_answers_are_plain_text():
    for q in load_bank():
        assert "<b>" not in q["answer"] and q["answer"].strip()


def test_validate_catches_problems():
    q = {"id": "x", "category": "nope", "level": "mid", "q": "?", "answer": "a",
         "rubric": [{"id": "r1", "point": "p", "concepts": [["a"]]}, {"id": "r1", "point": "", "concepts": []}]}
    p = validate_question(q)
    assert any("category" in s for s in p) and any("unique" in s for s in p) and any("needs point" in s for s in p)
    assert validate_question({"id": "y"})[0].startswith("missing")


# ---------------------------------------------------------------- reference implementations
def test_term_matching_rules():
    assert term_in("A RAG pipeline", "rag") and not term_in("drag", "rag")
    assert term_in("והאמבדינג", "אמבדינג") and term_in("20%", "%")
    assert term_in("calibration", "calibrat*") and not term_in("evaluate", "eval")


def test_scorer_and_srs_and_coding_smoke():
    q = {"rubric": [{"id": "r1", "point": "x", "concepts": [["golden set"]], "weight": 1}]}
    assert score_answer("we built a golden set", q)["covered"] == ["r1"]
    s = sm2_review(None, 5, date(2026, 11, 1))
    assert s["interval"] == 1 and s["due"] == "2026-11-02"
    assert grade_from_score(76) == 4
    assert pick_session(["a", "b"], {}, date(2026, 11, 1), new_per_day=1) == ["a"]
    assert top_k_cosine(np.array([1.0, 0.0]), np.eye(2), 1) == [(0, 1.0)]
    msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]
    assert fit_to_budget(msgs, 100) == msgs


# ---------------------------------------------------------------- interviewer over the mock server
@pytest.mark.parametrize("provider", ["anthropic", "openai", "gemini"])
def test_run_interview_offline(mock, provider):
    _, url = mock
    llm = LLM(f"{provider}:mock-model", base_url=url, api_key="mock-key")
    q = next(x for x in load_bank() if x["id"] == "rag-02")
    answers = iter(["first answer about chunking", "second", "third"])
    seen = []
    res = run_interview(llm, q, lambda m: next(answers), max_followups=2,
                        on_message=lambda r, t: seen.append(r))
    # the mock's sample object always says follow_up, so the cap of 2 follow-ups must stop it
    assert [r for r, _ in res.transcript] == ["interviewer", "candidate"] * 3
    assert seen == [r for r, _ in res.transcript]
    assert res.calls == 3 and res.cost_usd > 0
    assert res.score == 0  # the mock grader returns point_id "example", which matches nothing
    assert "score" in res.local and res.to_dict()["question_id"] == "rag-02"


def test_run_interview_english_opening_and_no_followups(mock):
    _, url = mock
    llm = LLM("anthropic:mock-model", base_url=url, api_key="mock-key")
    q = load_bank()[0]
    res = run_interview(llm, q, lambda m: "answer", lang="en", max_followups=0)
    assert [r for r, _ in res.transcript] == ["interviewer", "candidate"]
    assert res.calls == 2  # opening question + grade


def test_weighted_score_ignores_unknown_ids():
    q = {"rubric": [{"id": "r1", "weight": 3}, {"id": "r2", "weight": 1}]}
    v = [CriterionVerdict(point_id="r1", covered=True), CriterionVerdict(point_id="zz", covered=True),
         CriterionVerdict(point_id="r2", covered=False)]
    assert weighted_score(q, v) == (75, ["r1"])


def test_grade_answer_and_project_question(mock):
    _, url = mock
    llm = LLM("anthropic:mock-model", base_url=url, api_key="mock-key")
    pq = project_question("My project: RAG over Acme docs.", "Company Brain")
    assert "Company Brain" in pq["q"] and not validate_question(pq)
    g = grade_answer(llm, pq, "<transcript>CANDIDATE: hi</transcript>")
    assert g.calls == 1 and 0 <= g.score <= 100


# ---------------------------------------------------------------- lab scripts
def test_design_checklist_separates_strong_and_weak():
    import json
    checklist = json.loads((LAB / "system_design" / "checklist.json").read_text(encoding="utf-8"))
    strong = score_answer((LAB / "system_design" / "model_answer.md").read_text(encoding="utf-8"),
                          checklist, min_words=250, max_words=4000)
    weak = score_answer((LAB / "system_design" / "weak_answer.md").read_text(encoding="utf-8"),
                        checklist, min_words=250, max_words=4000)
    assert strong["score"] >= 90 and weak["score"] <= 40
    assert {p["section"] for p in checklist["rubric"]} >= {"requirements", "metrics", "architecture", "eval",
                                                           "failures", "cost_latency", "security"}


def test_design_check_cli_runs():
    out = subprocess.run([sys.executable, str(LAB / "design_check.py"), "check",
                          str(LAB / "system_design" / "model_answer.md"), "--reference"],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    assert "Checklist coverage" in out.stdout


def test_bank_tool_validate_cli():
    out = subprocess.run([sys.executable, str(LAB / "bank_tool.py"), "validate"],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0 and "OK" in out.stdout


def test_drill_session_with_stubs():
    sys.path.insert(0, str(LAB))
    from bank_tool import impl, run_drill
    bank = load_bank()
    states = {}
    done = run_drill(bank, states, date(2026, 11, 1), answer_fn=lambda q: q["answer"],
                     self_grade=lambda q, r, suggested: suggested, fns=impl(True), new_per_day=3, limit=3,
                     category="rag")
    assert [i for i, _ in done] == ["rag-01", "rag-02", "rag-03"]
    assert all(g >= 4 for _, g in done)  # reference answers score high
    assert states["rag-01"]["due"] == "2026-11-02"
