---
id: eng-runbook-flow-api
title: On-call Runbook - flow-api
department: engineering
doc_type: runbook
version: "4.0"
effective_date: 2026-09-01
owner: Itai Barak
classification: internal
language: en
---

# On-call Runbook: flow-api

`flow-api` is the public REST API of Acme Flow and the entry point for inbound webhooks. It is a Tier 1 service owned by the Core API team (lead: Itai Barak).

## Rotation

- Rotation name: core-api-oncall. Weekly, handover on Sunday at 10:00 Israel time in #core-api-oncall.
- Primary and secondary. The primary must acknowledge a page within 5 minutes; otherwise the secondary is paged, and after 15 minutes Itai Barak.
- Escalation beyond the team: the platform-oncall for cluster, Kafka or database problems, and identity-oncall for authentication failures.

## Key dashboards

- "Flow API - Golden Signals": request rate, 5xx rate, p50/p99 latency per endpoint, per region.
- "Auth - Token Validation": latency and errors of calls from flow-api to auth-service.
- Kafka producer errors for the `runs.requested` topic.

## Alerts and what to do

### FlowApi5xxRateHigh
Fires when the 5xx rate is above 2% for 5 minutes in a region.

1. Check whether a deploy happened in the last hour in #deploys. If yes, roll back first: `conveyor rollback flow-api --to <previous-sha>`.
2. Look at the error breakdown by endpoint and by upstream. A spike of `upstream=auth` errors means auth-service is failing or slow: page identity-oncall and check whether auth-service had a deploy or configuration change.
3. If Kafka produce errors are high, page platform-oncall.
4. If the 5xx rate is above 25% for more than 5 minutes, declare a SEV1 in #incidents and assign an incident commander.

### FlowApiLatencyP99High
Fires when p99 latency is above 800 ms for 10 minutes.

1. Check the slowest endpoints. `/v1/runs/{id}/logs` is known to be slow for very large runs; if only that endpoint is affected, it is not an incident.
2. Check pod CPU. If the pods are CPU-bound and not scaling, check the HPA: `kubectl -n flow-api get hpa`.
3. Check Redis latency (rate-limit counters). Redis problems go to platform-oncall.

### WebhookIngestBacklog
Fires when more than 50,000 inbound webhooks are waiting to be written to Kafka.

1. Webhooks are buffered locally on each pod for up to 10 minutes. No data is lost as long as pods are not restarted.
2. Do not restart flow-api pods while the backlog is high unless instructed by the incident commander.
3. Find why Kafka writes are failing (see above).

### RateLimiterDegraded
The rate limiter fails open: if Redis is unavailable, requests are allowed without limits. This keeps customers working but exposes downstream services to bursts. Inform engine-oncall so they can watch consumer lag.

## Useful commands

- Recent errors for one customer: in Datadog logs, `service:flow-api @org_id:<org> status:error`.
- Pods per region: `kubectl -n flow-api get pods -o wide --context prod-il` (or `prod-eu`).
- Disable an abusive API key temporarily: `acmectl apikey suspend <key-id> --reason "<ticket>"` (requires the on-call role; always notify Customer Support in #support-escalations).

## Severity guide for flow-api

- SEV1: API unavailable or 5xx above 25% in any region, or webhooks dropped.
- SEV2: elevated errors (5-25%) or p99 above 2 seconds for more than 15 minutes.
- SEV3: degradation of a single non-critical endpoint.

## Communication

For SEV1 and SEV2, the incident commander asks Customer Support to update the public status page within 15 minutes of declaring the incident, and every 30 minutes afterwards.

## After an incident

Every SEV1 and SEV2 gets a blameless postmortem, written within 5 business days and reviewed in Blue Room. See the August 2026 postmortem for the most recent flow-api SEV1.
