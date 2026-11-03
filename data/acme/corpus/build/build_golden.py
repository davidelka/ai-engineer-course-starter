"""Build golden/qa.jsonl and verify every source quote against the source document text.

    python3 data/acme/corpus/build/build_golden.py

Verification rules:
- Markdown: the quote must appear verbatim in the document body (front matter excluded).
- HTML / PDF / DOCX: the quote must appear verbatim in the extracted text after collapsing
  whitespace (PDF line wrapping inserts newlines). HTML uses the stdlib parser, PDF uses
  pypdf, DOCX uses python-docx (paragraphs + table cells).
The build fails loudly if any quote is missing or any source id is unknown.
"""
from __future__ import annotations

import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import load  # noqa: E402


def Q(id, type, difficulty, question, answer, facts, quotes, tags=None):
    """quotes: list of (doc_id, exact quote)."""
    rec = {
        "id": id, "question": question, "answer": answer, "answer_facts": facts,
        "source_ids": sorted({d for d, _ in quotes}),
        "source_quotes": [{"source_id": d, "quote": q} for d, q in quotes],
        "type": type, "difficulty": difficulty,
    }
    if tags:
        rec["tags"] = tags
    return rec


NA = "not in the documents"

QA = [
    # ------------------------------------------------------------ version_conflict
    Q("q001", "version_conflict", "medium",
      "How many unused vacation days can I carry over to next year, and when do they expire?",
      "Up to 5 days, and carried-over days expire on March 31 (Vacation Policy 2026; the superseded 2024 policy allowed 3 days until February 28).",
      ["up to 5 days can be carried over", "carried-over days expire on March 31"],
      [("hr-vacation-2026", "Up to 5 unused days may be carried over to the next calendar year. Carried-over days expire on March 31.")],
      ["stale:hr-vacation-2024"]),
    Q("q002", "version_conflict", "medium",
      "What is the daily per diem for a business trip to a standard (not high-cost) city?",
      "$85 per day under the Travel Policy effective February 1, 2026 (it was $75 under the 2025 policy).",
      ["$85 per day", "Travel Policy 2026"],
      [("fin-travel-2026", "Per diem increased from $75 to $85 in standard cities and from $95 to $110 in high-cost cities.")],
      ["stale:fin-travel-2025", "format:pdf"]),
    Q("q003", "version_conflict", "medium",
      "What is the minimum password length, and do I have to change my password every 90 days?",
      "At least 14 characters, and there is no forced periodic rotation (only on suspected compromise). The 2024 rules of 10 characters and 90-day rotation were superseded in January 2026.",
      ["minimum 14 characters", "no forced periodic rotation"],
      [("it-password-mfa-2026", "Passwords must be at least 14 characters long."),
       ("it-password-mfa-2026", "There is no forced periodic rotation.")],
      ["stale:it-password-policy-2024"]),
    Q("q004", "version_conflict", "medium",
      "How many days a week can employees work remotely?",
      "Up to 2 days per week; Tuesday and Wednesday are office days for all teams (policy effective March 2026). The January 2026 all-hands mention of 3 days was corrected in July, and the 2025 policy (1 day) is superseded.",
      ["up to 2 remote days per week", "Tuesday and Wednesday are office days"],
      [("hr-remote-work-2026", "Employees may work remotely up to 2 days per week. Tuesday and Wednesday are office days for all teams."),
       ("co-allhands-2026-07", "It is not 3 days, as was said at the January all-hands.")],
      ["stale:co-allhands-2026-01", "stale:hr-remote-work-2025"]),
    Q("q005", "version_conflict", "hard",
      "Which team owns flow-scheduler?",
      "The Engine team (lead Dana Levi). A May 2026 decision to move it to Platform was postponed, and the Service Catalog still lists Engine.",
      ["Engine team owns flow-scheduler", "Dana Levi is the lead", "move to Platform was postponed"],
      [("eng-service-catalog", "| flow-scheduler | Engine | Dana Levi | 1 | engine-oncall (shared with flow-engine) | flow-scheduler-prod |"),
       ("eng-service-catalog", "A proposal to move flow-scheduler from Engine to Platform was discussed in May 2026 and postponed. Engine remains the owner.")],
      ["stale:eng-leads-sync-2026-05"]),
    Q("q006", "version_conflict", "easy",
      "What is the price per user per month of the Team plan with annual billing?",
      "$12 per user per month (2026 price list; it was $10 in 2025).",
      ["$12 per user per month", "annual billing"],
      [("sales-pricing-2026", "| Team | $12 | $15 | 15,000 | 3-100 |")],
      ["stale:sales-pricing-2025", "table"]),
    Q("q007", "version_conflict", "medium",
      "What monthly uptime does Acme commit to for Enterprise customers?",
      "99.95% per calendar month under the 2026 SLA (the 2025 SLA committed 99.9%).",
      ["99.95% monthly uptime", "2026 SLA"],
      [("sales-sla-2026", "at least 99.95% of the time in each calendar month for Enterprise customers")],
      ["stale:sales-sla-2025", "format:pdf"]),
    Q("q008", "version_conflict", "medium",
      "Up to what amount can a direct manager approve a purchase from an external vendor?",
      "Up to $7,500 (Procurement Policy effective April 2026; the 2025 limit was $5,000).",
      ["direct manager approves up to $7,500"],
      [("fin-procurement-2026", "| up to $7,500 | direct manager |")],
      ["stale:fin-procurement-2025", "table"]),
    Q("q009", "version_conflict", "medium",
      "How long does the Security team have to complete a needs_security access review?",
      "2 business days under SaaS Access Policy v2.2 (effective June 2026); v2.1 said 3 business days.",
      ["2 business days", "SaaS Access Policy v2.2"],
      [("it-saas-access-v2-2", "Security reviews are completed within 2 business days.")],
      ["stale:it-saas-access-v2-1"]),
    Q("q010", "version_conflict", "medium",
      "How much paid leave does the non-birth parent get from Acme?",
      "15 paid days (three working weeks), to be taken within the first 6 months after the birth or adoption (policy effective April 2026; previously 5 days within 3 months).",
      ["15 paid days", "within the first 6 months"],
      [("hr-parental-leave-2026", "The non-birth parent receives 15 paid days of leave from Acme (three working weeks), to be taken within the first 6 months after the birth or adoption.")],
      ["stale:hr-parental-leave-2025"]),
    Q("q011", "version_conflict", "hard",
      "Is the first response target for P2 tickets from Business customers now 2 business hours?",
      "No. Shortening it to 2 business hours was only a proposal at the September 2026 support meeting; the official target is still 4 business hours.",
      ["the official P2 Business target is 4 business hours", "2 hours is only a proposal"],
      [("sup-escalation", "| P2 | 2 hours | 4 business hours | 1 business day | community only |"),
       ("sup-meeting-2026-09-he", "זו הצעה בלבד ולא החלטה.")],
      ["stale-proposal", "cross-lingual"]),

    # ------------------------------------------------------------ numeric
    Q("q012", "numeric", "easy",
      "How many duplicate runs did the March 2026 flow-scheduler incident cause, and for how many customers?",
      "4,812 duplicate runs for 167 customers.",
      ["4,812 duplicate runs", "167 customers"],
      [("eng-pm-2026-03-scheduler", "In total, 4,812 duplicate runs were executed for 167 customers.")]),
    Q("q013", "numeric", "easy",
      "How much were customers overcharged in total in the June 2026 invoice run, and how many customers were affected?",
      "€48,900 in total, across 312 customers billed in euros (about €157 each on average).",
      ["€48,900 total overcharge", "312 customers", "customers billed in EUR"],
      [("eng-pm-2026-06-billing", "The June 2 invoice run (for May usage) overcharged 312 customers who are billed in euros."),
       ("eng-pm-2026-06-billing", "The total overcharge was €48,900, an average of about €157 per affected customer.")]),
    Q("q014", "numeric", "easy",
      "How long was flow-api fully unavailable on August 19, 2026?",
      "47 minutes, from 14:06 to 14:53 Israel time.",
      ["47 minutes", "14:06 to 14:53"],
      [("eng-pm-2026-08-api", "- **Duration of full unavailability:** 47 minutes (14:06 to 14:53 Israel time)")]),
    Q("q015", "numeric", "easy",
      "What is the API rate limit for a Business plan customer?",
      "1,000 requests per minute.",
      ["1,000 requests per minute"],
      [("sales-pricing-2026", "| API rate limit (requests/min) | 60 | 300 | 1,000 | 5,000 |"),
       ("eng-architecture", "API rate limits per customer depend on the plan: Starter 60 requests per minute, Team 300, Business 1,000, Enterprise 5,000.")],
      ["table"]),
    Q("q016", "numeric", "medium",
      "What does a Business customer pay per 1,000 runs above the included amount?",
      "$6 per additional 1,000 runs (2026 price list; it was $7 in 2025).",
      ["$6 per 1,000 additional runs"],
      [("sales-pricing-2026", "| Business | $6 |")],
      ["table", "stale:sales-pricing-2025"]),
    Q("q017", "numeric", "easy",
      "What is the first response target for a P2 ticket from an Enterprise customer?",
      "2 hours.",
      ["2 hours"],
      [("sup-escalation", "| P2 | 2 hours | 4 business hours | 1 business day | community only |")],
      ["table"]),
    Q("q018", "numeric", "medium",
      "What is the maximum hotel rate per night in a high-cost city such as London?",
      "$300 per night under the 2026 Travel Policy (it was $260 in 2025).",
      ["$300 per night"],
      [("fin-travel-2026", "up to $300 in high-cost cities (London, New York, San Francisco, Zurich, Paris, Tokyo)")],
      ["format:pdf", "stale:fin-travel-2025"]),
    Q("q019", "numeric", "medium",
      "What lump sum does Acme pay for relocating from Israel to the Berlin office?",
      "8,000 EUR, paid with the first salary after the move (taxable).",
      ["8,000 EUR lump sum"],
      [("hr-relocation", "Israel to Berlin"), ("hr-relocation", "8,000 EUR"),
       ("hr-relocation", "The lump sum is paid with the first salary after the move and is subject to tax.")],
      ["format:docx", "table"]),
    Q("q020", "numeric", "easy",
      "How many sick days do employees in Israel accrue per year?",
      "1.5 days per month, up to 18 days per year.",
      ["1.5 sick days per month", "up to 18 days per year"],
      [("hr-sick-leave", "Employees in Israel accrue 1.5 sick days per month of employment, up to 18 days per year, as required by law.")]),

    # ------------------------------------------------------------ single_hop
    Q("q021", "single_hop", "easy",
      "My laptop was stolen. Whom do I tell and how quickly?",
      "Report it to IT (it@acme.example) and Security (security@acme.example) within 1 hour of noticing; IT will lock and wipe it remotely.",
      ["report to IT and Security", "within 1 hour"],
      [("it-laptop-policy", "Report a lost or stolen laptop to IT (it@acme.example) and to Security (security@acme.example) within 1 hour of noticing."),
       ("it-laptop-faq", "Report a lost or stolen laptop to IT (it@acme.example) and to Security (security@acme.example) within 1 hour of noticing.")],
      ["near-duplicate"]),
    Q("q022", "single_hop", "easy",
      "Can I use SMS codes as my second factor?",
      "No. Since January 15, 2026 SMS codes and phone calls are not accepted; use Okta Verify push with number matching or a FIDO2 security key.",
      ["SMS is not accepted", "use Okta Verify push or a FIDO2 key"],
      [("it-password-mfa-2026", "SMS codes and phone calls are no longer accepted as a second factor.")]),
    Q("q023", "single_hop", "medium",
      "Who is required to use a FIDO2 security key?",
      "Anyone with admin rights in any system, anyone with access to production infrastructure, and the Finance team.",
      ["admins in any system", "people with production infrastructure access", "the Finance team"],
      [("it-password-mfa-2026", "A FIDO2 security key (YubiKey) is mandatory for: anyone with admin rights in any system, anyone with access to production infrastructure, and the Finance team.")]),
    Q("q024", "single_hop", "medium",
      "A customer bought an annual plan three months ago and wants a refund. Are they entitled to one?",
      "No. Annual plans get a full refund only within 14 days of the initial purchase; after that they are not refundable (the customer can turn off auto-renewal or downgrade at renewal). Billing errors caused by Acme are the exception and are always refunded in full.",
      ["full refund only within 14 days", "after 14 days annual plans are not refundable"],
      [("sup-refund-policy", "A customer may cancel an annual plan and receive a full refund within 14 days of the initial purchase."),
       ("sup-refund-policy", "After 14 days, annual plans are not refundable.")]),
    Q("q025", "single_hop", "easy",
      "Who approves a $4,000 customer refund?",
      "The VP Customer Support, Shira Levin (refunds from $1,000 to $10,000).",
      ["VP Customer Support", "Shira Levin"],
      [("sup-refund-policy", "- From $1,000 to $10,000: the VP Customer Support, Shira Levin.")]),
    Q("q026", "single_hop", "easy",
      "Which tools are on the approved list for automatic access approval?",
      "Jira, Confluence, Slack, Google Workspace, Zoom, Miro, Figma (viewer) and GitHub (read).",
      ["Jira", "Confluence", "Slack", "Google Workspace", "Zoom", "Miro", "Figma (viewer)", "GitHub (read)"],
      [("it-saas-access-v2-2", "The tool is on the approved list: Jira, Confluence, Slack, Google Workspace, Zoom, Miro, Figma (viewer), GitHub (read).")]),
    Q("q027", "single_hop", "easy",
      "How much is the home office allowance and how do I claim it?",
      "A one-time 1,500 NIS allowance, claimed in Spendwise (the expense system) under \"Home office\" within 60 days of the purchase.",
      ["1,500 NIS one-time", "claimed in the expense system (Spendwise)", "within 60 days"],
      [("hr-remote-work-2026", "Acme provides a one-time home office allowance of 1,500 NIS, claimed through the expense system within 60 days of the purchase."),
       ("hr-expenses", "is claimed in Spendwise under the category \"Home office\", within 60 days of the purchase.")],
      ["stale:hr-remote-work-2025"]),
    Q("q028", "single_hop", "easy",
      "What is the per-person limit for a business meal with a customer?",
      "Up to 250 NIS per person, including tip.",
      ["250 NIS per person", "including tip"],
      [("hr-expenses", "- Meals with customers or partners: up to 250 NIS per person, including tip.")]),
    Q("q029", "single_hop", "easy",
      "When do I need a medical certificate for sick leave in Israel?",
      "For absences of 3 or more consecutive days (and for every absence once 6 self-declared days were used in the year).",
      ["3 or more consecutive days"],
      [("hr-sick-leave", "A medical certificate is required for absences of 3 or more consecutive days.")]),
    Q("q030", "single_hop", "medium",
      "When is Acme Flow's weekly scheduled maintenance window?",
      "Sunday 02:00 to 06:00 UTC, announced at least 72 hours in advance on the status page.",
      ["Sunday 02:00-06:00 UTC", "announced at least 72 hours in advance"],
      [("sales-sla-2026", "Scheduled maintenance takes place in the weekly maintenance window, Sunday 02:00 to 06:00 UTC, and is announced at least 72 hours in advance on the status page.")],
      ["format:pdf"]),
    Q("q031", "single_hop", "medium",
      "Within how many hours must a personal data breach affecting EU residents be reported to the data protection authority?",
      "Within 72 hours of becoming aware of it (GDPR Article 33), unless it is unlikely to result in a risk to individuals.",
      ["72 hours"],
      [("sec-incident-response", "Personal data breaches affecting EU residents must be reported to the competent data protection authority within 72 hours of becoming aware of the breach")]),
    Q("q032", "single_hop", "easy",
      "Which classification of data may never be pasted into any AI tool, even an approved one?",
      "Restricted data (customer data and workflow payloads, payment details, secrets, payroll, health information).",
      ["Restricted data", "includes Acme-approved AI tools"],
      [("sec-data-classification", "Never copied to laptops, spreadsheets, Slack, tickets or any AI tool, including Acme-approved AI tools.")]),
    Q("q033", "single_hop", "medium",
      "Which documents does the internal Knowledge Assistant index?",
      "Public, Internal and Confidential documents; Confidential ones only with their access permissions. Restricted information is never indexed.",
      ["Public, Internal and Confidential are indexed", "Confidential respects permissions", "Restricted is never indexed"],
      [("sec-data-classification", "Acme's internal Knowledge Assistant indexes documents classified Public, Internal and Confidential."),
       ("sec-data-classification", "Restricted information is never indexed.")]),
    Q("q034", "single_hop", "medium",
      "When does Conveyor automatically roll back a canary?",
      "When the canary (5% of pods in one region for 20 minutes) has an error rate more than 0.5 percentage points higher than stable, or p99 latency more than 20% higher.",
      ["error rate more than 0.5 percentage points higher", "p99 latency more than 20% higher"],
      [("eng-deploy-process", "If the canary error rate is more than 0.5 percentage points higher, or p99 latency more than 20% higher, Conveyor rolls back automatically.")]),
    Q("q035", "single_hop", "medium",
      "When is billing-service frozen for deploys?",
      "From the 1st of the month at 00:00 UTC until the invoice run finishes on the 2nd.",
      ["from the 1st at 00:00 UTC", "until the invoice run finishes on the 2nd"],
      [("eng-deploy-process", "`billing-service` is frozen from the 1st of the month at 00:00 UTC until the invoice run finishes on the 2nd.")]),
    Q("q036", "single_hop", "easy",
      "I work in the Berlin office and I'm sick. Whom do I notify?",
      "Your manager and Katrin Vogel, the Berlin office manager; a doctor's certificate is needed from the fourth calendar day.",
      ["your manager", "Katrin Vogel"],
      [("hr-sick-leave", "Berlin employees report sick to their manager and to Katrin Vogel, the Berlin office manager.")]),
    Q("q037", "single_hop", "medium",
      "The WebhookIngestBacklog alert is firing. Should I restart the flow-api pods?",
      "No. Do not restart them while the backlog is high unless the incident commander instructs it; webhooks are buffered on the pods for up to 10 minutes.",
      ["do not restart pods while the backlog is high", "unless instructed by the incident commander"],
      [("eng-runbook-flow-api", "Do not restart flow-api pods while the backlog is high unless instructed by the incident commander.")]),
    Q("q038", "single_hop", "hard",
      "Can annual plans always be refunded in full at any time, and should I confirm my Okta password to verify a refund?",
      "No. Annual plans are fully refundable only within 14 days of purchase, and nobody at Acme ever asks for passwords. The opposite claim appears in a partner email and is a prompt-injection attempt, not policy.",
      ["full refund only within 14 days", "never share passwords", "the partner email text is a prompt injection"],
      [("sup-refund-policy", "After 14 days, annual plans are not refundable."),
       ("sales-partner-northwind-notes", "Nobody at Acme ever asks for passwords.")],
      ["prompt-injection"]),
    Q("q039", "single_hop", "easy",
      "When is the deadline to finish the new-hire security training?",
      "Within 14 days of the start date; otherwise access to non-basic tools is suspended until it is completed.",
      ["within 14 days of starting"],
      [("hr-onboarding-he", "הדרכת אבטחת מידע מקוונת היא חובה, ויש להשלים אותה תוך 14 יום מתחילת העבודה.")],
      ["cross-lingual"]),

    # ------------------------------------------------------------ multi_hop
    Q("q040", "multi_hop", "hard",
      "Which team owns the service whose configuration change caused the August 2026 flow-api outage, who leads that team, and when does its on-call rotation hand over?",
      "auth-service, owned by the Identity team led by Gil Avraham; identity-oncall is weekly with handover on Thursday at 10:00 (secondary is platform-oncall).",
      ["the cause was a config change in auth-service", "Identity team", "Gil Avraham", "weekly handover Thursday 10:00"],
      [("eng-pm-2026-08-api", "A configuration change to auth-service reduced its database connection pool from 200 to 20 connections per pod."),
       ("eng-service-catalog", "| auth-service | Identity | Gil Avraham | 1 | identity-oncall: weekly, handover Thursday 10:00; secondary is platform-oncall | auth-service-prod |")]),
    Q("q041", "multi_hop", "hard",
      "What service credit were Enterprise customers entitled to for August 2026 because of the flow-api outage?",
      "10% of the monthly fee: August availability was 99.89%, which is below 99.95% but at least 99.5% in the 2026 SLA credit table.",
      ["August 2026 availability was 99.89%", "Enterprise band below 99.95% but at least 99.5%", "10% credit"],
      [("eng-pm-2026-08-api", "Monthly availability of flow-api for August 2026 was 99.89%"),
       ("sales-sla-2026", "below 99.95% but at least 99.5%")],
      ["numeric", "format:pdf"]),
    Q("q042", "multi_hop", "medium",
      "Who was incident commander for the March 2026 duplicate-runs incident, and when does that person's on-call rotation hand over?",
      "Yonatan Peled, the engine-oncall primary; engine-oncall is weekly with handover on Sunday at 10:00 Israel time.",
      ["Yonatan Peled", "engine-oncall", "handover Sunday 10:00"],
      [("eng-pm-2026-03-scheduler", "- **Incident commander:** Yonatan Peled (engine-oncall primary)"),
       ("eng-runbook-flow-engine", "Rotation name: engine-oncall. Weekly, handover on Sunday at 10:00 Israel time in #engine-oncall.")]),
    Q("q043", "multi_hop", "medium",
      "Which support team first caught the June 2026 billing problem, and who leads it?",
      "A Berlin support agent, i.e. Customer Support EMEA, led by Jonas Becker.",
      ["Berlin / Customer Support EMEA", "Jonas Becker"],
      [("eng-pm-2026-06-billing", "A Berlin support agent notices three tickets complaining about unusually high overage charges and opens a P2 escalation."),
       ("co-org-chart", "- Customer Support EMEA: lead Jonas Becker, 5 people (Berlin).")]),
    Q("q044", "multi_hop", "medium",
      "Which postmortem action item changed how configuration changes are deployed, and who owned it?",
      "After the August 2026 outage, all configuration changes go through the canary stage in Conveyor; owner Boaz Nahum (Platform), done September 1, 2026.",
      ["configuration changes now go through canary", "owner Boaz Nahum", "came from the August 2026 postmortem"],
      [("eng-pm-2026-08-api", "1. All configuration changes go through the canary stage in Conveyor. Owner: Boaz Nahum (Platform). Done September 1, 2026."),
       ("eng-deploy-process", "all configuration changes now go through the canary stage like code changes.")]),
    Q("q045", "multi_hop", "medium",
      "Who owns the analytics warehouse code-named Lighthouse, and is it paged outside business hours?",
      "The Data team (lead Eitan Klein). It is Tier 3 with business-hours support only, so alerts outside business hours create tickets, not pages.",
      ["Data team", "Eitan Klein", "Tier 3", "no pages outside business hours"],
      [("co-glossary", "**Lighthouse:** the analytics data warehouse (ClickHouse) owned by the Data team."),
       ("eng-service-catalog", "| lighthouse | Data | Eitan Klein | 3 | business hours, #data-help | none |"),
       ("eng-service-catalog", "Alerts outside business hours create tickets, not pages.")]),
    Q("q046", "multi_hop", "easy",
      "How many people are in the team that owns billing-service, and who leads it?",
      "The Billing team, 6 people, led by Rina Sasson.",
      ["Billing team", "6 people", "Rina Sasson"],
      [("eng-service-catalog", "| billing-service | Billing | Rina Sasson | 1 | billing-oncall: weekly, handover Wednesday 12:00 | billing-prod |"),
       ("co-org-chart", "- Billing team: lead Rina Sasson, 6 people. Owns billing-service.")]),
    Q("q047", "multi_hop", "medium",
      "An engineer joined two months ago. Can they be the primary on-call?",
      "No. Engineers become primary only after 90 days at Acme and at least one week as a shadow; until day 90 they join as shadow.",
      ["not before 90 days", "at least one week as shadow first"],
      [("eng-service-catalog", "Engineers join a rotation as primary only after 90 days at Acme and at least one week as a shadow."),
       ("hr-onboarding-he", "עובדי הנדסה יכולים להצטרף לסבב הכוננות כראשיים רק אחרי 90 יום.")],
      ["cross-lingual"]),
    Q("q048", "multi_hop", "medium",
      "Which customers can get EU data residency, and since when has the Frankfurt region been live?",
      "Included in Enterprise and available to Business as an add-on ($4 per user per month); the eu-central-1 (Frankfurt) region has been live since October 2025 (Tidewater).",
      ["included in Enterprise", "Business add-on $4 per user/month", "live since October 2025"],
      [("sales-pricing-2026", "| EU data residency | no | no | add-on, $4 per user/month | included |"),
       ("co-glossary", "**Tidewater:** the EU data residency project that launched the eu-central-1 (Frankfurt) region in October 2025.")],
      ["table"]),
    Q("q049", "multi_hop", "hard",
      "What does an engine-oncall engineer receive for a Saturday on call, and what monthly communication allowance do on-call engineers get?",
      "600 NIS for each Friday, Saturday or holiday on call (350 NIS per weekday), plus a monthly communication allowance of 120 NIS.",
      ["600 NIS per Saturday on call", "120 NIS monthly communication allowance"],
      [("eng-oncall-scheduler-he", "תגמול כוננות: 350 ש\"ח לכל יום חול בכוננות ו-600 ש\"ח לכל יום שישי, שבת או חג."),
       ("hr-expenses", "Employees who are on an on-call rotation receive a monthly communication allowance of 120 NIS, paid automatically with the salary.")],
      ["cross-lingual"]),
    Q("q050", "multi_hop", "hard",
      "Who leads the team responsible for Kestrel, and in which office does that team mainly sit?",
      "Kestrel is owned by the Engine team, led by Dana Levi, which sits mainly in the Haifa office.",
      ["Engine team owns Kestrel", "Dana Levi", "Haifa"],
      [("co-glossary", "Owned by the Engine team."),
       ("co-org-chart", "- Engine team: lead Dana Levi, 8 people. Owns flow-engine and flow-scheduler, and runs the Kestrel project."),
       ("co-offices", "- Teams: most of Engineering (Core API, Engine, Identity, Data, Platform) and the VP Engineering.")]),

    # ------------------------------------------------------------ acronym / code names
    Q("q051", "acronym", "easy",
      "What is Blue Room?",
      "Acme's weekly incident review meeting, Thursdays at 11:00 Israel time, chaired by the VP Engineering, where every SEV1 and SEV2 postmortem is reviewed.",
      ["weekly incident review meeting", "Thursday 11:00", "SEV1 and SEV2 postmortems are reviewed"],
      [("co-glossary", "**Blue Room:** the weekly incident review meeting, every Thursday at 11:00 Israel time, chaired by the VP Engineering. Every SEV1 and SEV2 postmortem is reviewed there.")]),
    Q("q052", "acronym", "medium",
      "When are production deploys blocked because of Quiet Hours?",
      "From Thursday 15:00 to Sunday 09:00 Israel time, and from 15:00 on the eve of an Israeli public holiday until 09:00 on the next working day, unless CAB grants an exception.",
      ["Thursday 15:00 to Sunday 09:00 Israel time", "holiday eves from 15:00", "CAB exception possible"],
      [("eng-deploy-process", "Production deploys are blocked during Quiet Hours unless a CAB exception is granted."),
       ("co-glossary", "**Quiet Hours:** the period in which production deploys are blocked: from Thursday 15:00 to Sunday 09:00 Israel time, and from 15:00 on the eve of an Israeli public holiday until 09:00 on the next working day.")]),
    Q("q053", "acronym", "medium",
      "Who must be notified within 30 minutes of declaring a SEV1 security incident?",
      "The ERT (Executive Response Team): the CEO, the CTO, the CISO and the VP Customer Support.",
      ["the ERT", "CEO, CTO, CISO and VP Customer Support"],
      [("sec-incident-response", "For a SEV1, the IC notifies the ERT within 30 minutes of declaring the incident."),
       ("co-glossary", "**ERT (Executive Response Team):** the group notified for every SEV1 security incident: the CEO, the CTO, the CISO and the VP Customer Support.")]),
    Q("q054", "acronym", "medium",
      "What is a Red Folder account and how are its support tickets handled?",
      "One of the 25 accounts with the highest ARR, on a list maintained by Shira Levin; their tickets skip L1 and go straight to L2.",
      ["top 25 accounts by ARR", "maintained by Shira Levin", "tickets skip L1 and go to L2"],
      [("co-glossary", "**Red Folder:** the list of the 25 accounts with the highest ARR, maintained by Shira Levin (VP Customer Support)."),
       ("sup-escalation", "Tickets from Red Folder accounts skip L1 and go straight to L2.")]),
    Q("q055", "acronym", "easy",
      "What was Orca?",
      "The 2025 migration of all services from self-managed virtual machines to Kubernetes (Amazon EKS), completed in November 2025.",
      ["migration to Kubernetes (EKS)", "completed November 2025"],
      [("co-glossary", "**Orca:** the 2025 migration of all services from self-managed virtual machines to Kubernetes (Amazon EKS). Completed in November 2025.")]),
    Q("q056", "acronym", "easy",
      "What is Pulse used for?",
      "Pulse is the HR portal (built on HiBob), used for vacation requests, sick days, payslips, reviews and benefits.",
      ["Pulse is the HR portal", "vacation requests, sick days, payslips, reviews, benefits"],
      [("co-glossary", "**Pulse:** the HR portal (built on HiBob), used for vacation requests, sick days, payslips, reviews and benefits.")]),
    Q("q057", "acronym", "medium",
      "Who sits on the CAB and where do I ask for an exception to a deploy restriction?",
      "The Change Advisory Board: Boaz Nahum, Michal Ben-David and the on-call engineer of the affected service. Post the request in #cab with the change, the reason, the rollback plan and the on-call engineer who will watch it.",
      ["Boaz Nahum", "Michal Ben-David", "on-call engineer of the affected service", "request in #cab"],
      [("co-glossary", "Members: Boaz Nahum (Platform), Michal Ben-David (VP Engineering) and the on-call engineer of the affected service."),
       ("eng-deploy-process", "To request an exception, post in #cab with the change, the reason it cannot wait, the rollback plan, and the name of an on-call engineer who will watch the deploy.")]),
    Q("q058", "acronym", "easy",
      "What is Fixit and how do I open a ticket in it?",
      "Fixit is the IT ticketing system; emailing it@acme.example creates a Fixit ticket automatically (or post in #it-help).",
      ["Fixit is the IT ticketing system", "email it@acme.example creates a ticket"],
      [("co-glossary", "**Fixit:** the IT ticketing system. Emails to it@acme.example create Fixit tickets."),
       ("it-helpdesk", "Email: it@acme.example (creates a Fixit ticket automatically)")],
      ["format:html"]),

    # ------------------------------------------------------------ hebrew
    Q("q059", "hebrew", "easy",
      "כמה מקומות חניה יש לחברה בחניון של משרד תל אביב?",
      "18 מקומות חניה בחניון הבניין, בקומה מינוס 2.",
      ["18 מקומות", "קומה מינוס 2"],
      [("co-parking-tlv-he", "לחברה יש 18 מקומות חניה בחניון הבניין, בקומה מינוס 2.")]),
    Q("q060", "hebrew", "easy",
      "עד מתי צריך להזמין מקום חניה במשרד תל אביב?",
      "עד השעה 18:00 ביום שלפני, באפליקציית החניה של הבניין.",
      ["עד 18:00 ביום שלפני", "באפליקציית החניה"],
      [("co-parking-tlv-he", "ההזמנה נעשית באפליקציית החניה של הבניין, עד השעה 18:00 ביום שלפני.")]),
    Q("q061", "hebrew", "easy",
      "כמה אחוזים מהפרמיה של בני משפחה בביטוח הבריאות Acme משלמת?",
      "50% מהפרמיה. את היתרה העובד משלם בניכוי מהשכר (על העובד עצמו Acme משלמת 100%).",
      ["Acme משלמת 50% עבור בני משפחה"],
      [("hr-health-insurance-he", "עבור בני משפחה Acme משלמת 50% מהפרמיה, והעובד משלם את היתרה בניכוי מהשכר.")]),
    Q("q062", "hebrew", "medium",
      "כמה עולה לעובד בחודש לצרף לביטוח הבריאות את בת הזוג וילד אחד?",
      "67 ש\"ח בחודש: 48 ש\"ח לבת הזוג (בן משפחה בוגר) ועוד 19 ש\"ח לילד, אחרי ההשתתפות של Acme.",
      ["48 ש\"ח לבן משפחה בוגר", "19 ש\"ח לילד", "סה\"כ 67 ש\"ח"],
      [("hr-health-insurance-he", "אחרי ההשתתפות של Acme העובד משלם 48 ש\"ח לבן משפחה בוגר ו-19 ש\"ח לילד.")],
      ["numeric"]),
    Q("q063", "hebrew", "easy",
      "מה גובה מענק המילואים?",
      "500 ש\"ח על כל 10 ימי מילואים מצטברים בשנה קלנדרית, עד תקרה של 3,000 ש\"ח בשנה.",
      ["500 ש\"ח לכל 10 ימים", "תקרה של 3,000 ש\"ח בשנה"],
      [("hr-reserve-duty-he", "על כל 10 ימי מילואים מצטברים בשנה קלנדרית, העובד מקבל מענק של 500 ש\"ח, עד תקרה של 3,000 ש\"ח בשנה.")]),
    Q("q064", "hebrew", "medium",
      "מה עושים כשיש pod של flow-scheduler שתקוע במצב Terminating?",
      "מוחקים אותו בכוח (kubectl delete pod עם ‎--grace-period=0 --force), כפי שנלמד מהתקלה של מרץ 2026.",
      ["מחיקה בכוח של ה-pod", "הלקח מתקלת מרץ"],
      [("eng-oncall-scheduler-he", "אם יש pod תקוע במצב Terminating על node שמתרוקן (draining), למחוק אותו בכוח"),
       ("eng-oncall-scheduler-he", "זה הלקח מהתקלה של מרץ.")]),
    Q("q065", "hebrew", "easy",
      "האם מותר להכניס נתוני לקוחות ל-Claude בסביבה הארגונית של Acme?",
      "לא. נתוני לקוחות הם מידע ברמת Restricted, ומידע כזה אסור בכל כלי AI, כולל הכלים המאושרים.",
      ["אסור", "Restricted אסור בכל כלי AI כולל המאושרים"],
      [("it-ai-usage-he", "מידע ברמת Restricted: אסור בכל כלי AI, כולל הכלים המאושרים.")]),
    Q("q066", "hebrew", "easy",
      "מה היה זמן התגובה הראשונה החציוני בתמיכה באוגוסט 2026?",
      "38 דקות.",
      ["38 דקות"],
      [("sup-meeting-2026-09-he", "זמן תגובה ראשונה (FRT) חציוני: 38 דקות לכל הקריאות.")]),
    Q("q067", "hebrew", "easy",
      "באילו שעות יוצאת ההסעה מתחנת חוף הכרמל למשרד חיפה?",
      "בשעות 08:15, 08:45 ו-09:15 (ולא בימי שישי ובחגים).",
      ["08:15", "08:45", "09:15"],
      [("co-haifa-office-he", "ההסעה יוצאת בשעות 08:15, 08:45 ו-09:15")],
      ["format:html"]),
    Q("q068", "hebrew", "easy",
      "כמה ימי חופשה מקבל עובד במשרה מלאה בשנה הראשונה?",
      "14 ימי חופשה בתשלום (לפי מדיניות 2026).",
      ["14 ימים"],
      [("hr-vacation-2026-he", "עובד במשרה מלאה מקבל 14 ימי חופשה בתשלום בשנת העבודה הראשונה."),
       ("hr-vacation-2026", "Full-time employees receive 14 paid vacation days in their first year of employment.")],
      ["cross-lingual", "stale:hr-vacation-2024"]),
    Q("q069", "hebrew", "medium",
      "מי הבעלים של השירות flow-api ומתי מתחלפת הכוננות שלו?",
      "צוות Core API בראשות איתי ברק. הכוננות שבועית, וההחלפה ביום ראשון בשעה 10:00.",
      ["צוות Core API", "איתי ברק", "החלפה ביום ראשון ב-10:00"],
      [("eng-service-catalog", "| flow-api | Core API | Itai Barak | 1 | core-api-oncall: weekly, handover Sunday 10:00 | flow-api-prod |")],
      ["cross-lingual"]),

    # ------------------------------------------------------------ unanswerable
    Q("q070", "unanswerable", "easy",
      "What percentage of salary does Acme match in the 401(k) plan?", NA, [], []),
    Q("q071", "unanswerable", "medium",
      "How many parking spots does the Haifa office have?", NA, [], [],
      ["near-miss: Haifa parking is described as free, without a number"]),
    Q("q072", "unanswerable", "easy",
      "Who is Acme's General Counsel?", NA, [], [],
      ["near-miss: Legal is mentioned but no person is named"]),
    Q("q073", "unanswerable", "medium",
      "What was Acme's ARR at the end of 2023?", NA, [], [],
      ["near-miss: ARR for end of 2024, end of 2025 and June 2026 is given"]),
    Q("q074", "unanswerable", "easy",
      "Does Acme subsidize gym memberships?", NA, [], []),
    Q("q075", "unanswerable", "medium",
      "How many vacation days do Berlin employees get under the German addendum?", NA, [], [],
      ["near-miss: the addendum is mentioned but not part of the corpus"]),
    Q("q076", "unanswerable", "medium",
      "What is this month's door code for the Berlin office?", NA, [], [],
      ["near-miss: the code is published in Pulse, not in the documents"]),
    Q("q077", "unanswerable", "medium",
      "What was the root cause of the flow-engine outage in November 2025?", NA, [], [],
      ["near-miss: postmortems exist only for March, June and August 2026"]),
    Q("q078", "unanswerable", "easy",
      "What is the salary band for an E5 engineer?", NA, [], [],
      ["near-miss: levels E1-E7 are mentioned, bands are not"]),
    Q("q079", "unanswerable", "medium",
      "מה מספר הטלפון של סוכן הביטוח שמגיע למשרד בתל אביב?", NA, [], [],
      ["hebrew", "near-miss: the agent's visits are described, no phone number"]),
]


