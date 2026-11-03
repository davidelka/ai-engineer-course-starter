"""Exercise 5: spec -> Mermaid."""

from archkit import mermaid as ref
from conftest import mini_spec
from mine import to_mermaid


def body(text):
    """Lines that the contract fixes (styling lines are free)."""
    return [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith(("classDef", "class "))]


def small():
    return mini_spec(
        [{"id": "ui", "name": "Web UI", "kind": "client", "boundary": "user", "tech": "React"},
         {"id": "end", "name": "The \"end\" service", "kind": "service", "boundary": "vpc"},
         {"id": "db", "name": "Store", "kind": "datastore", "boundary": "vpc"},
         {"id": "m", "name": "Model", "kind": "llm", "boundary": "prov_a", "model": "anthropic:claude-haiku-5-5",
          "fallback": "m2"},
         {"id": "m2", "name": "Backup", "kind": "llm", "boundary": "prov_b", "fallback": "static_message"}],
        [{"from": "ui", "to": "end", "data": "question", "classification": "pii"},
         {"from": "end", "to": "m", "data": "prompt"},
         {"from": "end", "to": "db", "data": "write"}])


def test_header_and_trailing_newline():
    out = to_mermaid(small())
    assert out.splitlines()[0] == "flowchart LR" and out.endswith("\n")


def test_one_subgraph_per_used_boundary():
    lines = body(to_mermaid(small()))
    subs = [ln for ln in lines if ln.startswith("subgraph ")]
    assert subs == ['subgraph b_user["User · untrusted"]', 'subgraph b_vpc["VPC · trusted"]',
                    'subgraph b_prov_a["Provider A · third_party"]', 'subgraph b_prov_b["Provider B · third_party"]']
    assert lines.count("end") == 4


def test_shapes_and_labels():
    lines = body(to_mermaid(small()))
    assert 'c_ui["Web UI<br/><small>client · React</small>"]' in lines
    assert 'c_db[("Store<br/><small>datastore</small>")]' in lines
    assert 'c_m{{"Model<br/><small>llm · anthropic:claude-haiku-5-5</small>"}}' in lines


def test_quotes_escaped_and_end_is_prefixed():
    lines = body(to_mermaid(small()))
    assert 'c_end["The #quot;end#quot; service<br/><small>service</small>"]' in lines


def test_edges_in_order_with_pii_thick():
    lines = [ln for ln in body(to_mermaid(small())) if "-->" in ln or "==>" in ln or "-.->" in ln]
    assert lines == ['c_ui ==>|"question (pii)"| c_end', 'c_end -->|"prompt"| c_m', 'c_end -->|"write"| c_db',
                     'c_m -.->|"fallback"| c_m2']


def test_company_brain_matches_reference(company_brain):
    assert body(to_mermaid(company_brain)) == body(ref.to_mermaid(company_brain))
