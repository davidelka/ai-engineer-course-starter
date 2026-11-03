"""Build the structured side of the Acme corpus: SQLite db + CSV files.

Deterministic (fixed seed). Run from anywhere:
    python3 data/acme/corpus/build/build_structured.py

Consistency with the documents:
- team leads, owners and headcounts match co-org-chart and eng-service-catalog;
- systems.owner_team matches the Service Catalog;
- access_grants.route is computed with the rules of the SaaS Access Policy (v2.1/v2.2);
- tickets.sla_target_minutes / sla_breached use the FRT targets of sup-escalation
  (business hours/days are approximated: 1 business hour = 60 min, 1 business day = 9 h).
"""
from __future__ import annotations

import csv
import random
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "structured"
SEED = 20261101
EXTRACTED_AT = "2026-10-31T23:00:00Z"

# team_id, name, department, lead, reports_to (lead of parent), main location, headcount
TEAMS = [
    ("exec", "Executive Team", "company", "Yael Shapira", None, "Tel Aviv", 8),
    ("core-api", "Core API", "engineering", "Itai Barak", "Michal Ben-David", "Haifa", 7),
    ("engine", "Engine", "engineering", "Dana Levi", "Michal Ben-David", "Haifa", 8),
    ("integrations", "Integrations", "engineering", "Omer Haddad", "Michal Ben-David", "Tel Aviv", 7),
    ("billing", "Billing", "engineering", "Rina Sasson", "Michal Ben-David", "Tel Aviv", 6),
    ("identity", "Identity", "engineering", "Gil Avraham", "Michal Ben-David", "Haifa", 5),
    ("frontend", "Frontend", "engineering", "Maya Rosen", "Michal Ben-David", "Tel Aviv", 7),
    ("data", "Data", "engineering", "Eitan Klein", "Michal Ben-David", "Haifa", 6),
    ("platform", "Platform", "engineering", "Boaz Nahum", "Michal Ben-David", "Haifa", 7),
    ("security", "Security", "it_security", "Tamar Golan", "Amir Katz", "Tel Aviv", 4),
    ("it", "IT", "it_security", "Yossi Dahan", "Amir Katz", "Tel Aviv", 3),
    ("product", "Product Management", "product", "Hagar Levy", "Noam Friedman", "Tel Aviv", 5),
    ("design", "Product Design", "product", "Hila Tzur", "Noam Friedman", "Tel Aviv", 4),
    ("sales-il", "Sales Israel & Americas", "sales_support", "Ofer Levi", "Daniel Weiss", "Tel Aviv", 8),
    ("sales-emea", "Sales EMEA", "sales_support", "Lena Hoffmann", "Daniel Weiss", "Berlin", 7),
    ("support-il", "Customer Support Israel & Americas", "sales_support", "Nir Golan", "Shira Levin", "Tel Aviv", 8),
    ("support-emea", "Customer Support EMEA", "sales_support", "Jonas Becker", "Shira Levin", "Berlin", 5),
    ("finance", "Finance", "finance", "Keren Amar", "Avi Mizrahi", "Tel Aviv", 5),
    ("people", "People", "hr", "Sivan Elbaz", "Orly Peretz", "Tel Aviv", 5),
    ("marketing", "Marketing", "company", "Gali Oren", "Yael Shapira", "Tel Aviv", 5),
]

