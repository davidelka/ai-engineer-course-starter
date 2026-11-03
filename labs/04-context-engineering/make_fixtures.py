"""Regenerate the lab's synthetic data (deterministic: same output every run).

    python labs/04-context-engineering/make_fixtures.py

Writes:
  data/acme_handbook.md        ~10.5K o200k tokens of Acme handbook sections: offices, teams,
                               per-diem rates, internal systems, procedures. It is the
                               big stable prefix for the caching experiments and the
                               haystack for the position test.
  data/long_conversation.json  a 56-message HR chat in which the employee mentions
                               12 personal facts early on, plus probe questions about them
                               (exercise 6: does compaction keep them?).
All names, codes and numbers are invented.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

LAB = Path(__file__).resolve().parent
DATA = LAB / "data"
R = random.Random(2026)

FIRST = ["Noa", "Yossi", "Rana", "Omer", "Maya", "Ahmad", "Shira", "Daniel", "Lina", "Itai", "Tamar", "Karim",
         "Yael", "Eitan", "Hiba", "Gal", "Nadav", "Salma", "Ruth", "Ori", "Michal", "Fadi", "Avi", "Dana"]
LAST = ["Levi", "Cohen", "Haddad", "Mizrahi", "Peretz", "Abu-Saleh", "Friedman", "Azoulay", "Nasser", "Katz",
        "Biton", "Khoury", "Shapiro", "Amar", "Dahan", "Mansour", "Golan", "Ben-Ami", "Zoabi", "Rosen"]


def person():
    return f"{R.choice(FIRST)} {R.choice(LAST)}"


OFFICES = [("Tel Aviv", "HaArba'a St. 21 (fictional)", 9), ("Haifa", "Matam Park, Building 4 (fictional)", 7),
           ("Beersheba", "Gav-Yam Negev, Tower 2 (fictional)", 5), ("Jerusalem", "Har Hotzvim, Kiryat Mada 9 (fictional)", 4),
           ("Nazareth", "Paulus VI St. 88 (fictional)", 3), ("Herzliya", "Abba Eban Blvd. 10 (fictional)", 6),
           ("Lisbon", "Avenida da Liberdade 190 (fictional)", 3), ("Berlin", "Torstrasse 140 (fictional)", 2),
           ("Austin", "Congress Ave 600 (fictional)", 4)]
TEAMS = ["Payments", "Identity", "Search", "Mobile", "Data Platform", "Billing", "Growth", "Security Operations",
         "IT Helpdesk", "People Operations", "Finance Systems", "Customer Support Tools", "Infrastructure",
         "Machine Learning", "Design Systems", "Legal Ops", "Procurement", "Partner Integrations", "QA Automation",
         "Internal Tools"]
COUNTRIES = [("Germany", "EUR", 170, 55), ("Portugal", "EUR", 140, 45), ("United States", "USD", 260, 75),
             ("United Kingdom", "GBP", 210, 60), ("France", "EUR", 190, 60), ("Netherlands", "EUR", 180, 55),
             ("Japan", "JPY", 26000, 8000), ("India", "INR", 12000, 3500), ("Cyprus", "EUR", 130, 40),
             ("Greece", "EUR", 135, 42), ("Poland", "PLN", 600, 180), ("Canada", "CAD", 250, 70),
             ("Spain", "EUR", 160, 50), ("Italy", "EUR", 170, 52), ("United Arab Emirates", "AED", 900, 250)]
SYSTEMS = ["Ledger", "Beacon", "Atlas", "Harbor", "Quill", "Pulse", "Vault", "Relay", "Compass", "Forge", "Lumen",
           "Tally", "Nimbus", "Orbit", "Prism", "Sentry", "Cobalt", "Juniper", "Mosaic", "Anchor", "Kestrel",
           "Cascade", "Ember", "Signal", "Trellis"]
PURPOSES = ["the general ledger and month-end close", "customer-facing status pages", "the service catalog and ownership map",
            "container image registry", "contract drafting and approvals", "employee engagement surveys",
            "secrets and API key storage", "the outbound email and SMS gateway", "OKR tracking", "CI build runners",
            "the analytics warehouse dashboards", "expense reports and per-diem claims", "the staging cloud accounts",
            "feature flags", "design tokens and the UI component library", "security alerts and on-call paging",
            "the payroll export to the external provider", "the partner API sandbox", "the knowledge base for support agents",
            "the asset inventory of laptops and phones", "load testing", "the data pipeline scheduler",
            "the incident timeline tool", "the internal URL shortener", "the recruiting pipeline"]
CLASSES = ["Public", "Internal", "Confidential", "Restricted"]


def office_section(city, addr, floors):
    rooms = R.sample(["Negev", "Carmel", "Kinneret", "Arava", "Golan", "Yarkon", "Hermon", "Tabor", "Ramon",
                      "Gilboa", "Sharon", "Galil"], 4)
    kitchen = f"{R.choice([7, 8])}:00 to {R.choice([17, 18, 19])}:00"
    lines = [
        f"## Office: {city}",
        f"Address: {addr}. The office occupies {floors} floor{'s' if floors > 1 else ''}; reception is on the first floor.",
        f"Office manager: {person()}. Facilities issues go to the #office-{city.lower().replace(' ', '-')} Slack channel.",
        f"Meeting rooms: {', '.join(rooms)}. Rooms are booked in the calendar; a booking not used within 10 minutes is released.",
        f"The kitchen is stocked from {kitchen}. Dishes left in the sink after 18:00 are thrown away on Thursdays.",
        f"Parking: {R.choice(['12', '20', '35', '8', '50'])} spaces, allocated by a monthly lottery in the HR portal; "
        f"electric vehicle chargers are on level -{R.choice([1, 2])}.",
        f"Guest Wi-Fi network name: Acme-Guest-{city[:3].upper()}. The password rotates weekly and is shown on the reception screen.",
        f"Emergency assembly point: the {R.choice(['north', 'south', 'east', 'west'])} parking lot. "
        f"Fire wardens: {person()} and {person()}.",
        f"Visitors sign in at reception and wear a badge at all times. Contractors need an escort beyond floor 1.",
    ]
    return "\n".join(lines)


def team_section(team):
    lead = person()
    day = R.choice(["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"])
    lines = [
        f"## Team: {team}",
        f"Team lead: {lead}. Slack channel: #team-{team.lower().replace(' ', '-')}. Daily standup at "
        f"{R.choice(['09:30', '09:45', '10:00', '10:15'])} Israel time.",
        f"On-call: a weekly rotation that changes every {day} at 10:00. The on-call engineer must acknowledge a page "
        f"within {R.choice([5, 10, 15])} minutes and is paid an on-call allowance of {R.choice([400, 500, 650])} NIS per week.",
        f"Primary systems: {', '.join(R.sample(SYSTEMS, 3))}. Requests for changes to these systems go through the team's "
        f"intake form, not direct messages.",
        f"Escalation: if the on-call engineer does not respond within 30 minutes, page the team lead, then "
        f"{person()} (engineering manager).",
        f"Planning happens every {R.choice(['two weeks', 'three weeks', 'month'])}; the team publishes its priorities "
        f"in the Compass OKR page.",
    ]
    return "\n".join(lines)


def perdiem_section(country, cur, lodging, meals):
    lines = [
        f"## Per-diem: {country}",
        f"Lodging cap: {lodging:,} {cur} per night, including taxes. Above the cap, the employee pays the difference "
        f"unless the travel approver signed off in advance.",
        f"Meals: a flat {meals:,} {cur} per full travel day, {meals // 2:,} {cur} on the departure and return days. "
        f"No receipts are needed for meals; alcohol is never reimbursed.",
        f"Local transport: public transport and taxis are reimbursed with receipts. Car rental needs prior approval "
        f"and is limited to compact cars.",
        f"Claims are submitted in Tally within {R.choice([30, 45, 60])} days of return.",
    ]
    return "\n".join(lines)


def system_section(name, purpose):
    owner_team = R.choice(TEAMS)
    cls = R.choice(CLASSES)
    access = {"Public": "available to everyone with an Acme account",
              "Internal": "auto-approved for employees, read-only by default",
              "Confidential": "needs manager approval through the access portal",
              "Restricted": "needs Security approval and is reviewed every 90 days"}[cls]
    lines = [
        f"## System: {name}",
        f"{name} is used for {purpose}. Owner: the {owner_team} team; technical contact {person()}.",
        f"Data classification: {cls}. Access is {access}.",
        f"Retention: {R.choice(['90 days', '1 year', '3 years', '7 years'])} for logs and records. "
        f"Backups run {R.choice(['hourly', 'nightly', 'every 6 hours'])} and are kept for 30 days.",
        f"Status and incidents: #sys-{name.lower()} on Slack. Planned maintenance is announced 3 working days ahead.",
    ]
    return "\n".join(lines)


PROCEDURES = [
    ("Laptop replacement", ["Open a ticket in the IT portal with the laptop's asset tag.",
                            "IT checks the warranty and, if needed, orders a replacement within 2 working days.",
                            "Back up local files to the company drive; the old laptop is wiped on return.",
                            "Return the old laptop within 7 days, or its value is deducted from the equipment budget."]),
    ("Expense claim", ["Photograph the receipt on the day of the expense.", "Submit it in Tally with a project code.",
                       "Your manager approves within 5 working days.", "Payment arrives with the next monthly salary."]),
    ("Onboarding week", ["Day 1: equipment pickup at reception at 09:00 and security training.",
                         "Day 2: meet your buddy and set up development tools.", "Day 3: first small task merged.",
                         "Day 5: a 30-minute check-in with your manager and People Operations."]),
    ("Offboarding", ["The manager files the departure in the HR portal at least 14 days ahead.",
                     "Access is removed at 18:00 on the last working day.",
                     "Equipment is returned to IT on the last day.", "An exit interview is offered but optional."]),
    ("Reporting a security incident", ["Do not try to investigate on your own.", "Page Security Operations via #sec-911.",
                                      "Write down what you saw and when.", "Keep the affected device on and connected unless told otherwise."]),
    ("Booking business travel", ["Get your manager's approval in the travel tool.", "Book flights through the travel agency, economy class for flights under 6 hours.",
                                 "Hotels must respect the per-diem lodging cap.", "Share your itinerary in the travel tool for duty of care."]),
    ("Requesting a training budget", ["Every employee has 4,000 NIS per year for courses and conferences.",
                                     "Submit the course link and price in the HR portal.", "Your manager approves; People Operations pays the provider directly.",
                                     "Share a short summary with your team after the course."]),
    ("Parental leave planning", ["Notify your manager and People Operations at least 30 days before the leave.",
                                 "Agree on a handover document.", "Your access stays active during the leave.",
                                 "A return-to-work meeting is scheduled for the first week back."]),
    ("Working from abroad", ["Up to 10 working days per year, with written approval from your department's VP.",
                             "Check the security checklist for the destination country.", "Use the VPN at all times.",
                             "Log the days in the HR portal."]),
    ("Equipment for home office", ["A one-time allowance of 1,500 NIS for chair, desk or screen.",
                                   "Claim it in Tally within 60 days of purchase.", "Items above 1,500 NIS need manager approval.",
                                   "The equipment remains yours after 24 months."]),
]


def procedure_section(title, steps):
    return "\n".join([f"## Procedure: {title}"] + [f"{i}. {s}" for i, s in enumerate(steps, 1)])


def handbook() -> str:
    parts = ["# Acme Ltd. Employee Handbook (synthetic, for the course)",
             "This handbook collects practical information about Acme's offices, teams, travel, internal systems "
             "and everyday procedures. HR policies (vacation, remote work, sick leave) live in separate documents."]
    parts += [office_section(*o) for o in OFFICES]
    parts += [team_section(t) for t in TEAMS]
    parts += [perdiem_section(*c) for c in COUNTRIES]
    parts += [system_section(n, p) for n, p in zip(SYSTEMS, PURPOSES)]
    parts += [procedure_section(t, s) for t, s in PROCEDURES]
    return "\n\n".join(parts) + "\n"


# ---------------------------------------------------------------- the long conversation
FACTS = [
    ("What is my employee ID?", "A-4471", "Hi! I just joined Acme. My employee ID is A-4471, in case you need it."),
    ("What is my start date?", "12 January", "My official start date is 12 January, and I'm in the Payments team."),
    ("Who is my manager?", "Yossi Levi", "My manager is Yossi Levi. He asked me to sort out HR questions with you."),
    ("Which city do I live in?", "Beersheba", "I live in Beersheba, so I'll mostly work from the Beersheba office."),
    ("What food allergy did I mention?", "sesame", "Also, I have a sesame allergy, which matters for team lunches."),
    ("What is my partner's due date?", "3 May", "My partner is due on 3 May, so I'll need parental leave around then."),
    ("What laptop screen size did I ask for?", "14-inch", "For equipment, I'd prefer a 14-inch laptop, I travel a lot."),
    ("How many years did I work at my previous company?", "6 years", "I worked 6 years at my previous company, Orbitron."),
    ("Which conference do I want to attend?", "PyCon Israel", "I'd love to attend PyCon Israel in June with the training budget."),
    ("What is my scope of employment?", "80%", "I'm employed at an 80% scope, four days a week."),
    ("Which day did I say I do not work?", "Thursday", "My day off each week is Thursday."),
    ("What is my car's license plate?", "52-718-34", "My car's plate is 52-718-34, for the parking lottery."),
]
FILLER_Q = [
    ("How many vacation days do new employees get?", "In the first year, full-time employees receive 14 paid vacation days, "
     "and the allowance grows by one day per year of service up to 24. Part-time employees get a proportional amount."),
    ("Can I carry unused days over?", "Yes, up to 5 unused days carry over to the next calendar year and expire on March 31."),
    ("What are the office days?", "Tuesday and Wednesday are office days for all teams; you can work remotely up to 2 days a week."),
    ("How do I claim the home office allowance?", "Acme gives a one-time 1,500 NIS allowance; claim it in the expense system within 60 days of the purchase."),
    ("Who approves working from abroad?", "Remote work from abroad needs written approval from your department's VP, up to 10 working days a year."),
    ("What are core hours?", "Be reachable on Slack between 10:00 and 16:00 Israel time."),
    ("How do vacation requests work?", "Requests of 3 days or more go through the HR portal at least 2 weeks ahead, approved by your direct manager."),
    ("Is there a shutdown week?", "Yes, between Rosh Hashanah and Yom Kippur; 3 vacation days are deducted automatically."),
]


def conversation() -> dict:
    msgs = []
    # facts first (early turns), each followed by an assistant acknowledgement
    for _, _, statement in FACTS:
        msgs.append({"role": "user", "content": statement})
        msgs.append({"role": "assistant", "content": "Thanks, noted. " + R.choice([
            "Let me know what you'd like to know about Acme's policies.",
            "I'll keep that in mind for your questions.",
            "Is there an HR policy question I can help with?"])})
    # then many filler policy questions with long-ish answers
    for q, a in FILLER_Q * 2:
        msgs.append({"role": "user", "content": q})
        msgs.append({"role": "assistant", "content": a + " " + R.choice([
            "The full details are in the policy document in the HR portal.",
            "If your situation is unusual, write to hr@acme.example.",
            "Your manager can also help with the practical side."])})
    probes = [{"question": q, "answer": a} for q, a, _ in FACTS]
    return {"messages": msgs, "probes": probes,
            "note": "Facts appear in the first 24 messages; messages 25-56 are policy small talk."}


def main() -> None:
    DATA.mkdir(exist_ok=True)
    (DATA / "acme_handbook.md").write_text(handbook(), encoding="utf-8")
    (DATA / "long_conversation.json").write_text(json.dumps(conversation(), indent=1, ensure_ascii=False) + "\n",
                                                 encoding="utf-8")
    print("wrote", DATA / "acme_handbook.md", "and", DATA / "long_conversation.json")


if __name__ == "__main__":
    main()
