"""ragkit.diagnose (lesson 13): taxonomy, classifier, stage-wise metrics, claim checking, runs."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from ragkit import diagnose as D
from ragkit.diagnose import Case

LAB = Path(__file__).resolve().parent.parent / "labs" / "13-rag-diagnostics"


def rows(name):
    return [json.loads(x) for x in (LAB / "fixtures" / name).read_text(encoding="utf-8").splitlines() if x.strip()]


# ------------------------------------------------------------------ taxonomy
def test_every_stage_has_a_fix_and_a_group():
    for s in D.STAGES:
        assert s in D.FIXES and D.FIXES[s].action and D.FIXES[s].lesson
        assert D.STAGE_GROUP[s] in ("ingestion", "retrieval", "generation")
    assert D.ALL_LABELS[0] == "ok" and len(set(D.ALL_LABELS)) == len(D.ALL_LABELS)


# ------------------------------------------------------------------ classifier
@pytest.mark.parametrize("row", rows("cases.jsonl"), ids=lambda r: r["name"])
def test_constructed_cases(row):
    d = D.classify(Case(**row["case"]))
    assert d.stage == row["expected"], row["why"]
    assert d.path and d.path[0].startswith("outcome passed?")
    if d.stage != "ok":
        assert d.fix is not None


def test_traces_fixture_labels():
    want = {"T1": "extraction_lost", "T2": "chunk_split", "T3": "ranked_low", "T4": "false_refusal",
            "T5": "lost_in_middle", "T6": "hallucination"}
    got = {t["trace_id"]: D.classify(D.case_from_trace(t)).stage for t in rows("traces.jsonl")}
    assert got == want


def test_flags_keep_downstream_problems():
    c = Case(source_ids=["a"], quote_status=["split"], candidates=["a"], context=["a"], cited=["old"],
             stale_ids=["old"], fact_coverage=0.0, grounded=False)
    d = D.classify(c)
    assert d.stage == "chunk_split"
    assert {"stale_cited", "ungrounded", "facts_missing", "source_not_cited"} <= set(d.flags)


def test_lost_in_middle_rule():
    c = Case(source_ids=["a"], context=["x", "a", "y"], evidence_positions=[2], context_tokens=5000)
    assert D.is_lost_in_middle(c)
    assert not D.is_lost_in_middle(replace(c, context_tokens=100))
    assert not D.is_lost_in_middle(replace(c, evidence_positions=[1, 2]))
    assert D.is_lost_in_middle(replace(c, context_tokens=3000), long_context=2000)


# ------------------------------------------------------------------ metrics
def test_metrics():
    assert D.context_recall(["A  b."], ["x a b. y"]) == 1.0
    assert D.context_recall([], ["x"]) is None
    assert D.context_precision([True, False, True]) == pytest.approx((1 + 2 / 3) / 2)
    assert D.context_precision([False, False]) == 0.0 and D.context_precision([]) is None
    assert D.simple_precision([True, False, True, False]) == 0.5
    assert D.citation_precision([1, 3, 1, 9], {1, 2}) == pytest.approx(1 / 3)
    assert D.citation_precision([], {1}) is None
    assert D.citation_recall([1], [{1}, {2}, set()]) == pytest.approx(1 / 3)
    assert D.citation_recall([1], []) is None
    assert D.quote_locations(["b c"], ["a b c", "c", "B  C"]) == [{1, 3}]
    assert D.relevance_from_quotes(["b c"], ["a b c", "c"]) == [True, False]


def test_trace_metrics_on_fixture():
    t = rows("traces.jsonl")[2]                       # T3, q040: the catalog never reached the prompt
    m = D.trace_metrics(t)
    assert m["context_recall"] == 0.5
    assert m["citation_recall"] == 0.5
    assert m["context_precision"] == 1.0              # the one relevant chunk is first: AP = 1.0


# ------------------------------------------------------------------ claims
def test_split_claims_and_heuristic_verdicts():
    cl = D.split_claims("Up to 5 days carry over [1]. They expire on March 31 [1].\n| Team | $12 | 300 |")
    assert cl == ["Up to 5 days carry over", "They expire on March 31", "Team, $12, 300"]
    ctx = ["- Passwords must be at least 14 characters long.\n- There is no forced periodic rotation."]
    assert D.heuristic_verdict("Passwords must be at least 14 characters long", ctx)[0] == "supported"
    assert D.heuristic_verdict("Passwords must be at least 12 characters long", ctx)[0] == "contradicted"
    assert D.heuristic_verdict("There is forced periodic rotation", ctx)[0] == "contradicted"
    assert D.heuristic_verdict("Laptops are replaced every 3 years", ctx)[0] == "not_found"


def test_check_claims_offline_and_evidence_check():
    llm = D.heuristic_judge_llm()
    ctx = ["- Up to 5 unused days may be carried over. Carried-over days expire on March 31."]
    rep = D.check_claims("Up to 5 unused days may be carried over [1]. Unused days can be sold back for cash [1].",
                         ctx, llm)
    assert rep.label == "partially_grounded" and rep.score == 0.5
    assert rep.claims[0].evidence_verified is True
    assert rep.cost_usd > 0
    assert D.check_claims("not in the documents", ctx, llm).refusal
    assert D.evidence_in_context("carried  over.", ctx) and not D.evidence_in_context("sold back", ctx)
    assert not D.evidence_in_context(None, ctx) and not D.evidence_in_context("  ", ctx)


def test_claim_result_needs_verified_evidence():
    assert not D.ClaimResult("x", "supported", "e", 1, False).supported
    assert D.ClaimResult("x", "supported", "e", 1, None).supported
    rep = D.GroundednessReport(claims=[D.ClaimResult("x", "contradicted")])
    assert rep.label == "not_grounded" and rep.grounded is False
    assert D.GroundednessReport(error="boom").label is None


def test_nli_checker_with_a_fake_model():
    def predict(premise, hypothesis):
        if hypothesis in premise:
            return {"entailment": 0.9, "neutral": 0.05, "contradiction": 0.05}
        if "not" in hypothesis:
            return {"entailment": 0.05, "neutral": 0.15, "contradiction": 0.8}
        return {"entailment": 0.1, "neutral": 0.8, "contradiction": 0.1}
    nli = D.NLIChecker(predict=predict)
    rep = nli.check(["5 days", "not 5 days", "cash"], ["Up to 5 days carry over.", "Other text."])
    assert [c.verdict for c in rep.claims] == ["supported", "contradicted", "not_found"]
    assert rep.claims[0].source == 1


# ------------------------------------------------------------------ full run (offline)
@pytest.fixture(scope="module")
def baseline_run():
    from ragkit.acme import acme_documents, acme_qa
    from ragkit.chunking import make_chunker
    from ragkit.fake import ExtractiveAnswerer
    from ragkit.retrieval import BM25Index
    qa = acme_qa()
    docs = acme_documents()
    cs = make_chunker("heading:400:40:150", "approx").split_all(docs)
    bm = BM25Index()
    bm.add(cs)
    traces = D.run_diagnosis(qa, bm, ExtractiveAnswerer(), coverage=D.quote_status_map(docs, cs, qa),
                             judge_llm=D.heuristic_judge_llm())
    return traces, [D.classify(D.case_from_trace(t)) for t in traces]


def test_offline_baseline_breakdown(baseline_run):
    traces, diags = baseline_run
    assert len(traces) == 79
    t = traces[0]
    assert {"candidates", "context", "quote_locations", "fact_coverage", "groundedness"} <= set(t)
    assert [c["doc"] for c in t["context"]] == t["candidates"][:5]
    by = D.breakdown(diags, by="type")
    assert sum(by["ALL"].values()) == 79
    # numbers measured when the lesson was written (offline: BM25 + extractive answerer + lexical judge)
    assert by["ALL"]["ok"] == 36
    assert by["ALL"]["stale_version"] == 6 and by["ALL"]["failed_to_refuse"] == 7
    assert by["unanswerable"]["failed_to_refuse"] == 7
    f = D.funnel(diags)
    assert f[0] == ("in corpus", 69, 0) and f[-1][0] == "correct"
    assert sum(drop for _, _, drop in f) + f[-1][1] == 69
    txt = D.format_breakdown(diags, "baseline") + D.format_funnel(diags)
    assert "by question type" in txt and "funnel" in txt


def test_traces_roundtrip_and_evalkit_run(tmp_path, baseline_run):
    traces, diags = baseline_run
    p = tmp_path / "t.jsonl"
    D.save_traces(traces, p)
    back = D.load_traces(p)
    assert [D.classify(D.case_from_trace(t)).stage for t in back] == [d.stage for d in diags]
    from evalkit.dataset import acme_golden
    from evalkit.gates import NoSignificantDrop, Threshold, check_gates
    run = D.to_evalkit_run(traces, diags, "baseline")
    assert run.mean("answer_ok") == pytest.approx(36 / 79)
    assert run.mean("stage:stale_version") == pytest.approx(6 / 79)
    res = check_gates(run, acme_golden(), [Threshold("answer_ok", 0.4), NoSignificantDrop("answer_ok")], baseline=run)
    assert all(r.passed for r in res)
