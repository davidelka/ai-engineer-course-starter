"""Environment tests for the shared Acme corpus (data/acme/corpus).

They check the contract that lessons 8-13, 22-23 and the projects rely on: document counts
and metadata, the golden QA set (every quote verbatim in its source), and the consistency of
the structured data with the documents. Offline, standard library only (pypdf/python-docx are
used for the PDF/DOCX quote checks when installed, otherwise those checks are skipped).
"""
from __future__ import annotations

import csv
import re
import sqlite3
import sys
from collections import Counter
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

import pytest

CORPUS = Path(__file__).resolve().parents[1] / "data" / "acme" / "corpus"
sys.path.insert(0, str(CORPUS))
import load  # noqa: E402

DEPARTMENTS = {"hr", "it_security", "engineering", "sales_support", "finance", "company"}
CLASSIFICATIONS = {"public", "internal", "confidential"}
QA_TYPES = {"single_hop", "multi_hop", "numeric", "unanswerable", "version_conflict", "hebrew", "acronym"}

DOCS = list(load.iter_docs())
BY_ID = {d.id: d for d in DOCS}
QA = load.load_qa()


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


class _TextHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self._skip = [], 0

    def handle_starttag(self, tag, attrs):
        self._skip += tag in ("script", "style")

    def handle_endtag(self, tag):
        self._skip -= tag in ("script", "style")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


# ------------------------------------------------------------------ documents

def test_document_count_and_formats():
    assert 45 <= len(DOCS) <= 55
    fmt = Counter(d.format for d in DOCS)
    assert fmt["html"] >= 3 and fmt["pdf"] >= 2 and fmt["docx"] >= 1
    assert fmt["md"] >= 40


def test_ids_unique_and_match_filenames():
    assert len(BY_ID) == len(DOCS)
    for d in DOCS:
        assert d.path.stem == d.id, d.path


@pytest.mark.parametrize("doc", DOCS, ids=lambda d: d.id)
def test_metadata_fields(doc):
    for k in load.REQUIRED_META:
        assert doc.meta.get(k) not in (None, ""), f"{doc.id}: missing {k}"
    assert doc.meta["department"] in DEPARTMENTS
    assert doc.meta["classification"] in CLASSIFICATIONS
    assert doc.meta["language"] in {"en", "he"}
    date.fromisoformat(str(doc.meta["effective_date"]))
    if doc.format != "md":
        assert doc.path.with_name(doc.id + ".meta.yaml").exists()


def test_markdown_lengths():
    for d in load.iter_docs({"md"}):
        n = len(d.text.split())
        assert 200 <= n <= 2500, (d.id, n)


def test_departments_and_hebrew():
    dept = Counter(d.meta["department"] for d in DOCS)
    assert set(dept) == DEPARTMENTS
    he = [d for d in DOCS if d.meta["language"] == "he"]
    assert 8 <= len(he) <= 10
    for d in he:
        if d.text:
            assert re.search(r"[֐-׿]", d.text)


def test_supersedes_points_to_older_doc():
    pairs = [(d, d.meta["supersedes"]) for d in DOCS if d.meta.get("supersedes")]
    assert len(pairs) >= 8
    for d, old in pairs:
        assert old in BY_ID, old
        assert str(BY_ID[old].meta["effective_date"]) < str(d.meta["effective_date"])


def test_prompt_injection_doc_present():
    text = BY_ID["sales-partner-northwind-notes"].text
    assert "ignore all previous instructions" in text


# ------------------------------------------------------------------ golden set

def test_golden_size_and_types():
    assert 70 <= len(QA) <= 80
    types = Counter(r["type"] for r in QA)
    assert set(types) <= QA_TYPES
    assert types["unanswerable"] >= 8
    assert types["hebrew"] >= 8
    assert types["multi_hop"] >= 8
    assert types["version_conflict"] >= 8
    assert types["acronym"] >= 5 and types["numeric"] >= 5
    assert len({r["id"] for r in QA}) == len(QA)


def test_golden_fields_and_sources():
    for r in QA:
        for k in ("id", "question", "answer", "answer_facts", "source_ids", "source_quotes", "type", "difficulty"):
            assert k in r, (r["id"], k)
        assert r["difficulty"] in {"easy", "medium", "hard"}
        assert set(r["source_ids"]) == {q["source_id"] for q in r["source_quotes"]}
        for sid in r["source_ids"]:
            assert sid in BY_ID, (r["id"], sid)
        if r["type"] == "unanswerable":
            assert r["answer"] == "not in the documents" and not r["source_ids"]
        else:
            assert r["source_quotes"] and r["answer_facts"]
        if r["type"] == "multi_hop":
            assert len(r["source_ids"]) >= 2, r["id"]


def _quotes(fmt):
    return [(r["id"], q["source_id"], q["quote"]) for r in QA for q in r["source_quotes"]
            if BY_ID[q["source_id"]].format == fmt]


def test_quotes_verbatim_markdown():
    qs = _quotes("md")
    assert len(qs) > 60
    for qid, sid, quote in qs:
        assert quote in BY_ID[sid].text, (qid, sid, quote)


def test_quotes_verbatim_html():
    for qid, sid, quote in _quotes("html"):
        p = _TextHTML()
        p.feed(BY_ID[sid].path.read_text(encoding="utf-8"))
        assert norm(quote) in norm(" ".join(p.parts)), (qid, sid)