# name, team, title, location (named people referenced in the documents)
FIXED = [
    ("Yael Shapira", "exec", "CEO", "Tel Aviv"),
    ("Amir Katz", "exec", "CTO", "Tel Aviv"),
    ("Michal Ben-David", "exec", "VP Engineering", "Haifa"),
    ("Noam Friedman", "exec", "VP Product", "Tel Aviv"),
    ("Daniel Weiss", "exec", "VP Sales", "Tel Aviv"),
    ("Shira Levin", "exec", "VP Customer Support", "Tel Aviv"),
    ("Orly Peretz", "exec", "VP People", "Tel Aviv"),
    ("Avi Mizrahi", "exec", "CFO", "Tel Aviv"),
    ("Itai Barak", "core-api", "Engineering Team Lead", "Haifa"),
    ("Tomer Shani", "core-api", "Senior Software Engineer", "Haifa"),
    ("Dana Levi", "engine", "Engineering Team Lead", "Haifa"),
    ("Yonatan Peled", "engine", "Senior Software Engineer", "Haifa"),
    ("Omer Haddad", "integrations", "Engineering Team Lead", "Tel Aviv"),
    ("Rina Sasson", "billing", "Engineering Team Lead", "Tel Aviv"),
    ("Nadav Eshel", "billing", "Software Engineer", "Tel Aviv"),
    ("Gil Avraham", "identity", "Engineering Team Lead", "Haifa"),
    ("Maya Rosen", "frontend", "Engineering Team Lead", "Tel Aviv"),
    ("Eitan Klein", "data", "Engineering Team Lead", "Haifa"),
    ("Boaz Nahum", "platform", "Engineering Team Lead", "Haifa"),
    ("Sergey Volkov", "platform", "Site Reliability Engineer", "Haifa"),
    ("Tamar Golan", "security", "CISO", "Tel Aviv"),
    ("Lior Ashkenazi", "security", "Security Engineer", "Tel Aviv"),
    ("Ruth Malka", "security", "Security Engineer", "Haifa"),
    ("Yossi Dahan", "it", "Head of IT", "Tel Aviv"),
    ("Ariel Cohen", "it", "IT Specialist", "Tel Aviv"),
    ("Bar Malul", "it", "IT Specialist", "Tel Aviv"),
    ("Hagar Levy", "product", "Group Product Manager", "Tel Aviv"),
    ("Hila Tzur", "design", "Design Lead", "Tel Aviv"),
    ("Noa Cohen", "design", "Product Designer", "Tel Aviv"),
    ("Ofer Levi", "sales-il", "Sales Director", "Tel Aviv"),
    ("Lena Hoffmann", "sales-emea", "Head of EMEA Sales", "Berlin"),
    ("Nir Golan", "support-il", "Support Manager", "Tel Aviv"),
    ("Jonas Becker", "support-emea", "Support Lead EMEA", "Berlin"),
    ("Keren Amar", "finance", "Controller", "Tel Aviv"),
    ("Moshe Biton", "finance", "Procurement Manager", "Tel Aviv"),
    ("Sivan Elbaz", "people", "HR Manager", "Tel Aviv"),
    ("Adi Navon", "people", "Office Manager Tel Aviv", "Tel Aviv"),
    ("Rotem Shalev", "people", "Office Manager Haifa", "Haifa"),
    ("Katrin Vogel", "people", "Office Manager Berlin", "Berlin"),
    ("Tal Ben-Ami", "people", "Recruiter", "Tel Aviv"),
    ("Gali Oren", "marketing", "Head of Marketing", "Tel Aviv"),
]

IL_FIRST = ["Avital", "Oren", "Shani", "Eyal", "Liat", "Amit", "Roni", "Yuval", "Noga", "Ido", "Keren",
            "Asaf", "Tamar", "Guy", "Inbal", "Lior", "Neta", "Ohad", "Shir", "Yoav", "Hadar", "Matan",
            "Efrat", "Nimrod", "Michal", "Dor", "Sapir", "Erez", "Galit", "Raz", "Adva", "Barak",
            "Hila", "Omri", "Yarden", "Maor", "Talia", "Shai", "Rotem", "Elad", "Na'ama", "Alon"]
IL_LAST = ["Mizrahi", "Friedman", "Azoulay", "Biton", "Peretz", "Dahan", "Ohana", "Gabay", "Segal",
           "Shapiro", "Katz", "Tal", "Hadad", "Amsalem", "Rubin", "Sharabi", "Ben-Haim", "Nachmias",
           "Erez", "Weiss", "Livne", "Golan", "Harel", "Zur", "Carmi", "Barzilai", "Ashkenazi",
           "Yosef", "Elkayam", "Kaplan", "Sasson", "Navon", "Rosenberg", "Alon", "Doron"]
DE_FIRST = ["Lukas", "Anna", "Felix", "Marie", "Jan", "Sophie", "Tobias", "Laura", "Niklas", "Lea",
            "Moritz", "Hannah", "Paul", "Clara", "Simon", "Julia"]
