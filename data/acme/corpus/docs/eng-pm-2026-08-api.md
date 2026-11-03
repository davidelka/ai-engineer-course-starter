---
id: eng-pm-2026-08-api
title: "Postmortem: flow-api outage (August 19, 2026)"
department: engineering
doc_type: postmortem
version: "1.0"
effective_date: 2026-08-26
owner: Itai Barak
classification: confidential
language: en
---

# Postmortem: flow-api outage on August 19, 2026

- **Date of incident:** August 19, 2026
- **Severity:** SEV1
- **Duration of full unavailability:** 47 minutes (14:06 to 14:53 Israel time)
- **Affected service:** flow-api in both regions; root cause in auth-service
- **Incident commander:** Tomer Shani (core-api-oncall primary)
- **Reviewed in:** Blue Room, August 27, 2026

## Summary

A configuration change to auth-service reduced its database connection pool from 200 to 20 connections per pod. Token validation requests from flow-api queued behind the small pool and timed out, and flow-api returned errors for 92% of requests at the peak. For 47 minutes the public API, the web app and inbound webhooks were effectively unavailable in both regions. The configuration change skipped the canary stage, because configuration-only changes were not canaried at the time.

## Impact

- About 1,140 customer organizations made at least one failed API call.
- About 2.3 million API requests failed with 5xx errors or timeouts.
- Inbound webhooks were buffered on flow-api pods and replayed after recovery; no webhook was lost. Scheduled runs were not affected, because flow-scheduler does not depend on flow-api.
- Monthly availability of flow-api for August 2026 was 99.89%, below the 99.95% monthly commitment for Enterprise customers and the 99.9% commitment for Business customers.
- 203 support tickets, including 31 P1 tickets from Enterprise customers.

## Timeline (Israel time)

- 14:03: An identity engineer merges a configuration change to auth-service intended to set a per-pod connection limit of 200; a typo sets it to 20. Conveyor applies it to both regions in under 2 minutes, without a canary.
- 14:06: flow-api 5xx rate rises to 92%. Customer-facing outage begins.
- 14:09: FlowApi5xxRateHigh pages core-api-oncall. Tomer Shani acknowledges at 14:10.
- 14:15: SEV1 declared, Tomer Shani is incident commander. Status page updated at 14:21.
- 14:19: No flow-api deploy in the last hour; the error breakdown shows `upstream=auth` timeouts. identity-oncall paged.
- 14:31: identity-oncall finds the connection pool change in #deploys.
- 14:41: Rollback of the configuration started with `conveyor rollback auth-service`.
- 14:49: auth-service pods restarted with the correct pool size; error rate dropping.
- 14:53: flow-api error rate back to normal. Outage ends.
- 15:20: Webhook backlog fully replayed.

## Root cause

The connection pool size of auth-service was changed from 200 to 20 by a typo in a configuration-only change. Configuration changes were deployed through Conveyor without the canary stage, so the change went to 100% of pods in both regions within 2 minutes. A canary at 5% would have shown the latency increase and rolled back automatically.

## Contributing factors

- No validation of configuration values (for example a minimum pool size).
- flow-api's token validation cache (60 seconds) was too short to absorb the problem.
- It took 12 minutes from the identity page to finding the change, because configuration changes were not shown in the auth-service dashboard.

## SLA and customer communication

- Customer Support issued SLA credits to eligible Business and Enterprise customers proactively, according to the SLA in force for 2026, without waiting for customers to request them.
- A public summary of this incident was published on the status page on August 21.

## Action items

1. All configuration changes go through the canary stage in Conveyor. Owner: Boaz Nahum (Platform). Done September 1, 2026.
2. Schema validation with minimum and maximum values for auth-service configuration. Owner: Gil Avraham (Identity). Done September 8, 2026.
3. Show configuration changes as events on all service dashboards. Owner: Platform team. Done September 3, 2026.
4. Evaluate a longer token validation cache with revocation events. Owner: Gil Avraham. In progress, due December 2026.
