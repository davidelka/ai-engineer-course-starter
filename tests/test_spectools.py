"""Environment tests for spectools (lesson 6): spec parsing, lint, traceability, drift, review grounding."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "labs" / "06-spec-driven"
sys.path[:0] = [str(ROOT), str(LAB)]

from spectools.lint import lint_spec  # noqa: E402
from spectools.review import SpecReview, ground_findings  # noqa: E402
from spectools.spec import parse_spec  # noqa: E402
from spectools.trace import attach_results, build_matrix, scan_req_markers  # noqa: E402

SPEC = LAB / "spec" / "access-requests.spec.md"


def test_parse_example_spec():
    spec = parse_spec(SPEC)
    assert spec.ids() == [f"REQ-{i}" for i in range(1, 12)] + ["NFR-1", "NFR-2"]
    r4 = spec.get("REQ-4")
    assert r4.statement.startswith("WHEN a request is created") and "Payroll" in r4.statement
    assert [c.id for c in r4.criteria][:2] == ["AC-4.1", "AC-4.2"]
    assert spec.get("NFR-1").kind == "non-functional"
    assert "out of scope" in spec.sections


def test_lint_example_is_clean_and_draft_is_not():
    assert lint_spec(parse_spec(SPEC)) == []
    rules = {f.rule for f in lint_spec(parse_spec(LAB / "spec" / "draft-vague.spec.md"))}
    assert {"missing-id", "duplicate-id", "not-ears", "vague-word", "no-criteria", "nfr-not-measurable"} <= rules


def test_traceability_of_acceptance_tests():
    m = build_matrix(parse_spec(SPEC), scan_req_markers([LAB / "acceptance"]))
    assert "REQ-10" in m.uncovered  # left for exercise 3
    assert m.orphans == {}


def test_attach_results_by_suffix():
    m = build_matrix(parse_spec(SPEC), {"REQ-1": ["test_a.py::test_x"]})
    attach_results(m, {"labs/06-spec-driven/acceptance/test_a.py::test_x": "failed"})
    assert m.rows[0].status == "FAILING"
    assert m.rows[1].status == "UNTESTED"


def test_review_grounding_drops_invented_quotes():
    spec_text = SPEC.read_text(encoding="utf-8")
    data = json.loads((LAB / "fixtures" / "review_access-requests.json").read_text(encoding="utf-8"))
    review = SpecReview.model_validate({"findings": data["findings"]})
    contract = (LAB / "spec" / "openapi.yaml").read_text(encoding="utf-8")
    g = ground_findings(review, spec_text + "\n" + contract, parse_spec(SPEC).ids())
    assert len(g.kept) == 5 and len(g.dropped) == 2


def test_reference_app_has_no_contract_drift():
    pytest.importorskip("fastapi")
    pytest.importorskip("openapi_core")
    from reference.app import create_app

    from spectools.contract import ContractClient, find_drift, load_contract

    app = create_app()
    assert find_drift(load_contract(LAB / "spec" / "openapi.yaml"), app.openapi()) == []
    c = ContractClient(app, LAB / "spec" / "openapi.yaml")
    h = {"X-Actor": "dana@acme.example", "X-Role": "employee"}
    r = c.post("/access-requests", json={"tool": "Slack", "access_level": "admin", "justification": "workspace admin"},
               headers=h, expect_valid_request=True)
    assert r.status_code == 201 and r.json()["route"] == "needs_security"
    assert c.post(f"/access-requests/{r.json()['id']}/approve", headers=h).status_code == 403


def test_drift_scenario_is_detected():
    pytest.importorskip("fastapi")
    from drift.scenarios import build_app

    from spectools.contract import find_drift, load_contract

    kinds = {d.kind for d in find_drift(load_contract(LAB / "spec" / "openapi.yaml"), build_app("reject_route").openapi())}
    assert kinds == {"undocumented-operation", "enum-mismatch"}