DE_LAST = ["Schmidt", "Müller", "Fischer", "Wagner", "Becker", "Schulz", "Koch", "Richter", "Klein",
           "Wolf", "Neumann", "Schwarz", "Braun", "Zimmermann", "Hartmann", "Krüger"]

TEAM_TITLES = {
    "core-api": "Software Engineer", "engine": "Software Engineer", "integrations": "Software Engineer",
    "billing": "Software Engineer", "identity": "Software Engineer", "frontend": "Frontend Engineer",
    "data": "Data Engineer", "platform": "Site Reliability Engineer", "security": "Security Engineer",
    "it": "IT Specialist", "product": "Product Manager", "design": "Product Designer",
    "sales-il": "Account Executive", "sales-emea": "Account Executive", "support-il": "Support Engineer",
    "support-emea": "Support Engineer", "finance": "Financial Analyst", "people": "People Partner",
    "marketing": "Marketing Manager",
}

# name, owner_team, tier, data_classification, approved_tool, kind, sensitive (prod/customer/financial)
SYSTEMS = [
    ("flow-api", "core-api", 1, "restricted", False, "service", True),
    ("flow-engine", "engine", 1, "restricted", False, "service", True),
    ("flow-scheduler", "engine", 1, "confidential", False, "service", True),
    ("auth-service", "identity", 1, "restricted", False, "service", True),
    ("billing-service", "billing", 1, "restricted", False, "service", True),
    ("connectors-hub", "integrations", 2, "restricted", False, "service", True),
    ("notifications", "integrations", 2, "confidential", False, "service", True),
    ("web-app", "frontend", 2, "confidential", False, "service", True),
    ("lighthouse", "data", 3, "confidential", False, "service", True),
    ("conveyor", "platform", 2, "internal", False, "platform", False),
    ("kubernetes-prod", "platform", 1, "restricted", False, "platform", True),
    ("aws-production", "platform", 1, "restricted", False, "saas", True),
    ("datadog", "platform", 2, "confidential", False, "saas", False),
    ("pagerduty", "platform", 2, "internal", False, "saas", False),
    ("jira", "it", 3, "internal", True, "saas", False),
    ("confluence", "it", 3, "internal", True, "saas", False),
    ("slack", "it", 3, "internal", True, "saas", False),
    ("google-workspace", "it", 3, "confidential", True, "saas", False),
    ("zoom", "it", 3, "internal", True, "saas", False),
    ("miro", "it", 3, "internal", True, "saas", False),
    ("figma", "design", 3, "internal", True, "saas", False),
    ("github", "platform", 2, "confidential", True, "saas", False),
    ("1password", "it", 2, "restricted", False, "saas", False),
    ("salesforce", "sales-il", 2, "restricted", False, "saas", True),
    ("zendesk", "support-il", 2, "restricted", False, "saas", True),
    ("netsuite", "finance", 2, "restricted", False, "saas", True),
    ("hilan-payroll", "people", 2, "restricted", False, "saas", True),
    ("notion", "design", 3, "internal", False, "saas", False),
]

# FRT targets in minutes (sup-escalation); None = no SLA (community only)
BH, BD = 60, 9 * 60
FRT = {
    "enterprise": {"P1": 30, "P2": 120, "P3": 8 * BH, "P4": 2 * BD},
    "business": {"P1": 60, "P2": 4 * BH, "P3": 1 * BD, "P4": 3 * BD},
    "team": {"P1": 4 * BH, "P2": 1 * BD, "P3": 2 * BD, "P4": 5 * BD},
    "starter": {"P1": None, "P2": None, "P3": None, "P4": None},
}

COMPANY_WORDS = ["Nova", "Blue", "Cedar", "Atlas", "Orbit", "Pine", "Quartz", "River", "Summit", "Vertex",
                 "Harbor", "Lumen", "Maple", "Delta", "Echo", "Falcon", "Granite", "Helix", "Iris", "Juniper"]
COMPANY_SUFFIX = ["Logistics", "Health", "Retail", "Labs", "Foods", "Media", "Finance", "Systems", "Energy",
                  "Studio", "Travel", "Robotics", "Education", "Insurance", "Manufacturing"]


