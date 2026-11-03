---
id: co-glossary
title: Acme Glossary of Internal Terms
department: company
doc_type: reference
version: "2026.3"
effective_date: 2026-09-01
owner: Gali Oren
classification: internal
language: en
---

# Acme Glossary of Internal Terms

Acme uses many internal names, code names and abbreviations. This glossary explains them. If you find a term that is missing, add it in the Confluence version of this page or ask in #ask-anything.

## Code names and internal tools

- **Kestrel:** the project to rewrite the execution layer of flow-engine with a new storage model for run checkpoints. Owned by the Engine team. Running in shadow mode since June 2026; general availability planned for Q1 2027.
- **Tidewater:** the EU data residency project that launched the eu-central-1 (Frankfurt) region in October 2025.
- **Orca:** the 2025 migration of all services from self-managed virtual machines to Kubernetes (Amazon EKS). Completed in November 2025. "Post-Orca node groups" means the managed Kubernetes node groups created in that migration.
- **Conveyor:** the CI/CD pipeline owned by the Platform team. Every production change goes through it.
- **Lighthouse:** the analytics data warehouse (ClickHouse) owned by the Data team. The service is called `lighthouse` in the Service Catalog.
- **Bridge:** the old name of connectors-hub, still used in some dashboards and older documents.
- **Fixit:** the IT ticketing system. Emails to it@acme.example create Fixit tickets.
- **Pulse:** the HR portal (built on HiBob), used for vacation requests, sick days, payslips, reviews and benefits.
- **Spendwise:** the expense system.
- **TripDesk:** the travel booking tool.
- **Forge:** Acme's yearly internal hackathon.
- **acmectl:** the internal command-line tool for operational actions (throttling, pausing workflows, billing corrections). Requires the on-call role.

## Meetings and processes

- **Blue Room:** the weekly incident review meeting, every Thursday at 11:00 Israel time, chaired by the VP Engineering. Every SEV1 and SEV2 postmortem is reviewed there. The name comes from the blue meeting room on floor 3 in Haifa where it was first held.
- **CAB (Change Advisory Board):** the group that approves exceptions to deploy restrictions. Members: Boaz Nahum (Platform), Michal Ben-David (VP Engineering) and the on-call engineer of the affected service. Requests go to #cab and are answered within 2 hours during working hours.
- **Quiet Hours:** the period in which production deploys are blocked: from Thursday 15:00 to Sunday 09:00 Israel time, and from 15:00 on the eve of an Israeli public holiday until 09:00 on the next working day.
- **ERT (Executive Response Team):** the group notified for every SEV1 security incident: the CEO, the CTO, the CISO and the VP Customer Support.
- **Red Folder:** the list of the 25 accounts with the highest ARR, maintained by Shira Levin (VP Customer Support). Tickets from Red Folder accounts skip L1 and go directly to L2.
- **Handover:** the weekly transfer of an on-call rotation, done in writing in the rotation's Slack channel.
- **Shadow:** a new on-call engineer who receives pages alongside the primary but is not responsible for them.

## Product terms

- **Run:** one execution of a workflow, from the trigger to the last step. Plans include a number of runs per month.
- **Step:** one unit of work inside a workflow (an action, a condition, a transformation).
- **Connector:** an integration with a third-party tool, provided by connectors-hub.
- **Cell:** a full, independent copy of the platform in one AWS region.

## Abbreviations

- **ARR:** annual recurring revenue.
- **NRR:** net revenue retention.
- **CSM:** customer success manager.
- **FRT:** first response time in Customer Support.
- **IC:** incident commander.
- **SEV1-SEV4:** incident severity levels; SEV1 is the most severe.
- **PIP:** performance improvement plan.
- **PO:** purchase order.
- **TLV-1, HFA-1, BER-1:** office codes for Tel Aviv, Haifa and Berlin.
