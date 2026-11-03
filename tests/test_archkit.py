"""archkit (lesson 19): spec loading, rules, cost, latency, Mermaid, ADR lint, critique (mock)."""

from pathlib import Path

import pytest

from archkit import SpecError, load_spec
from archkit.adr import lint_adr
from archkit.cost import CallProfile, call_cost, monthly_cost, profiles_from_spec, request_cost, with_model
from archkit.critique import ADRCritique, critique, load_fixture
from archkit.latency import Stage, latency_budget, simulate, stages_from_spec
from archkit.mermaid import to_html, to_mermaid
from archkit.rules import check, rule_observability, rule_write_tools_approved

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "labs" / "19-ai-architecture"
SPECS = {
    "seeded": LAB / "specs" / "company_brain.arch.yaml",
    "fixed": ROOT / "archkit" / "examples" / "company_brain_fixed.arch.yaml",
    "triage": ROOT / "archkit" / "examples" / "ticket_triage.arch.yaml",
    "starter": LAB / "cases" / "ticket_triage" / "starter.arch.yaml",
}


def total_monthly(spec):
    b = spec.budget
    return b.fixed_monthly_usd + sum(
        monthly_cost(profiles_from_spec(p), p.requests_per_day, days=p.days, prompt_cache_hit_rate=p.prompt_cache_hit_rate,
                     response_cache_hit_rate=p.response_cache_hit_rate)["llm_monthly_usd"] for p in b.paths)


def keys(findings):
    return sorted((f.rule, f.severity, f.where) for f in findings)


# ------------------------------------------------------------ spec
@pytest.mark.parametrize("name", list(SPECS))
def test_shipped_specs_load(name):
    assert load_spec(SPECS[name]).components


def base():
    return {"system": "x", "boundaries": [{"id": "vpc", "name": "VPC", "trust": "trusted"}],
            "components": [{"id": "a", "name": "A", "kind": "service", "boundary": "vpc"}], "flows": []}


def test_unknown_boundary():
    d = base()
    d["components"][0]["boundary"] = "nope"
    with pytest.raises(SpecError, match="unknown boundary"):
        load_spec(d)


def test_duplicate_id_and_unknown_flow_end():
    d = base()
    d["components"].append(dict(d["components"][0]))
    with pytest.raises(SpecError, match="duplicate"):
        load_spec(d)
    d = base()
    d["flows"] = [{"from": "a", "to": "b", "data": "x"}]
    with pytest.raises(SpecError, match="unknown component"):
        load_spec(d)


def test_extra_field_rejected():
    d = base()
    d["components"][0]["colour"] = "red"
    with pytest.raises(SpecError):
        load_spec(d)


# ------------------------------------------------------------ rules on the shipped specs
def test_seeded_company_brain_findings():
    got = keys(check(load_spec(SPECS["seeded"])))
    assert got == sorted([
        ("external_input_guarded", "error", "grant_tool"),
        ("external_input_guarded", "error", "policy_llm"),
        ("llm_resilience", "error", "intent_router"),
        ("llm_resilience", "error", "policy_llm"),
        ("pii_classified", "error", "access_workflow->policy_llm"),
        ("pii_classified", "error", "access_workflow->tracing"),
        ("pii_classified", "error", "api_gateway->tracing"),
        ("pii_classified", "error", "grant_tool->okta"),
        ("observability", "warning", "policy_llm"),
    ])


def test_reference_solutions_are_clean_and_within_budget():
    for name in ("fixed", "triage"):
        s = load_spec(SPECS[name])
        assert check(s) == [], name
        assert total_monthly(s) <= s.budget.monthly_limit_usd, name


def test_seeded_is_over_budget():
    s = load_spec(SPECS["seeded"])
    assert total_monthly(s) > s.budget.monthly_limit_usd


def test_starter_only_misses_ops():
    assert {f.rule for f in check(load_spec(SPECS["starter"]))} == {"observability"}


def mini(flows, tool_side="write"):
    return load_spec({
        "system": "m",
        "boundaries": [{"id": "vpc", "name": "VPC", "trust": "trusted"}],
        "components": [
            {"id": "m", "name": "M", "kind": "llm", "boundary": "vpc"},
            {"id": "wf", "name": "WF", "kind": "service", "boundary": "vpc"},
            {"id": "ok", "name": "OK", "kind": "human_approval", "boundary": "vpc"},
            {"id": "t", "name": "T", "kind": "tool", "boundary": "vpc", "side_effects": tool_side},
        ],
        "flows": flows,
    })


def test_write_tool_needs_approval_or_exemption():
    bad = mini([{"from": "m", "to": "wf", "data": "x"}, {"from": "wf", "to": "t", "data": "x"}])
    assert keys(rule_write_tools_approved(bad)) == [("write_tools_approved", "error", "wf->t")]
    exempt = mini([{"from": "m", "to": "wf", "data": "x"},
                   {"from": "wf", "to": "t", "data": "x", "approval_exempt": "policy says so"}])
    assert rule_write_tools_approved(exempt) == []
    approved = mini([{"from": "m", "to": "ok", "data": "x"}, {"from": "ok", "to": "t", "data": "x"}])
    assert rule_write_tools_approved(approved) == []
    read_only = mini([{"from": "m", "to": "t", "data": "x"}], tool_side="read")
    assert rule_write_tools_approved(read_only) == []


