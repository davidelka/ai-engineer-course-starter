"""Exercise 2: your semantic layer, labs/08-enterprise-data/semantic/my_semantic.yaml.

It must load (datakit.semantic.load_layer validates it), keep the sensitivity labels, and
contain the definitions the golden questions depend on.
"""

import re
from pathlib import Path

import pytest

from datakit.semantic import load_layer, policy_from_layer, render_context
from ctxkit.tokens import count_tokens

PATH = Path(__file__).resolve().parent.parent / "semantic" / "my_semantic.yaml"


@pytest.fixture(scope="module")
def mine():
    return load_layer(PATH)


def metric(layer, name):
    m = next((m for m in layer.metrics if m.name == name), None)
    assert m is not None, f"metric {name!r} is missing"
    return m


def test_loads_and_keeps_all_tables(mine):
    assert set(mine.tables) == {"employees", "teams", "systems", "access_grants", "customers", "tickets"}


def test_sensitivity_labels_kept(mine):
    assert mine.tables["employees"].columns["email"].sensitivity == "pii"
    assert mine.tables["customers"].columns["arr_usd"].sensitivity == "financial"


def test_sla_breach_rate_excludes_tickets_without_target(mine):
    m = metric(mine, "sla_breach_rate")
    assert m.table == "tickets"
    assert re.search(r"sla_target_minutes\s+IS\s+NOT\s+NULL", m.filter, re.I), \
        "starter tickets have no target: they must not be in the denominator"
    assert "sla_breached" in m.expr


def test_open_tickets_includes_pending(mine):
    m = metric(mine, "open_tickets")
    assert "pending" in m.filter and "open" in m.filter


def test_red_folder_arr(mine):
    m = metric(mine, "red_folder_arr")
    assert m.table == "customers" and "arr_usd" in m.expr and "red_folder" in m.filter


def test_red_folder_term_with_synonyms(mine):
    t = next((t for t in mine.terms if "red folder" in t.term.lower()), None)
    assert t is not None, "add a 'Red Folder' business term"
    assert t.synonyms, "give it at least one synonym (how people actually say it)"
    assert "red_folder" in t.means


def test_open_ticket_term(mine):
    t = next((t for t in mine.terms if "open" in t.term.lower()), None)
    assert t is not None and "pending" in t.means


def test_join_paths(mine):
    pairs = {(r.from_, r.to) for r in mine.relationships}
    assert ("tickets.customer_id", "customers.id") in pairs
    assert ("systems.owner_team", "teams.id") in pairs


def test_renders_compactly_and_hides_what_the_role_cannot_see(mine):
    text = render_context(mine, role="analyst")
    assert count_tokens(text) < 2500
    lines = text.splitlines()
    assert not any(l.startswith("- email ") for l in lines), "analyst must not even see the email column"
    assert not any(l.startswith("- arr_usd ") for l in lines), "analyst must not see arr_usd"


def test_policy_still_builds(mine):
    p = policy_from_layer(mine)
    assert p.sensitive["employees.email"] == "pii"