def email_of(name: str) -> str:
    base = name.lower().replace("'", "").replace("ü", "ue").replace("ö", "oe").replace("ä", "ae")
    return base.replace(" ", ".") + "@acme.example"


def route_for(system: tuple, level: str) -> str:
    """SaaS Access Policy v2.1/v2.2 rules; strictest track wins."""
    name, _owner, _tier, _cls, approved, _kind, sensitive = system
    if level == "admin":
        return "needs_security"
    if sensitive:
        return "needs_security"
    if approved:
        if level in ("read", "viewer", "member"):
            return "auto_approve"
        return "needs_manager"  # paid seat / write on team resource
    return "needs_manager"  # not approved, no customer/financial data


def build(rng: random.Random):
    team_by_id = {t[0]: t for t in TEAMS}
    people = []  # dicts
    used = set()
    for name, team, title, loc in FIXED:
        used.add(name)
        people.append({"name": name, "team": team, "title": title, "location": loc})
    for t in TEAMS:
        tid, _n, _d, _lead, _r, loc, hc = t
        have = sum(1 for p in people if p["team"] == tid)
        while have < hc:
            berlin = loc == "Berlin"
            if berlin:
                name = f"{rng.choice(DE_FIRST)} {rng.choice(DE_LAST)}"
                ploc = "Berlin"
            else:
                name = f"{rng.choice(IL_FIRST)} {rng.choice(IL_LAST)}"
                ploc = loc if rng.random() < 0.7 else ("Tel Aviv" if loc == "Haifa" else "Haifa" if tid in ("core-api", "engine", "identity", "data", "platform") else "Tel Aviv")
            if name in used:
                continue
            used.add(name)
            people.append({"name": name, "team": tid, "title": TEAM_TITLES.get(tid, "Specialist"), "location": ploc})
            have += 1
    # stable ordering: execs, then by team order, leads first
    order = {t[0]: i for i, t in enumerate(TEAMS)}
    leads = {t[3] for t in TEAMS}
    people.sort(key=lambda p: (order[p["team"]], 0 if p["name"] in leads else 1, p["name"]))
    for i, p in enumerate(people, start=1):
        p["id"] = f"E{i:03d}"
    by_name = {p["name"]: p for p in people}
    # managers
    for p in people:
        t = team_by_id[p["team"]]
        lead, reports_to = t[3], t[4]
        if p["team"] == "exec":
            if p["name"] == "Yael Shapira":
                p["manager_id"] = None
            elif p["name"] == "Michal Ben-David":
                p["manager_id"] = by_name["Amir Katz"]["id"]
            else:
                p["manager_id"] = by_name["Yael Shapira"]["id"]
        elif p["name"] == lead:
            p["manager_id"] = by_name[reports_to]["id"]
        else:
            p["manager_id"] = by_name[lead]["id"]
        # start dates: leads earlier
        if p["team"] == "exec":
            start = date(2016, 3, 1) + timedelta(days=rng.randint(0, 900))
        elif p["name"] in leads:
            start = date(2017, 1, 1) + timedelta(days=rng.randint(0, 1800))
        else:
            start = date(2019, 1, 1) + timedelta(days=rng.randint(0, 2700))
        p["start_date"] = min(start, date(2026, 10, 15)).isoformat()
        p["email"] = email_of(p["name"])
    if by_name["Yael Shapira"]["start_date"] > "2016-06-01":
        by_name["Yael Shapira"]["start_date"] = "2016-03-01"

    teams = []
    for tid, tname, dept, lead, reports_to, loc, hc in TEAMS:
        teams.append({"id": tid, "name": tname, "department": dept, "lead_id": by_name[lead]["id"],
                      "parent_lead_id": by_name[reports_to]["id"] if reports_to else None,
                      "main_location": loc, "headcount": hc})

    systems = [{"name": s[0], "owner_team": s[1], "tier": s[2], "data_classification": s[3],
                "approved_tool": int(s[4]), "kind": s[5],
                "sensitive": int(s[6])} for s in SYSTEMS]
    sys_by_name = {s[0]: s for s in SYSTEMS}

    # access grants
    security_ids = [by_name[n]["id"] for n in ("Lior Ashkenazi", "Ruth Malka", "Tamar Golan")]
    eng_teams = {"core-api", "engine", "integrations", "billing", "identity", "frontend", "data", "platform"}
    levels_for = {
        "figma": ["viewer", "viewer", "editor"], "github": ["read", "read", "write"],
        "miro": ["member", "member", "editor"],
    }
    grants = []
    seen = set()
    gid = 1
    while len(grants) < 300:
        p = rng.choice(people)
        if p["team"] in eng_teams:
            pool = ["github", "github", "jira", "confluence", "datadog", "pagerduty", "conveyor",
                    "flow-api", "flow-engine", "kubernetes-prod", "aws-production", "lighthouse",
                    "slack", "figma", "notion", "1password", "flow-scheduler", "auth-service",
                    "billing-service", "connectors-hub", "web-app", "notifications"]
        elif p["team"] in ("support-il", "support-emea"):
            pool = ["zendesk", "zendesk", "salesforce", "jira", "confluence", "slack", "zoom", "lighthouse", "miro"]
        elif p["team"] in ("sales-il", "sales-emea"):
            pool = ["salesforce", "salesforce", "zoom", "google-workspace", "slack", "miro", "notion", "figma"]
        elif p["team"] == "finance":
            pool = ["netsuite", "netsuite", "hilan-payroll", "google-workspace", "slack", "jira"]
        elif p["team"] == "people":
            pool = ["hilan-payroll", "google-workspace", "slack", "zoom", "notion", "miro"]
        elif p["team"] in ("design", "product"):
            pool = ["figma", "figma", "miro", "notion", "jira", "confluence", "lighthouse", "github"]
        else:
            pool = [s[0] for s in SYSTEMS]
        sname = rng.choice(pool)
        if (p["id"], sname) in seen:
            continue
        seen.add((p["id"], sname))
        system = sys_by_name[sname]
        if sname in levels_for:
            level = rng.choice(levels_for[sname])
        elif system[5] == "service" or sname in ("kubernetes-prod", "aws-production"):
            level = rng.choice(["read", "read", "write"])
        elif system[4]:  # approved
            level = rng.choice(["member", "member", "member", "read"])
        else:
            level = rng.choice(["member", "read", "write"])
        if rng.random() < 0.04 and (system[1] == p["team"] or p["team"] in ("it", "platform")):
            level = "admin"
        route = route_for(system, level)
        start = date.fromisoformat(p["start_date"])
        lo = max(start, date(2023, 1, 1))
        span = (date(2026, 10, 30) - lo).days
        granted = lo + timedelta(days=rng.randint(0, max(span, 0)))
        if route == "auto_approve":
            approved_by = "system:auto"
        elif route == "needs_manager":
            approved_by = p["manager_id"] or by_name["Yael Shapira"]["id"]
        else:
            approved_by = rng.choice(security_ids)
            if approved_by == p["id"]:
                approved_by = security_ids[0] if p["id"] != security_ids[0] else security_ids[1]
        expires = None
        if route == "needs_security" and granted >= date(2026, 6, 1):
            expires = (granted + timedelta(days=90)).isoformat()  # v2.2: 90-day default
        grants.append({"id": f"G{gid:04d}", "employee_id": p["id"], "system": sname, "level": level,
                       "granted_at": granted.isoformat(), "approved_by": approved_by, "route": route,
                       "expires_at": expires,
                       "policy_version": "2.2" if granted >= date(2026, 6, 1) else "2.1"})
        gid += 1
    grants.sort(key=lambda g: g["granted_at"])
    for i, g in enumerate(grants, start=1):
        g["id"] = f"G{i:04d}"

    # customers
    customers = []
    names = set()
    plans = ["starter"] * 25 + ["team"] * 55 + ["business"] * 45 + ["enterprise"] * 25
    for i, plan in enumerate(plans, start=1):
        while True:
            n = f"{rng.choice(COMPANY_WORDS)} {rng.choice(COMPANY_SUFFIX)}"
            if n not in names:
                names.add(n)
                break
        region = "eu-central-1" if (plan == "enterprise" and rng.random() < 0.35) or (plan == "business" and rng.random() < 0.12) else "il-central-1"
        seats = {"starter": rng.randint(1, 3), "team": rng.randint(3, 60), "business": rng.randint(10, 300),
                 "enterprise": rng.randint(50, 900)}[plan]
        price = {"starter": 0, "team": 12, "business": 29, "enterprise": rng.choice([38, 42, 45, 48])}[plan]
        arr = seats * price * 12
        customers.append({"id": f"CUST-{1000 + i}", "name": n, "plan": plan, "region": region,
                          "seats": seats, "arr_usd": arr,
                          "currency": "EUR" if region == "eu-central-1" else rng.choice(["USD", "USD", "ILS"]),
                          "red_folder": 0})
    for c in sorted(customers, key=lambda c: -c["arr_usd"])[:25]:
        c["red_folder"] = 1

    # tickets
    subjects = {
        "P1": ["Workflows not running", "Cannot log in with SSO", "API returning 500 errors", "All runs stuck in queued"],
        "P2": ["Webhook trigger delayed", "Connector failing intermittently", "Run history not loading", "Invoice amount looks wrong"],
        "P3": ["Question about run limits", "Slack action formatting issue", "How to rotate API key", "Schedule fired at wrong time zone"],
        "P4": ["Feature request: dark mode", "Typo in email template", "Request for SAP connector", "Export run history to CSV"],
    }
    tickets = []
    incident_days = {date(2026, 8, 19): ("P1", "API returning 500 errors", "INC-2026-08-19"),
                     date(2026, 6, 3): ("P2", "Invoice amount looks wrong", "INC-2026-06-03")}
    cust_ids = [c for c in customers]
    for i in range(1, 201):
        c = rng.choice(cust_ids)
        if i <= 14:
            day = date(2026, 8, 19)
        elif i <= 22:
            day = date(2026, 6, 3)
            # billing incident hit EUR customers
            eur = [x for x in customers if x["currency"] == "EUR" and x["plan"] != "starter"]
            c = rng.choice(eur)
        else:
            day = date(2026, 5, 1) + timedelta(days=rng.randint(0, 182))
        if day in incident_days:
            prio, subj, inc = incident_days[day]
            if c["plan"] == "starter":
                c = rng.choice([x for x in customers if x["plan"] != "starter"])
        else:
            prio = rng.choices(["P1", "P2", "P3", "P4"], weights=[6, 22, 47, 25])[0]
            subj = rng.choice(subjects[prio])
            inc = None
        created = datetime(day.year, day.month, day.day, rng.randint(6, 19), rng.randint(0, 59))
        if day == date(2026, 8, 19):
            created = datetime(2026, 8, 19, 14, rng.randint(6, 55))
        target = FRT[c["plan"]][prio]
        base = target if target else 24 * 60
        frt = int(base * rng.uniform(0.15, 1.05)) if rng.random() < 0.88 else int(base * rng.uniform(1.05, 2.5))
        if day == date(2026, 8, 19) and c["plan"] == "enterprise":
            frt = rng.randint(18, 55)
        breached = int(target is not None and frt > target)
        status = rng.choices(["solved", "closed", "pending", "open"], weights=[45, 35, 10, 10])[0]
        if day < date(2026, 10, 1) and status == "open":
            status = "closed"
        team = "support-emea" if c["region"] == "eu-central-1" or c["currency"] == "EUR" else "support-il"
        tickets.append({"id": f"T-{10000 + i}", "customer_id": c["id"], "customer_plan": c["plan"],
                        "subject": subj, "priority": prio, "status": status,
                        "created_at": created.strftime("%Y-%m-%dT%H:%M:00"),
                        "first_response_minutes": frt, "sla_target_minutes": target,
                        "sla_breached": breached, "assigned_team": team,
                        "red_folder": c["red_folder"], "incident_id": inc})
    tickets.sort(key=lambda t: t["created_at"])
    for i, t in enumerate(tickets, start=1):
        t["id"] = f"T-{10000 + i}"

    employees = [{"id": p["id"], "name": p["name"], "email": p["email"], "title": p["title"],
                  "team": p["team"], "manager_id": p["manager_id"], "location": p["location"],
                  "start_date": p["start_date"]} for p in people]
    return {"employees": employees, "teams": teams, "systems": systems, "access_grants": grants,
            "customers": customers, "tickets": tickets}