def test_observability_rule():
    out = rule_observability(mini([]))
    assert [f.severity for f in out] == ["error", "error", "warning"]


# ------------------------------------------------------------ cost and latency
def test_cost_numbers():
    from llmkit.pricing import PRICES
    p = PRICES["claude-haiku-5-5"]
    c = CallProfile("a", "claude-haiku-5-5", 1000, 100, cacheable_tokens=800)
    assert call_cost(c) == pytest.approx((1000 * p["input"] + 100 * p["output"]) / 1e6)
    hit = (200 * p["input"] + 800 * p["cached_input"] + 100 * p["output"]) / 1e6
    miss = (200 * p["input"] + 800 * p["cache_write"] + 100 * p["output"]) / 1e6
    assert call_cost(c, 1.0) == pytest.approx(hit)
    assert request_cost([c], 0.5) == pytest.approx(0.5 * hit + 0.5 * miss)
    assert with_model([c], "claude-sonnet-5-5")[0].model == "claude-sonnet-5-5"
    with pytest.raises(ValueError):
        call_cost(CallProfile("a", "nope", 1, 1))


def test_company_brain_question_path_cost():
    p = load_spec(SPECS["seeded"]).budget.paths[0]
    m = monthly_cost(profiles_from_spec(p), p.requests_per_day, prompt_cache_hit_rate=p.prompt_cache_hit_rate,
                     response_cache_hit_rate=p.response_cache_hit_rate)
    assert 500 < m["llm_monthly_usd"] < 800   # Sonnet answers dominate; exact value depends on llmkit prices


def test_latency_budget_and_simulation():
    st = [Stage("a", 100, 50), Stage("b", 300, 100, "g"), Stage("c", 200, 80, "g"), Stage("d", 50, 20)]
    lb = latency_budget(st, 500)
    assert lb["blocks"] == [("a", 100), ("g", 300), ("d", 50)] and lb["slack_ms"] == 50
    sim = simulate(st, n=5000, seed=1)
    assert sim["p50_ms"] < sim["p95_ms"] < sim["sum_of_p95_ms"] == 450


def test_sum_of_p95_is_pessimistic_on_company_brain():
    p = load_spec(SPECS["seeded"]).budget.paths[0]
    sim = simulate(stages_from_spec(p), n=5000)
    assert sim["p95_ms"] < sim["sum_of_p95_ms"]


# ------------------------------------------------------------ mermaid
@pytest.mark.parametrize("name", list(SPECS))
def test_mermaid_shape(name):
    s = load_spec(SPECS[name])
    code = to_mermaid(s)
    lines = code.splitlines()
    assert lines[0] == "flowchart LR"
    assert sum(1 for ln in lines if ln.strip().startswith("subgraph ")) == sum(ln.strip() == "end" for ln in lines)
    assert all(f"c_{c.id}" in code for c in s.components)
    assert sum(1 for ln in lines if ("-->|" in ln or "==>|" in ln)) == len(s.flows)
    assert "<pre class=\"mermaid\">" in to_html(code, s.system)


# ------------------------------------------------------------ ADR lint
def test_example_adr_is_clean():
    assert lint_adr((LAB / "adr" / "0000-example-response-cache.md").read_text(encoding="utf-8")) == []


def test_template_is_not_an_adr_yet():
    out = lint_adr((LAB / "adr" / "TEMPLATE.md").read_text(encoding="utf-8"))
    where = {f.where for f in out if f.severity == "error"}
    assert {"decision drivers", "consequences", "cost and latency", "confirmation"} <= where


def test_lint_catches_missing_negative_and_numbers():
    text = """# ADR-0007: Something
- Status: accepted
## Context and problem statement
""" + ("x " * 200) + """
## Decision drivers
- a
- b
- c
## Considered options
### Option A: one
- Good, because x
- Bad, because y
### Option B: two
- Good, because x
- Bad, because y
## Decision outcome
Chosen option: "Option A: one", because a.
## Consequences
### Positive
- fast
## Cost and latency
cheap and quick
## Confirmation
we will see
"""
    msgs = " | ".join(f.message for f in lint_adr(text))
    assert "Negative" in msgs and "dollar" in msgs and "latency" in msgs and "threshold" in msgs


# ------------------------------------------------------------ critique
def test_critique_fixture_validates():
    c = load_fixture(LAB / "fixtures" / "adr_critique_example.json")
    assert isinstance(c, ADRCritique) and c.total == 6 and c.verdict == "revise"


def test_critique_against_mock_server():
    from llmkit import LLM, RetryPolicy
    from mockllm import MockConfig, start_in_thread
    server, url = start_in_thread(MockConfig(ttft=0, tps=0, seed=1))
    try:
        llm = LLM("anthropic:mock-model", base_url=url, api_key="mock", retry=RetryPolicy(max_attempts=1))
        res = critique(llm, "# ADR-0001: x", "rubric")
        assert isinstance(res.value, ADRCritique) and res.value.scores
    finally:
        server.shutdown()
