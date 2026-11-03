"""Exercise 3: architecture rules."""

from archkit import rules as ref
from conftest import mini_spec
from mine import rule_llm_resilience, rule_pii_classified

OK_LLM = dict(kind="llm", boundary="prov_a", timeout_s=10, retry={"max_attempts": 3}, fallback="static_message")


def llm(cid, **kw):
    return {"id": cid, "name": cid, **OK_LLM, **kw}


def svc(cid, kind="service", boundary="vpc", **kw):
    return {"id": cid, "name": cid, "kind": kind, "boundary": boundary, **kw}


def msgs(findings, severity=None):
    return [f.message for f in findings if severity in (None, f.severity)]


# ------------------------------------------------------------ llm_resilience
def test_resilient_llm_is_clean():
    assert rule_llm_resilience(mini_spec([llm("m")], [])) == []


def test_missing_timeout_retry_fallback():
    s = mini_spec([llm("m", timeout_s=None, retry=None, fallback=None)], [])
    out = rule_llm_resilience(s)
    assert all(f.rule == "llm_resilience" and f.where == "m" and f.severity == "error" for f in out)
    text = " ".join(msgs(out)).lower()
    assert "timeout" in text and "retry" in text and "fallback" in text and len(out) == 3


def test_one_attempt_is_not_a_retry():
    out = rule_llm_resilience(mini_spec([llm("m", retry={"max_attempts": 1})], []))
    assert len(out) == 1 and "retry" in out[0].message.lower()


def test_zero_timeout():
    out = rule_llm_resilience(mini_spec([llm("m", timeout_s=0)], []))
    assert len(out) == 1 and "timeout" in out[0].message.lower()


def test_unknown_fallback():
    out = rule_llm_resilience(mini_spec([llm("m", fallback="nope")], []))
    assert len(out) == 1 and out[0].severity == "error" and "nope" in out[0].message


def test_fallback_itself():
    out = rule_llm_resilience(mini_spec([llm("m", fallback="m")], []))
    assert len(out) == 1 and "itself" in out[0].message


def test_fallback_same_boundary_is_a_warning():
    s = mini_spec([llm("m", fallback="m2"), llm("m2")], [])
    out = rule_llm_resilience(s)
    assert [(f.severity, f.where) for f in out] == [("warning", "m")]
    assert "same boundary" in out[0].message


def test_fallback_other_provider_or_service_is_fine():
    s = mini_spec([llm("m", fallback="m2"), llm("m2", boundary="prov_b"), llm("m3", fallback="rules"), svc("rules")], [])
    assert rule_llm_resilience(s) == []


def test_non_llm_components_are_ignored():
    assert rule_llm_resilience(mini_spec([svc("api")], [])) == []


# ------------------------------------------------------------ pii_classified
def test_pii_direct_to_third_party():
    s = mini_spec([svc("api"), svc("logs", kind="observability", boundary="prov_a")],
                  [{"from": "api", "to": "logs", "data": "raw", "classification": "pii"}])
    out = rule_pii_classified(s)
    assert len(out) == 1 and out[0].where == "api->logs" and out[0].rule == "pii_classified"
    assert "pii" in out[0].message.lower() and "logs" in out[0].message


def test_pii_allowed_destination_is_skipped():
    s = mini_spec([svc("api"), llm("m", pii_allowed=True)],
                  [{"from": "api", "to": "m", "data": "ticket", "classification": "pii"}])
    assert rule_pii_classified(s) == []


def test_upstream_pii_without_classifier():
    s = mini_spec([svc("ui", kind="client", boundary="user"), svc("api"), llm("m")],
                  [{"from": "ui", "to": "api", "data": "q", "classification": "pii"},
                   {"from": "api", "to": "m", "data": "q2"}])
    out = rule_pii_classified(s)
    assert len(out) == 1 and out[0].where == "api->m" and "ui" in out[0].message


def test_classifier_on_the_path_stops_it():
    s = mini_spec([svc("ui", kind="client", boundary="user"), svc("api"), svc("red", kind="classifier"),
                   svc("router"), llm("m")],
                  [{"from": "ui", "to": "api", "data": "q", "classification": "pii"},
                   {"from": "api", "to": "red", "data": "q", "classification": "pii"},
                   {"from": "red", "to": "router", "data": "redacted"},
                   {"from": "router", "to": "m", "data": "redacted"}])
    assert rule_pii_classified(s) == []


def test_flow_from_classifier_is_fine():
    s = mini_spec([svc("ui", kind="client", boundary="user"), svc("red", kind="classifier"), llm("m")],
                  [{"from": "ui", "to": "red", "data": "q", "classification": "pii"},
                   {"from": "red", "to": "m", "data": "redacted"}])
    assert rule_pii_classified(s) == []


def test_cycles_terminate_and_one_finding_per_flow():
    s = mini_spec([svc("ui", kind="client", boundary="user"), svc("wf"), llm("m")],
                  [{"from": "ui", "to": "wf", "data": "q", "classification": "pii"},
                   {"from": "wf", "to": "m", "data": "req"},
                   {"from": "m", "to": "wf", "data": "decision"},
                   {"from": "ui", "to": "wf", "data": "again", "classification": "pii"}])
    out = rule_pii_classified(s)
    assert [f.where for f in out] == ["wf->m"]


def test_trusted_destinations_are_ignored():
    s = mini_spec([svc("ui", kind="client", boundary="user"), svc("db", kind="datastore")],
                  [{"from": "ui", "to": "db", "data": "q", "classification": "pii"}])
    assert rule_pii_classified(s) == []


# ------------------------------------------------------------ the real spec
def key(findings):
    return sorted((f.rule, f.severity, f.where) for f in findings)


def test_company_brain_matches_reference(company_brain):
    assert key(rule_llm_resilience(company_brain)) == key(ref.rule_llm_resilience(company_brain))
    assert key(rule_pii_classified(company_brain)) == key(ref.rule_pii_classified(company_brain))
