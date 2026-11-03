---
id: sup-escalation
title: Support Priorities and Escalation
department: sales_support
doc_type: policy
version: "3.1"
effective_date: 2026-02-15
owner: Shira Levin
classification: internal
language: en
---

# Support Priorities and Escalation

## Support tiers

- **L1, Support Agents:** first contact for all tickets. The Tel Aviv team works Sunday to Thursday, 08:00-18:00 Israel time; the Berlin team works Monday to Friday, 08:00-18:00 Berlin time. Together they cover most of the working week in both time zones.
- **L2, Support Engineers:** handle technical investigations, reproduce bugs, read logs, and decide when engineering is needed.
- **L3, Engineering:** the on-call rotation of the owning team, paged through PagerDuty by an L2 engineer or by the incident process.

Outside working hours, P1 tickets from Business and Enterprise customers page the support on-call (an L2 engineer) 24/7. Other tickets wait for the next working day.

## Priorities

- **P1, Critical:** production workflows are down or the customer cannot log in, with no workaround.
- **P2, High:** a major feature is broken or severely degraded; a workaround exists but is painful.
- **P3, Normal:** a problem with limited impact, or a question about expected behavior.
- **P4, Low:** feature requests, cosmetic issues, general questions.

The customer chooses an initial priority; the agent may change it, and must explain why in the ticket.

## First response targets

First response time (FRT) is measured from the creation of the ticket to the first reply by a human agent.

| Priority | Enterprise | Business | Team | Starter |
|---|---|---|---|---|
| P1 | 30 minutes (24/7) | 1 hour (24/7) | 4 business hours | community only |
| P2 | 2 hours | 4 business hours | 1 business day | community only |
| P3 | 8 business hours | 1 business day | 2 business days | community only |
| P4 | 2 business days | 3 business days | 5 business days | community only |

A ticket whose first response comes after the target is counted as an SLA breach in the weekly support report.

## Escalation rules

1. L1 escalates to L2 when the problem is technical and not answered by the knowledge base within 30 minutes of work.
2. Tickets from Red Folder accounts skip L1 and go straight to L2.
3. L2 pages the owning team's on-call (L3) for any P1 that is not mitigated within 60 minutes, or immediately when several customers report the same P1 problem.
4. When engineering declares an incident, support links all related tickets to the incident ticket and stops working them individually; the communications lead posts updates.
5. Any customer threatening to cancel, or any legal threat, is escalated to the support manager the same day.

## Who to call

- Support manager, Israel and Americas: Nir Golan.
- Support lead, EMEA: Jonas Becker (Berlin).
- VP Customer Support: Shira Levin.
- Slack: #support-escalations for L2/L3 handoffs.

## Status page

During incidents, the public status page is updated by Customer Support at the request of the incident commander. Agents link customers to the status page instead of writing their own explanations.