PROVENANCE = {
    "employees": ("HiBob (Pulse HR portal)", "export_employees_v3", "People Ops nightly export"),
    "teams": ("HiBob (Pulse HR portal)", "export_departments", "team lead taken from org chart field"),
    "systems": ("IT asset register (Google Sheet)", "sheet:systems-register", "owner_team reconciled with Service Catalog 2026-09-15"),
    "access_grants": ("Okta + access-bot audit log", "access_register", "route recorded by the access bot at grant time"),
    "customers": ("Salesforce", "Account", "ARR is annualised list price, not booked revenue"),
    "tickets": ("Zendesk API", "tickets.json", "first_response_minutes computed from first public agent comment"),
}


def write(data: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    db = OUT / "acme.db"
    if db.exists():
        db.unlink()
    con = sqlite3.connect(db)
    schema = {
        "teams": "id TEXT PRIMARY KEY, name TEXT, department TEXT, lead_id TEXT, parent_lead_id TEXT, main_location TEXT, headcount INTEGER",
        "employees": "id TEXT PRIMARY KEY, name TEXT, email TEXT UNIQUE, title TEXT, team TEXT REFERENCES teams(id), manager_id TEXT REFERENCES employees(id), location TEXT, start_date TEXT",
        "systems": "name TEXT PRIMARY KEY, owner_team TEXT REFERENCES teams(id), tier INTEGER, data_classification TEXT, approved_tool INTEGER, kind TEXT, sensitive INTEGER",
        "access_grants": "id TEXT PRIMARY KEY, employee_id TEXT REFERENCES employees(id), system TEXT REFERENCES systems(name), level TEXT, granted_at TEXT, approved_by TEXT, route TEXT, expires_at TEXT, policy_version TEXT",
        "customers": "id TEXT PRIMARY KEY, name TEXT, plan TEXT, region TEXT, seats INTEGER, arr_usd INTEGER, currency TEXT, red_folder INTEGER",
        "tickets": "id TEXT PRIMARY KEY, customer_id TEXT REFERENCES customers(id), customer_plan TEXT, subject TEXT, priority TEXT, status TEXT, created_at TEXT, first_response_minutes INTEGER, sla_target_minutes INTEGER, sla_breached INTEGER, assigned_team TEXT, red_folder INTEGER, incident_id TEXT",
    }
    for table, cols in schema.items():
        rows = data[table]
        # every row also carries its provenance (source system + extraction time)
        con.execute(f"CREATE TABLE {table} ({cols}, _source_system TEXT, _extracted_at TEXT)")
        keys = list(rows[0].keys())
        src = PROVENANCE[table][0]
        con.executemany(
            f"INSERT INTO {table} ({', '.join(keys)}, _source_system, _extracted_at) VALUES ({', '.join('?' * (len(keys) + 2))})",
            [tuple(r[k] for k in keys) + (src, EXTRACTED_AT) for r in rows])
        with open(OUT / f"{table}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(keys + ["_source_system", "_extracted_at"])
            for r in rows:
                w.writerow([("" if r[k] is None else r[k]) for k in keys] + [src, EXTRACTED_AT])
    con.execute("CREATE TABLE provenance (table_name TEXT PRIMARY KEY, source_system TEXT, source_object TEXT, extracted_at TEXT, extracted_by TEXT, row_count INTEGER, notes TEXT)")
    prov_rows = [(t, s, o, EXTRACTED_AT, "build_structured.py", len(data[t]), n) for t, (s, o, n) in PROVENANCE.items()]
    con.executemany("INSERT INTO provenance VALUES (?,?,?,?,?,?,?)", prov_rows)
    with open(OUT / "provenance.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["table_name", "source_system", "source_object", "extracted_at", "extracted_by", "row_count", "notes"])
        w.writerows(prov_rows)
    con.commit()
    con.close()


if __name__ == "__main__":
    d = build(random.Random(SEED))
    write(d)
    for k, v in d.items():
        print(f"{k}: {len(v)}")
