---
id: eng-leads-sync-2026-05
title: Engineering Leads Sync - May 14, 2026
department: engineering
doc_type: meeting_notes
version: "1.0"
effective_date: 2026-05-14
owner: Michal Ben-David
classification: internal
language: en
---

# Engineering Leads Sync - May 14, 2026

**Attendees:** Michal Ben-David (chair), Itai Barak, Dana Levi, Omer Haddad, Rina Sasson, Gil Avraham, Maya Rosen, Eitan Klein, Boaz Nahum, Tamar Golan (for item 4)
**Notes by:** Maya Rosen

## 1. Kestrel status (Dana)

- Shadow mode will start in June with 5% of runs in il-central-1 only.
- Checkpoint write load in shadow mode is 61% lower than the current engine in load tests.
- Target for general availability: Q1 2027. Dana is worried about the Q4 hiring plan; two open positions in the Engine team are still not filled.

## 2. flow-scheduler ownership

- Boaz proposed moving flow-scheduler from Engine to Platform, since the March incident was mostly about node and clock problems and Engine is fully loaded with Kestrel.
- Dana agreed in principle.
- **Decision:** flow-scheduler ownership moves from Engine to Platform in Q3 2026. Boaz will update the service catalog and the PagerDuty routing by July 1.

## 3. Quiet Hours

- Several teams asked to start Quiet Hours earlier on Thursday, at 14:00, because late Thursday deploys keep causing weekend pages.
- No decision. Boaz will bring data on weekend pages by deploy time to the next sync.

## 4. Security: production access review (Tamar)

- Tamar presented the results of the Q1 access review: 23 engineers had production database access they had not used in 90 days. All of it was revoked.
- Starting with SaaS Access Policy v2.2 (planned for June), needs_security grants will expire after 90 days by default.

## 5. On-call load

- Billing-oncall had the quietest quarter. Core API had 41 pages in April, of which 17 were non-actionable. Itai will tune FlowApiLatencyP99High.
- Proposal to compensate on-call at a higher rate during holidays; Michal will raise it with Orly (People).

## Action items

- Boaz: update service catalog and PagerDuty for flow-scheduler move (by July 1).
- Boaz: weekend pages vs deploy time analysis.
- Itai: tune noisy flow-api alerts.
- Dana: Kestrel shadow mode plan to all engineering.
- Michal: on-call holiday compensation with People.
