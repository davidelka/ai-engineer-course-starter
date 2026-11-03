"""Exercise 8: one question, two kinds of sources.

  "Who owns the service that caused the August 19 outage, how many tickets in our data are
   linked to that incident, and how many of them breached the SLA?"

No single source answers it:
  - WHICH service caused it, and when: only the postmortem document says so
    (data/acme/corpus/docs/eng-pm-2026-08-api.md: "Affected service: flow-api in both
    regions; root cause in auth-service")
  - WHO owns that service, and the ticket numbers: only the database has them
    (systems -> teams -> employees; tickets.incident_id)

The pipeline:
  1. document step: extract {root_cause_service, incident_date, quote} from the postmortem.
     Offline: a regex. --live: Claude with structured output. Either way the quote is CHECKED
     to appear verbatim in the document (a citation you cannot verify is not a citation).
  2. data step: PARAMETERIZED queries, not text-to-SQL. The question shape is known, so the
     SQL is written once by a person and only the values change (?, never string formatting).
  3. answer: facts from both, each with its own provenance, plus the scope note when the
     document and the data disagree (203 tickets in the postmortem vs the 200-ticket extract).

    python labs/08-enterprise-data/hybrid_answer.py
    python labs/08-enterprise-data/hybrid_answer.py --live
    python labs/08-enterprise-data/hybrid_answer.py --doc eng-pm-2026-06-billing      # try another postmortem
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from typing import Optional

import _lab
from _lab import DEFAULT_MODEL, ROOT
from pydantic import BaseModel, Field

from datakit import connect_ro, load_layer
from sqlglot import exp
from datakit.freshness import max_age_from_layer
from datakit.provenance import build_provenance

sys.path.insert(0, str(ROOT / "data" / "acme" / "corpus"))
import load  # noqa: E402

OWNER_SQL = ("SELECT s.name AS system, s.tier, t.name AS team, e.name AS lead "
             "FROM systems s JOIN teams t ON t.id = s.owner_team JOIN employees e ON e.id = t.lead_id "
             "WHERE s.name = ?")
TICKETS_SQL = ("SELECT COUNT(*) AS tickets, SUM(priority = 'P1') AS p1, SUM(sla_breached) AS breached "
               "FROM tickets WHERE incident_id = ?")


class IncidentFacts(BaseModel):
    root_cause_service: str = Field(description="The service where the root cause was, exactly as named in the document")
    incident_date: str = Field(description="Date of the incident, YYYY-MM-DD")
    quote: str = Field(description="One sentence or line copied VERBATIM from the document that names the root-cause service")
    tickets_reported: Optional[int] = Field(description="Number of support tickets the document reports, or null")


def extract_offline(text: str) -> IncidentFacts:
    """A deliberately simple extractor for the offline path."""
    line = next((l for l in text.splitlines() if "Affected service" in l), "")
    m = re.search(r"root cause in ([\w-]+)", line) or re.search(r"Affected service:\*\*\s*([\w-]+)", line)
    d = re.search(r"Date of incident:\*\*\s*([A-Z][a-z]+ \d{1,2}, \d{4})", text)
    t = re.search(r"(\d+) support tickets", text)
    date = datetime.strptime(d.group(1), "%B %d, %Y").strftime("%Y-%m-%d") if d else ""
    return IncidentFacts(root_cause_service=m.group(1) if m else "", incident_date=date,
                         quote=line.strip("- ").strip(), tickets_reported=int(t.group(1)) if t else None)


def extract_live(text: str, model: str) -> tuple[IncidentFacts, float]:
    from llmkit import LLM, load_dotenv
    from llmkit.structured import complete_structured
    load_dotenv(str(ROOT / ".env"))
    res = complete_structured(LLM(model), f"<document>\n{text}\n</document>", IncidentFacts,
                              system="Extract facts from this incident postmortem. Copy the quote verbatim.",
                              max_tokens=600)
    return res.value, res.cost_usd


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc", default="eng-pm-2026-08-api")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--now", default="2026-11-01T09:00:00Z")
    a = ap.parse_args()

    doc = load.get_doc(a.doc)
    meta = doc.meta
    print(f"document: {a.doc} | {meta['title']} | effective {meta['effective_date']} | "
          f"classification {meta['classification']}")
    if meta["classification"] == "confidential":
        print("  (confidential: Company Brain must check that the asker may open it; see lessons 9 and 25)")
    cost = 0.0
    facts, cost = extract_live(doc.text, a.model) if a.live else (extract_offline(doc.text), 0.0)
    verified = " ".join(facts.quote.split()) in " ".join(doc.text.split())
    print(f"\n1) from the document ({'Claude' if a.live else 'regex'}): {facts.model_dump()}")
    print(f"   quote found verbatim in the document: {verified}")
    if not verified or not facts.root_cause_service:
        print("   cannot continue without a verified fact")
        return

    layer = load_layer()
    con = connect_ro()
    pks = {t: tab.primary_key for t, tab in layer.tables.items()}
    limits = max_age_from_layer(layer)
    # The lineage query needs the values inline: sqlglot builds the literals (quotes escaped).
    lit = lambda v: exp.Literal.string(v).sql(dialect="sqlite")  # noqa: E731

    print("\n2) from the database (parameterized SQL):")
    owner = con.execute(OWNER_SQL, (facts.root_cause_service,)).fetchone()
    print(f"   owner   : {owner}   <- {OWNER_SQL}  [{facts.root_cause_service}]")
    if owner is None:
        print("   the service is not in the systems table: say so instead of guessing")
        return
    prov = build_provenance(con, OWNER_SQL.replace("?", lit(facts.root_cause_service)),
                            ["systems", "teams", "employees"], pks, a.now, limits).chips()
    # The document has no incident id. The tickets use INC-<date>. Linking by date is a guess
    # that works only when the date is clean: the real fix is an incident_id field in the
    # postmortem's metadata (a shared key between documents and data).
    tick = None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", facts.incident_date or ""):
        incident_id = "INC-" + facts.incident_date
        tick = con.execute(TICKETS_SQL, (incident_id,)).fetchone()
        print(f"   tickets : {tick}   <- {TICKETS_SQL}  [{incident_id}]")
        prov += build_provenance(con, TICKETS_SQL.replace("?", lit(incident_id)), ["tickets"], pks, a.now,
                                 limits).chips()
    else:
        print(f"   tickets : cannot link: no clean incident date ({facts.incident_date!r}) and no incident id "
              "in the document")

    print("\n3) answer")
    system, tier, team, lead = owner
    text = (f"   {meta['title']}: the root cause was in {system} (tier {tier}), owned by the {team} team, "
            f"led by {lead}.")
    if tick is None:
        text += " I could not link this document to ticket data, so I give no ticket numbers."
    elif tick[0] == 0:
        text += (f" No tickets in our data are linked to {incident_id} (the extract covers May-October 2026 "
                 "and only 200 tickets).")
    else:
        text += (f" In our ticket data, {tick[0]} tickets are linked to {incident_id} ({tick[1]} of them P1), "
                 f"and {tick[2]} breached the first-response SLA.")
    print(text)
    if facts.tickets_reported and (tick is None or facts.tickets_reported != tick[0]):
        print(f"   Note: the postmortem itself reports {facts.tickets_reported} tickets. acme.db holds a "
              "200-ticket extract of Zendesk, so its count is a sample, not the total.")
    print("\n   sources:")
    print(f"   [doc {a.doc} · effective {meta['effective_date']} · \"{facts.quote[:90]}\"]")
    for c in prov:
        print(f"   [{c}]")
    if a.live:
        print(f"\ncost: ${cost:.5f}")


if __name__ == "__main__":
    main()
