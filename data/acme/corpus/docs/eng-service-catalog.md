---
id: eng-service-catalog
title: Engineering Service Catalog
department: engineering
doc_type: reference
version: "2026-09"
effective_date: 2026-09-15
owner: Boaz Nahum
classification: internal
language: en
---

# Engineering Service Catalog

The Service Catalog is the source of truth for who owns what. Every production service and platform component has exactly one owning team. When a meeting note, a Slack message or an older document says something different, this catalog wins until it is updated. Changes to ownership are made by a pull request to the catalog repository, approved by the VP Engineering, Michal Ben-David.

Last full review: September 15, 2026.

## Tier definitions

- **Tier 1:** customer-facing and on the critical path of every run or login. 24/7 on-call, acknowledge a page within 5 minutes, SEV1 response within 15 minutes.
- **Tier 2:** customer-facing but degradation is tolerable for a short time, or internal and critical for engineering. 24/7 on-call, acknowledge within 15 minutes.
- **Tier 3:** internal or analytical. Business-hours support only (Sunday to Thursday, 09:00-18:00 Israel time). Alerts outside business hours create tickets, not pages.

## Production services

| Service | Owner team | Team lead | Tier | On-call rotation | PagerDuty service |
|---|---|---|---|---|---|
| flow-api | Core API | Itai Barak | 1 | core-api-oncall: weekly, handover Sunday 10:00 | flow-api-prod |
| flow-engine | Engine | Dana Levi | 1 | engine-oncall: weekly, handover Sunday 10:00 | flow-engine-prod |
| flow-scheduler | Engine | Dana Levi | 1 | engine-oncall (shared with flow-engine) | flow-scheduler-prod |
| auth-service | Identity | Gil Avraham | 1 | identity-oncall: weekly, handover Thursday 10:00; secondary is platform-oncall | auth-service-prod |
| billing-service | Billing | Rina Sasson | 1 | billing-oncall: weekly, handover Wednesday 12:00 | billing-prod |
| connectors-hub | Integrations | Omer Haddad | 2 | integrations-oncall: weekly, handover Monday 10:00 | connectors-prod |
| notifications | Integrations | Omer Haddad | 2 | integrations-oncall (shared with connectors-hub) | notifications-prod |
| web-app | Frontend | Maya Rosen | 2 | frontend-oncall: weekly, handover Sunday 10:00 | web-app-prod |
| lighthouse | Data | Eitan Klein | 3 | business hours, #data-help | none |

## Platform components

| Component | Owner team | Team lead | Tier | On-call rotation |
|---|---|---|---|---|
| Kubernetes clusters (EKS, both regions) | Platform | Boaz Nahum | 1 | platform-oncall: weekly, handover Sunday 10:00 |
| Conveyor (CI/CD pipeline) | Platform | Boaz Nahum | 2 | platform-oncall |
| Kafka (MSK), PostgreSQL (Aurora), Redis | Platform | Boaz Nahum | 1 | platform-oncall |
| Observability (Datadog, PagerDuty configuration) | Platform | Boaz Nahum | 2 | platform-oncall |
| Okta and corporate SaaS | IT | Yossi Dahan | 3 | business hours, #it-help |

## Repositories and dashboards

- flow-api: repo `acme/flow-api`, dashboard "Flow API - Golden Signals".
- flow-engine: repo `acme/flow-engine`, dashboard "Engine - Runs and Lag".
- flow-scheduler: repo `acme/flow-scheduler`, dashboard "Scheduler - Triggers".
- auth-service: repo `acme/auth-service`, dashboard "Auth - Token Validation".
- billing-service: repo `acme/billing-service`, dashboard "Billing - Invoice Run".
- connectors-hub: repo `acme/connectors-hub`, dashboard "Connectors - Third-party Errors".
- notifications: repo `acme/notifications`.
- web-app: repo `acme/web-app`, dashboard "Web - Core Web Vitals".
- lighthouse: repo `acme/lighthouse-pipelines`.

## On-call rules that apply to every rotation

- Each rotation has a primary and a secondary. The secondary is paged if the primary does not acknowledge in time.
- Engineers join a rotation as primary only after 90 days at Acme and at least one week as a shadow.
- Handover happens in the rotation's Slack channel with a short written summary of open issues.
- Runbooks exist for flow-api, flow-engine and billing-service; the flow-scheduler on-call notes are in Hebrew in the Engine team space.

## Recent ownership changes

- April 2026: notifications moved from Core API to Integrations.
- A proposal to move flow-scheduler from Engine to Platform was discussed in May 2026 and postponed. Engine remains the owner.
