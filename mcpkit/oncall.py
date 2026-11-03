"""Who is on call for an Acme production service (reference for lesson 17, exercise 3).

The source of truth is the Engineering Service Catalog, a Markdown document in the corpus:
data/acme/corpus/docs/eng-service-catalog.md. Its "Production services" table has one row
per service:

    | Service | Owner team | Team lead | Tier | On-call rotation | PagerDuty service |
    | flow-api | Core API | Itai Barak | 1 | core-api-oncall: weekly, handover Sunday 10:00 | flow-api-prod |
    | flow-scheduler | Engine | Dana Levi | 1 | engine-oncall (shared with flow-engine) | flow-scheduler-prod |
    | auth-service | Identity | Gil Avraham | 1 | identity-oncall: weekly, handover Thursday 10:00; secondary is platform-oncall | auth-service-prod |
    | lighthouse | Data | Eitan Klein | 3 | business hours, #data-help | none |

get_oncall_for_service() turns one row into a dict an LLM can use without reading the whole
document (that is the point of a tool: precise, small, structured). Runbooks are found by
title: a corpus document whose title ends with " - <service>" (e.g. "On-call Runbook - flow-api",
or the Hebrew "הערות כונן - flow-scheduler").
"""

from __future__ import annotations

import difflib
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

from toolkit import ToolError

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "data" / "acme" / "corpus" / "docs"
CATALOG = DOCS / "eng-service-catalog.md"
ACK_MINUTES = {1: 5, 2: 15}  # from the catalog's "Tier definitions"


def catalog_text() -> str:
    return CATALOG.read_text(encoding="utf-8")


def parse_services_table(text: str) -> list[dict]:
    """The rows of the '## Production services' table as raw dicts (column name -> cell)."""
    m = re.search(r"^## Production services\s*$(.*?)(?=^## |\Z)", text, flags=re.M | re.S)
    if not m:
        raise ToolError("The service catalog has no 'Production services' section.")
    lines = [ln.strip() for ln in m.group(1).splitlines() if ln.strip().startswith("|")]
    header = [c.strip() for c in lines[0].strip("|").split("|")]
    rows = []
    for ln in lines[2:]:  # skip the |---| separator
        cells = [c.strip() for c in ln.strip("|").split("|")]
        rows.append(dict(zip(header, cells)))
    return rows


@lru_cache(maxsize=1)
def _runbook_titles() -> dict[str, str]:
    """service name -> doc id, from document titles ending with ' - <service>'."""
    out = {}
    for p in sorted(DOCS.glob("*.md")):
        head = p.read_text(encoding="utf-8")[:600]
        t = re.search(r"^title:\s*\"?(.+?)\"?\s*$", head, flags=re.M)
        if t and " - " in t.group(1):
            out[t.group(1).rsplit(" - ", 1)[1].strip()] = p.stem
    return out


def _rotation_parts(cell: str) -> dict:
    """'core-api-oncall: weekly, handover Sunday 10:00' / 'engine-oncall (shared with flow-engine)' /
    'identity-oncall: weekly, handover Thursday 10:00; secondary is platform-oncall' / 'business hours, #data-help'."""
    out = {"rotation": None, "schedule": None, "secondary": None, "shared_with": None, "channel": None}
    if cell.lower().startswith("business hours"):
        ch = re.search(r"#[\w-]+", cell)
        out["channel"] = ch.group(0) if ch else None
        return out
    main, _, rest = cell.partition(";")
    sec = re.search(r"secondary is ([\w-]+)", rest)
    out["secondary"] = sec.group(1) if sec else None
    shared = re.search(r"\(shared with ([\w-]+)\)", main)
    if shared:
        out["shared_with"] = shared.group(1)
        main = main[: shared.start()]
    name, _, sched = main.partition(":")
    out["rotation"] = name.strip() or None
    out["schedule"] = sched.strip() or None
    return out


def get_oncall_for_service(service: str, catalog: Optional[str] = None) -> dict:
    """See labs/17-mcp/mine.py for the exact contract (this is the reference implementation)."""
    key = (service or "").strip().lower().replace(" ", "-").replace("_", "-")
    if not key:
        raise ToolError("service is empty. Pass a service name such as 'flow-api' or 'billing-service'.")
    rows = parse_services_table(catalog if catalog is not None else catalog_text())
    by_name = {r["Service"].lower(): r for r in rows}
    row = by_name.get(key)
    if row is None:
        names = list(by_name)
        close = difflib.get_close_matches(key, names, n=3, cutoff=0.5) or [n for n in names if key in n]
        hint = f" Did you mean: {', '.join(close)}?" if close else f" Known services: {', '.join(names)}."
        raise ToolError(f"No production service named {service!r} in the Engineering Service Catalog.{hint}")
    tier = int(row["Tier"])
    parts = _rotation_parts(row["On-call rotation"])
    if parts["shared_with"] and not parts["schedule"]:
        # the schedule is written once, on the row that owns the rotation
        for r in rows:
            p = _rotation_parts(r["On-call rotation"])
            if p["rotation"] == parts["rotation"] and p["schedule"]:
                parts["schedule"] = p["schedule"]
                break
    pd = row.get("PagerDuty service", "").strip()
    name = row["Service"]
    return {
        "service": name,
        "owner_team": row["Owner team"],
        "team_lead": row["Team lead"],
        "tier": tier,
        **parts,
        "pagerduty_service": None if pd.lower() in ("", "none") else pd,
        "coverage": "24/7" if tier in ACK_MINUTES else "business hours",
        "ack_minutes": ACK_MINUTES.get(tier),
        "runbook": _runbook_titles().get(name),
        "source": "eng-service-catalog",
    }
