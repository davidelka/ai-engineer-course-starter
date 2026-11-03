"""evalkit (lesson 23): datasets, runner + cache, metrics, judge, calibration, stats, gates, reports."""

import json
import math
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
LAB = ROOT / "labs" / "23-evaluation"

from evalkit import (Dataset, Example, FunctionSystem, HeuristicJudgeLLM, Judge, NoSignificantDrop, OutputCache,  # noqa: E402
                     Run, Threshold, acme_golden, agreement, assert_gates, binary_groundedness, bootstrap_ci,
                     build_report, calibrate, check_gates, citation_scores, cohen_kappa, confusion, contains,
                     exact_match, fact_coverage, fact_covered, hit_at_k, mcnemar_exact, min_detectable_diff, mrr,
                     paired_compare, per_field_accuracy, recall_at_k, regex_match, run_system, sample_size,
                     score_run, to_html, to_markdown, wilson_ci)
from evalkit.rag import PROMPTS, RAG_METRICS, RagSystem, RuleFollowingAnswerer, policy_family, rag_scorer  # noqa: E402


# ------------------------------------------------------------------ fixtures
@pytest.fixture(scope="module")
def golden():
    return acme_golden()


@pytest.fixture(scope="module")
def index():
    from ragkit.acme import acme_chunks
    from ragkit.chunking import make_chunker
    from ragkit.retrieval import BM25Index
    idx = BM25Index()
    idx.add(acme_chunks(make_chunker("heading:400:40:150", "approx")))
    return idx


@pytest.fixture(scope="module")
def v1v2(golden, index):
    runs = {}
    for p in ("v1", "v2"):
        r = run_system(RagSystem(index, RuleFollowingAnswerer(), prompt=p), golden)
        runs[p] = score_run(r, golden, [rag_scorer()])
    return runs


# ------------------------------------------------------------------ dataset
def test_golden_set_shape(golden):
    assert len(golden) == 79
    assert golden.counts() == {"acronym": 8, "hebrew": 11, "multi_hop": 11, "numeric": 9, "single_hop": 19,
                               "unanswerable": 10, "version_conflict": 11}
    q1 = golden["q001"]
    assert q1.type == "version_conflict" and q1.expected["stale_ids"] == ["hr-vacation-2024"]
    assert golden["q070"].expected["answerable"] is False


def test_version_is_content_hash(golden):
    v = golden.version
    assert v == acme_golden().version and len(v) == 8
    edited = Dataset(golden.name, [Example(**{**e.to_dict()}) for e in golden])
    edited.examples[0].expected["answer"] += " (edited)"
    assert edited.version != v
    meta_only = Dataset(golden.name, [Example(**{**e.to_dict()}) for e in golden])
    meta_only.examples[0].meta["note"] = "meta is not part of the version"
    assert meta_only.version == v


def test_filter_and_split(golden):
    vc = golden.filter(type="version_conflict")
    assert len(vc) == 11 and vc.version != golden.version
    assert len(golden.filter(tag="stale")) >= 11
    s = golden.split({"dev": 0.5, "test": 0.5})
    assert len(s["dev"]) + len(s["test"]) == 79
    assert not set(s["dev"].ids()) & set(s["test"].ids())
    for t, n in golden.counts().items():               # stratified: each type split about evenly
        assert abs(s["dev"].counts().get(t, 0) - n / 2) <= 1
    assert golden.split({"dev": 0.5, "test": 0.5})["dev"].ids() == s["dev"].ids()   # deterministic
    grown = Dataset(golden.name, golden.examples + [Example("q999", {"question": "new"}, tags=["type:numeric"])])
    s2 = grown.split({"dev": 0.5, "test": 0.5})
    moved = [i for i in s["test"].ids() if i in s2["dev"].ids()]
    assert len(moved) <= 1                              # adding a question barely moves old ones


def test_save_load_roundtrip(tmp_path, golden):
    p = golden.save(tmp_path / "g.jsonl")
    back = Dataset.load(p)
    assert back.version == golden.version and back.name == golden.name
    lines = p.read_text(encoding="utf-8").splitlines()
    lines[1] = lines[1].replace("carry over", "carry")     # hand edit without re-saving
    p.write_text("\n".join(lines), encoding="utf-8")
    with pytest.raises(ValueError, match="edited by hand"):
        Dataset.load(p)