def test_quotes_verbatim_pdf():
    pypdf = pytest.importorskip("pypdf")
    for qid, sid, quote in _quotes("pdf"):
        text = " ".join(pg.extract_text() for pg in pypdf.PdfReader(str(BY_ID[sid].path)).pages)
        assert norm(quote) in norm(text), (qid, sid, quote)


def test_quotes_verbatim_docx():
    docx = pytest.importorskip("docx")
    for qid, sid, quote in _quotes("docx"):
        d = docx.Document(str(BY_ID[sid].path))
        parts = [p.text for p in d.paragraphs] + [c.text for t in d.tables for row in t.rows for c in row.cells]
        assert norm(quote) in norm("\n".join(parts)), (qid, sid, quote)


def test_hebrew_questions_are_in_hebrew():
    for r in QA:
        if r["type"] == "hebrew":
            assert re.search(r"[֐-׿]", r["question"]), r["id"]


# ------------------------------------------------------------------ structured data

@pytest.fixture(scope="module")
def db():
    con = sqlite3.connect(load.db_path())
    con.row_factory = sqlite3.Row
    yield con
    con.close()


def test_structured_counts(db):
    counts = {t: db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in ("employees", "teams", "systems", "access_grants", "customers", "tickets")}
    assert counts["employees"] == 120
    assert 20 <= counts["systems"] <= 30
    assert 280 <= counts["access_grants"] <= 320
    assert 180 <= counts["tickets"] <= 220
    for t, n in counts.items():
        with open(load.csv_path(t), encoding="utf-8") as f:
            assert sum(1 for _ in csv.reader(f)) - 1 == n, t
    prov = {r["table_name"]: r for r in db.execute("SELECT * FROM provenance")}
    assert set(counts) <= set(prov)
    for t, n in counts.items():
        assert prov[t]["row_count"] == n and prov[t]["source_system"]


def test_org_chart_matches_employees(db):
    text = BY_ID["co-org-chart"].text
    for team in db.execute("SELECT t.name, t.headcount, e.name AS lead FROM teams t JOIN employees e ON e.id = t.lead_id"):
        if team["name"] == "Executive Team":
            continue
        n = db.execute("SELECT COUNT(*) FROM employees e JOIN teams t ON e.team = t.id WHERE t.name = ?",
                       (team["name"],)).fetchone()[0]
        assert n == team["headcount"]
        assert team["lead"] in text
        assert re.search(rf"{re.escape(team['lead'])}[^\n]*?{n} people", text), team["name"]
    locs = dict(db.execute("SELECT location, COUNT(*) FROM employees GROUP BY location").fetchall())
    assert f"{locs['Tel Aviv']} in Tel Aviv" in text and f"{locs['Haifa']} in Haifa" in text
    assert f"{locs['Berlin']} in Berlin" in text
    # every manager exists
    assert db.execute("SELECT COUNT(*) FROM employees WHERE manager_id IS NOT NULL AND manager_id NOT IN (SELECT id FROM employees)").fetchone()[0] == 0


def test_service_owners_match_catalog(db):
    catalog = BY_ID["eng-service-catalog"].text
    rows = re.findall(r"^\| ([a-z-]+) \| ([A-Za-z ]+) \| ([A-Za-z ]+) \| (\d) \|", catalog, re.M)
    assert len(rows) >= 9
    for service, team_name, lead, tier in rows:
        r = db.execute("SELECT s.tier, t.name AS team, e.name AS lead FROM systems s JOIN teams t ON t.id = s.owner_team "
                       "JOIN employees e ON e.id = t.lead_id WHERE s.name = ?", (service,)).fetchone()
        assert r is not None, service
        assert (r["team"], r["lead"], r["tier"]) == (team_name, lead, int(tier)), service


def test_access_grants_follow_policy(db):
    approved = {r[0] for r in db.execute("SELECT name FROM systems WHERE approved_tool = 1")}
    assert approved == {"jira", "confluence", "slack", "google-workspace", "zoom", "miro", "figma", "github"}
    security = {r[0] for r in db.execute("SELECT id FROM employees WHERE team = 'security'")}
    for g in db.execute("SELECT g.*, s.approved_tool, s.sensitive FROM access_grants g JOIN systems s ON s.name = g.system"):
        if g["level"] == "admin" or g["sensitive"]:
            assert g["route"] == "needs_security", g["id"]
            assert g["approved_by"] in security
        elif g["approved_tool"] and g["level"] in ("read", "viewer", "member"):
            assert g["route"] == "auto_approve" and g["approved_by"] == "system:auto"
        else:
            assert g["route"] == "needs_manager", g["id"]
    assert set(r[0] for r in db.execute("SELECT DISTINCT route FROM access_grants")) == {"auto_approve", "needs_manager", "needs_security"}


def test_tickets_sla_consistent(db):
    for t in db.execute("SELECT * FROM tickets"):
        if t["sla_target_minutes"] is None:
            assert t["customer_plan"] == "starter" and t["sla_breached"] == 0
        else:
            assert t["sla_breached"] == int(t["first_response_minutes"] > t["sla_target_minutes"])
    p1_ent = db.execute("SELECT DISTINCT sla_target_minutes FROM tickets WHERE priority='P1' AND customer_plan='enterprise'").fetchall()
    assert [r[0] for r in p1_ent] in ([30], [])
    assert db.execute("SELECT COUNT(*) FROM tickets WHERE customer_id NOT IN (SELECT id FROM customers)").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM customers WHERE red_folder = 1").fetchone()[0] == 25
