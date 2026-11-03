---
id: eng-runbook-flow-engine
title: On-call Runbook - flow-engine
department: engineering
doc_type: runbook
version: "3.1"
effective_date: 2026-06-15
owner: Dana Levi
classification: internal
language: en
---

# On-call Runbook: flow-engine

`flow-engine` executes workflow runs. It is a Tier 1 service owned by the Engine team (lead: Dana Levi). The same rotation also covers `flow-scheduler`; scheduler-specific notes are in a separate Hebrew document in the Engine space.

## Rotation

- Rotation name: engine-oncall. Weekly, handover on Sunday at 10:00 Israel time in #engine-oncall.
- Primary and secondary. Acknowledge pages within 5 minutes. Escalate to Dana Levi after 15 minutes without progress on a SEV1.
- Kestrel shadow mode: Kestrel workers run alongside the production engine for 5% of runs. Kestrel alerts are routed to a separate low-urgency PagerDuty service and never page at night.

## Key dashboards

- "Engine - Runs and Lag": runs started per second, consumer lag on `runs.requested`, run start latency (p95), step failure rate.
- "Engine - Workers": worker pods, CPU and memory, OOM kills.
- "Connectors - Third-party Errors": many engine incidents are really third-party outages.

## Alerts and what to do

### EngineConsumerLagHigh
Fires when lag on `runs.requested` exceeds 100,000 messages or run start latency p95 exceeds 30 seconds for 10 minutes.

1. Check whether workers are scaling. The worker autoscaler is capped at 400 pods per region; if the cap is reached, ask platform-oncall to raise it temporarily.
2. Check whether one customer is flooding the queue (top orgs by runs requested). Enterprise customers may legitimately burst; a Starter customer starting thousands of runs per minute probably has a loop in their workflow. You may throttle a single organization with `acmectl org throttle <org-id> --runs-per-min 100` for up to 24 hours, and you must notify Customer Support.
3. On the first business day of the month, a lag of up to 300,000 that clears within 30 minutes is expected because of scheduled monthly reports.

### EngineStepFailureRateHigh
Fires when the step failure rate across all customers is above 8% for 15 minutes.

1. Break down failures by connector. If one connector dominates, it is likely a third-party outage: inform integrations-oncall and post in #support-escalations. This is not an engine incident.
2. If failures are spread across connectors and started after a deploy, roll back flow-engine.

### EngineCheckpointWriteErrors
Fires when writing checkpoints to the runs database fails for more than 1% of steps.

1. This is serious: runs cannot progress. Page platform-oncall for the Aurora cluster.
2. Check database CPU and connections. The engine opens at most 40 connections per worker pod through PgBouncer.
3. Declare a SEV1 if it lasts more than 10 minutes.

### WorkerOOMKills
Workers killed for exceeding memory, usually because of a very large step payload. Payloads over 256 KB should go to S3; a sudden increase usually means a bug in that offloading logic. Not urgent at night unless lag grows.

## Pausing runs for a customer

In rare cases (a runaway workflow causing harm to a third-party system), the on-call engineer may pause all runs of one workflow: `acmectl workflow pause <workflow-id> --reason "<ticket>"`. Pausing a whole organization requires the approval of the VP Customer Support or the incident commander.

## Severity guide for flow-engine

- SEV1: runs not starting or not progressing for more than 10 minutes in a region, or data loss of run state.
- SEV2: run start latency p95 above 2 minutes for more than 15 minutes, or a single Enterprise customer fully blocked.
- SEV3: elevated failures limited to one connector or a small group of customers.

## Handover template

At handover, post: open incidents, ongoing throttles or paused workflows (with expiry), noisy alerts that need tuning, and anything planned for the coming week (migrations, Kestrel experiments).