# ------------------------------------------------------------------ runner
def test_runner_cache_and_errors(tmp_path):
    calls = []

    def fn(inp):
        calls.append(inp["x"])
        if inp["x"] == 3:
            raise RuntimeError("boom")
        return {"answer": str(inp["x"] * 2), "cost_usd": 0.01}

    ds = Dataset("toy", [Example(f"e{i}", {"x": i}) for i in range(5)])
    cache = OutputCache(tmp_path / "c")
    r1 = run_system(FunctionSystem("toy", "v1", fn), ds, cache=cache)
    assert len(r1.errors) == 1 and "boom" in r1.errors[0].error
    assert r1.cost_usd == pytest.approx(0.04)
    r2 = run_system(FunctionSystem("toy", "v1", fn), ds, cache=cache)
    assert r2.cached_count == 4 and r2.cost_usd == 0.0     # failures are not cached: e3 runs again
    assert calls.count(3) == 2 and calls.count(1) == 1
    r3 = run_system(FunctionSystem("toy", "v2", fn), ds, cache=cache)
    assert r3.cached_count == 0                             # a new version never gets old outputs
    score_run(r1, ds, [lambda ex, out: {"ok": float(out["answer"] == str(ex.input["x"] * 2))}])
    assert r1.mean("ok") == 1.0 and r1.by_id()["e3"].scores == {"error": 1.0}
    p = r1.save(tmp_path / "run.jsonl")
    back = Run.load(p)
    assert back.system_version == "v1" and back.by_id()["e1"].scores["ok"] == 1.0


def test_rag_system_version_and_output(golden, index):
    s = RagSystem(index, RuleFollowingAnswerer(), prompt="v1", k=5)
    assert s.version.startswith("rag|v1:") and "|k=5|" in s.version
    assert RagSystem(index, RuleFollowingAnswerer(), prompt="v2").version != s.version
    out = s(golden["q001"].input)
    assert set(out) >= {"answer", "cited_docs", "retrieved_docs", "contexts", "abstained", "cost_usd"}
    assert out["contexts"][0]["doc"] == out["retrieved_docs"][0]


# ------------------------------------------------------------------ metrics
def test_string_and_field_metrics():
    assert exact_match(" Up to 5 DAYS ", "up to 5 days")
    assert contains("It is 3,000 NIS.", "3000 nis")
    assert regex_match("route: needs_security", r"needs_(security|manager)")
    acc = per_field_accuracy({"tool": "Figma", "route": "needs_manager", "level": "read"},
                             {"tool": ["Figma", "Google Workspace"], "route": "needs_security", "level": "read"})
    assert acc == {"tool": True, "route": False, "level": True}


def test_retrieval_metrics():
    ret = ["a", "b", "c", "d"]
    assert recall_at_k(ret, ["c", "x"], 3) == 0.5 and recall_at_k(ret, ["c", "x"], 2) == 0.0
    assert hit_at_k(ret, ["c"], 3) == 1.0
    assert mrr(ret, ["c", "d"]) == pytest.approx(1 / 3) and mrr(ret, ["z"]) == 0.0
    assert recall_at_k(ret, [], 5) is None and mrr(ret, []) is None


def test_fact_coverage():
    facts = ["up to 5 days can be carried over", "carried-over days expire on March 31"]
    assert fact_coverage("Up to 5 unused days may be carried over. Carried-over days expire on March 31. [1]", facts) == 1.0
    assert fact_coverage("Up to 3 days, until February 28.", facts) == 0.0
    assert fact_coverage("x", []) is None
    assert fact_covered("לחברה יש 18 מקומות חניה בחניון", "18 מקומות")
    assert fact_covered("The total overcharge was €48,900", "€48,900 in total")
    assert fact_covered("SMS codes are accepted", "SMS codes are no longer accepted")   # documented blind spot


def test_citation_scores():
    assert citation_scores(["a", "old"], ["a"], ["old"]) == {"precision": 0.5, "recall": 1.0, "stale": True}
    assert citation_scores([], []) == {"precision": 1.0, "recall": 1.0, "stale": False}
    assert citation_scores(["a"], []) == {"precision": 0.0, "recall": 0.0, "stale": False}


# ------------------------------------------------------------------ stats
def test_bootstrap_ci_reasonable():
    vals = [1.0] * 40 + [0.0] * 40
    ci = bootstrap_ci(vals, seed=1)
    w = wilson_ci(40, 80)
    assert ci.low < 0.5 < ci.high
    assert abs(ci.low - w.low) < 0.03 and abs(ci.high - w.high) < 0.03     # agrees with the closed form
    assert bootstrap_ci(vals, seed=1).low == ci.low                       # reproducible


def test_paired_beats_unpaired():
    """The same +5 points: invisible with two separate CIs, clear with pairing."""
    rng = random.Random(0)
    a = [float(rng.random() < 0.6) for _ in range(200)]
    b = list(a)
    flipped = [i for i, x in enumerate(a) if x == 0.0][:10]
    for i in flipped:
        b[i] = 1.0
    ca, cb = bootstrap_ci(a), bootstrap_ci(b)
    assert not (ca.high < cb.low)                    # the separate intervals overlap
    pr = paired_compare(a, b)
    assert pr.significant and pr.diff == pytest.approx(0.05) and pr.wins == 10 and pr.losses == 0
    assert mcnemar_exact([x == 1 for x in a], [x == 1 for x in b]) == pytest.approx(2 / 2 ** 10)