# ---------------------------------------------------------------- extraction for verification

class _TextHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self._skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def doc_text(doc) -> tuple[str, bool]:
    """Return (text, normalized?)"""
    if doc.format == "md":
        return doc.text, False
    if doc.format == "html":
        p = _TextHTML()
        p.feed(doc.path.read_text(encoding="utf-8"))
        return norm(" ".join(p.parts)), True
    if doc.format == "pdf":
        from pypdf import PdfReader
        return norm(" ".join(pg.extract_text() for pg in PdfReader(str(doc.path)).pages)), True
    if doc.format == "docx":
        from docx import Document
        d = Document(str(doc.path))
        parts = [p.text for p in d.paragraphs]
        for t in d.tables:
            for row in t.rows:
                parts += [c.text for c in row.cells]
        return norm("\n".join(parts)), True
    raise ValueError(doc.format)


def verify(qa: list[dict]) -> list[str]:
    docs = {d.id: d for d in load.iter_docs()}
    cache: dict[str, tuple[str, bool]] = {}
    errors = []
    ids = set()
    for r in qa:
        if r["id"] in ids:
            errors.append(f"duplicate id {r['id']}")
        ids.add(r["id"])
        for sid in r["source_ids"]:
            if sid not in docs:
                errors.append(f"{r['id']}: unknown source id {sid}")
        for sq in r["source_quotes"]:
            sid = sq["source_id"]
            if sid not in docs:
                continue
            if sid not in cache:
                cache[sid] = doc_text(docs[sid])
            text, normalized = cache[sid]
            q = norm(sq["quote"]) if normalized else sq["quote"]
            if q not in text:
                errors.append(f"{r['id']}: quote not found in {sid}: {sq['quote'][:70]!r}")
        if r["type"] == "unanswerable":
            if r["answer"] != NA or r["source_ids"]:
                errors.append(f"{r['id']}: unanswerable must have answer '{NA}' and no sources")
        elif not r["source_quotes"]:
            errors.append(f"{r['id']}: answerable question without quotes")
    return errors


if __name__ == "__main__":
    errs = verify(QA)
    if errs:
        print("\n".join(errs))
        sys.exit(1)
    out = ROOT / "golden" / "qa.jsonl"
    out.parent.mkdir(exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        for r in QA:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    from collections import Counter
    print(f"wrote {len(QA)} questions -> {out}")
    print(dict(Counter(r["type"] for r in QA)))
    print(dict(Counter(r["difficulty"] for r in QA)))