def test_mcnemar_and_power():
    assert mcnemar_exact([True] * 5, [True] * 5) == 1.0
    assert mcnemar_exact([True, True, True, False, False], [False, False, False, False, False]) == pytest.approx(0.25)
    mdd = min_detectable_diff(79, 0.5)
    assert 0.2 < mdd < 0.25
    assert min_detectable_diff(79, 0.5, paired=True, discordant=0.1) < mdd
    n = sample_size(0.05, 0.7)
    assert min_detectable_diff(n, 0.7) <= 0.05 < min_detectable_diff(n - 50, 0.7)
    with pytest.raises(ValueError):
        paired_compare([1.0], [1.0, 0.0])


# ------------------------------------------------------------------ calibration
def test_kappa_and_confusion():
    h, j = list("gggn"), list("ggnn")
    assert agreement(h, j) == 0.75 and cohen_kappa(h, j) == pytest.approx(0.5)
    assert cohen_kappa(list("gggn"), list("gggg")) == pytest.approx(0.0)
    assert cohen_kappa(["g"] * 3, ["g"] * 3) == 1.0
    c = confusion(h, j)
    assert c[("g", "n")] == 1 and c[("n", "n")] == 1 and sum(c.values()) == 4
    rep = calibrate(h, j, positive="g")
    assert rep.false_fail == 1 and rep.false_pass == 0 and rep.precision == 1.0


def test_lab_human_labels_file():
    rows = [json.loads(x) for x in (LAB / "data" / "human_labels.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    assert len(rows) == 30
    assert {r["human"] for r in rows} == {"grounded", "not_grounded"}
    assert all(r["contexts"] and r["answer"] and r["why"] and r["trap"] for r in rows)
    judge = Judge(HeuristicJudgeLLM())
    got = [binary_groundedness(judge.groundedness(r["question"], r["answer"], r["contexts"]).label) for r in rows]
    rep = calibrate([r["human"] for r in rows], got, positive="grounded")
    assert 0.3 < rep.kappa < 0.9          # the lexical judge is useful and clearly imperfect
    traps = {r["trap"] for r, g in zip(rows, got) if g != r["human"]}
    assert "negation_flip" in traps and "cross_lingual" in traps


# ------------------------------------------------------------------ judge
CTX = [{"doc": "it-password-mfa-2026", "text": "SMS codes and phone calls are no longer accepted as a second factor."}]


def test_heuristic_judge_through_structured_outputs():
    j = Judge(HeuristicJudgeLLM())
    r = j.groundedness("Can I use SMS?", "SMS codes are no longer accepted as a second factor [1].", CTX)
    assert r.label == "grounded" and r.verdict.claims[0].supported and r.cost_usd == 0.0
    r = j.groundedness("Can I use SMS?", "Yes, use a FIDO2 key and the Okta app.", CTX)
    assert r.label == "not_grounded"
    assert j.groundedness("q", "not in the documents", CTX).label == "grounded"
    c = j.correctness("q", "Up to 5 days.", ["up to 5 days", "expire on March 31"])
    assert c.label == "partially_correct" and [f.status for f in c.verdict.facts] == ["stated", "missing"]
    assert j.correctness("q", "not in the documents", []).label == "correct"
    ref = j.refusal("Are SMS codes accepted as a second factor?", "not in the documents", CTX)
    assert ref.verdict.context_has_answer and ref.label == "inappropriate"


def test_pairwise_position_swap():
    facts = ["up to 5 days"]
    good, worse = "Up to 5 days.", "Some days, maybe."
    fair = Judge(HeuristicJudgeLLM())
    assert fair.pairwise("q", good, worse, facts=facts).extra["winner"] == "1"
    assert fair.pairwise("q", worse, good, facts=facts).extra["winner"] == "2"
    biased = Judge(HeuristicJudgeLLM(position_bias=0.5))
    one = biased.pairwise("q", "Up to 5 days off.", "5 days.", facts=facts, swap=False)
    assert one.extra["winner"] == "1"                       # first position wins a close call
    both = biased.pairwise("q", "Up to 5 days off.", "5 days.", facts=facts, swap=True)
    assert both.extra["position_inconsistent"] and both.extra["winner"] == "tie"


def test_judge_cache(tmp_path):
    j = Judge(HeuristicJudgeLLM(), cache=OutputCache(tmp_path))
    a = j.groundedness("q", "SMS codes are no longer accepted [1].", CTX)
    b = j.groundedness("q", "SMS codes are no longer accepted [1].", CTX)
    assert not a.cached and b.cached and b.label == a.label
    other = Judge(HeuristicJudgeLLM(), cache=OutputCache(tmp_path), rubrics={"groundedness": "changed rubric RUBRIC: groundedness"})
    assert other.version != j.version and not other.groundedness("q", "SMS codes are no longer accepted [1].", CTX).cached


def test_judge_with_mock_server():
    """The live code path (llmkit.LLM + native structured output) against mockllm."""
    from llmkit import LLM
    from mockllm import MockConfig, start_in_thread
    server, url = start_in_thread(MockConfig(ttft=0, tps=0))
    try:
        j = Judge(LLM("anthropic:mock-model", api_key="t", base_url=url))
        r = j.groundedness("q", "an answer", CTX)
        assert r.error is None and r.label in ("grounded", "partially_grounded", "not_grounded")
        p = j.pairwise("q", "a", "b")
        assert p.extra["winner"] in ("1", "2", "tie")
    finally:
        server.shutdown()


# ------------------------------------------------------------------ rag simulation, gates, reports
def test_policy_family_and_rule_follower():
    assert policy_family("Vacation Policy (2024)") == policy_family("Vacation Policy (2026)") == "vacation policy"
    assert policy_family("SaaS Access Policy (v2.1)") == "saas access policy"
    assert "latest effective_date" in PROMPTS["v1"] and "latest effective_date" not in PROMPTS["v2"]


def test_v2_prompt_regression_is_caught(golden, v1v2):
    base, cand = v1v2["v1"], v1v2["v2"]
    vc = golden.filter(type="version_conflict").ids()
    assert base.mean("answer_ok", vc) > cand.mean("answer_ok", vc)
    assert cand.mean("stale_cited") > base.mean("stale_cited")
    gates = [Threshold("answer_ok", 0.45), Threshold("answer_ok", 0.50, slice="version_conflict"),
             NoSignificantDrop("answer_ok"), NoSignificantDrop("answer_ok", slice="version_conflict", max_drop=0.10)]
    res = check_gates(cand, golden, gates, baseline=base)
    assert [r.passed for r in res] == [True, False, True, False]
    assert "McNemar" in res[2].detail                      # 0/1 metric: the exact test
    with pytest.raises(AssertionError, match="regression gate failed"):
        assert_gates(res)
    assert_gates(check_gates(base, golden, gates, baseline=base))     # v1 vs itself passes


def test_gate_refuses_mismatched_datasets(golden, v1v2):
    other = golden.filter(type="numeric")
    with pytest.raises(ValueError):
        check_gates(v1v2["v2"], golden, [Threshold("answer_ok", 0.1)],
                    baseline=Run("x", "y", other.ref, records=v1v2["v1"].records))


def test_reports_have_no_tables(golden, v1v2):
    rep = build_report(v1v2["v2"], golden, RAG_METRICS, baseline=v1v2["v1"],
                       gate_results=check_gates(v1v2["v2"], golden, [Threshold("answer_ok", 0.5)], baseline=v1v2["v1"]))
    md, html = to_markdown(rep), to_html(rep)
    assert "## Gates: FAIL" in md and "version_conflict" in md and "|---" not in md
    assert "<table" not in html and "prefers-color-scheme: dark" in html and "answer_ok" in html
    assert rep.failures and all(not math.isnan(ci.estimate) for ci in rep.overall.values() if ci)


def test_lab_promptfoo_config_is_valid_yaml():
    yaml = pytest.importorskip("yaml")
    for name in ("promptfooconfig.yaml", "promptfooconfig.live.yaml"):
        cfg = yaml.safe_load((LAB / "promptfoo" / name).read_text(encoding="utf-8"))
        assert len(cfg["tests"]) == 30 and [p["label"] for p in cfg["prompts"]] == ["v1", "v2"]
        t = cfg["tests"][0]["vars"]
        assert json.loads(t["expected"])["answer_facts"] and json.loads(t["doc_map"])
    sys.path.insert(0, str(LAB / "promptfoo"))
    try:
        import assert_evalkit
        import provider_offline
        v = cfg["tests"][0]["vars"]
        prompt = json.dumps([{"role": "system", "content": PROMPTS["v1"]}, {"role": "user", "content": v["user_message"]}])
        out = provider_offline.call_api(prompt, {}, {})["output"]
        g = assert_evalkit.get_assert(out, {"vars": v})
        assert isinstance(g["pass"], bool) and "answer_ok" in g["reason"]
    finally:
        sys.path.remove(str(LAB / "promptfoo"))
