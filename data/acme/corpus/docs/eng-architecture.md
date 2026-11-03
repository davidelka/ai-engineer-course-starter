---
id: eng-architecture
title: Acme Flow Architecture Overview
department: engineering
doc_type: reference
version: "3.3"
effective_date: 2026-09-20
owner: Michal Ben-David
classification: internal
language: en
---

# Acme Flow Architecture Overview

This document explains how Acme Flow, Acme's workflow automation platform, is built: the main services, how a workflow run travels through the system, where data lives, and the main design decisions and their trade-offs. It is meant for new engineers, for engineers from other teams who need the big picture, and for anyone preparing for an on-call rotation. For the list of services with owners and on-call rotations, see the Service Catalog. For deploys, see the Deploy Process.

## 1. What Acme Flow does

Acme Flow lets business teams automate work across the tools they already use. A customer builds a **workflow** in the web app: a **trigger** (a webhook, a schedule, or an event from a connected tool such as a new row in a spreadsheet) followed by a sequence of **steps** (transformations, conditions, loops, and **actions** in other tools, for example "create a Jira issue" or "send a Slack message"). Every time a trigger fires, Acme Flow creates a **run**: one execution of the workflow from the trigger to the last step.

At the time of writing, Acme Flow serves about 1,950 customer organizations and executes about 38 million runs per month. Peak load is around 2,600 runs started per second, usually on the first business morning of the month, when many scheduled reporting workflows fire together.

## 2. High-level picture

Requests reach Acme Flow through two doors:

1. **The web app** (`web-app`), a React single-page application that customers use to build and monitor workflows. It talks only to the public API.
2. **The public API** (`flow-api`), a REST API used by the web app, by customers' own code, and by inbound webhooks from third-party tools.

Behind the API, the main services are:

- **auth-service:** identity, login, OAuth2/OIDC token issuing and validation, SAML single sign-on for Business and Enterprise customers, and API keys. Every request to `flow-api` is authenticated by calling `auth-service` (with a short local cache of validated tokens, 60 seconds).
- **flow-scheduler:** owns time-based triggers (cron-like schedules) and delayed steps. It decides *when* a run should start and publishes a "run requested" message.
- **flow-engine:** the heart of the platform. It consumes "run requested" messages, loads the workflow definition, and executes steps one by one on a pool of workers, persisting the state of each run after every step so that a run can resume after a crash.
- **connectors-hub:** the integration layer with about 240 connectors to third-party tools. It stores customers' connection credentials (encrypted) and executes actions and polling triggers against third-party APIs, with per-connector rate limiting.
- **notifications:** sends email, Slack and in-app notifications about failed runs, usage limits and account events.
- **billing-service:** meters usage (runs, connector calls, seats), calculates invoices, and talks to the payment provider. It produces invoices on the 2nd of each month for the previous month.
- **lighthouse:** the analytics data warehouse (ClickHouse) fed by a change-data-capture pipeline. It powers internal analytics and the customer-facing usage dashboards.

All services run on Kubernetes (Amazon EKS), built and deployed by the Platform team's CI/CD pipeline, Conveyor.

## 3. Life of a run

The following walk-through follows a single run of a workflow with a webhook trigger and two actions.

1. A third-party tool sends an HTTP POST to the customer's webhook URL, which points to `flow-api`.
2. `flow-api` validates the signature of the webhook, checks the customer's rate limit, and writes a "run requested" message to the `runs.requested` Kafka topic. It returns `202 Accepted` to the caller within a target p99 of 300 ms. The API never executes workflow steps itself.
3. A `flow-engine` worker consumes the message, loads the workflow definition (cached in Redis, with PostgreSQL as the source of truth), and creates a run record in the runs database.
4. For each step, the worker either executes it locally (transformations, conditions) or calls `connectors-hub` for actions in third-party tools. After every step, the worker writes a checkpoint: the step's output and the next step to execute.
5. If a step fails with a retryable error (for example a 429 from a third-party API), the engine schedules a retry with exponential backoff through `flow-scheduler`. Non-retryable errors fail the run and trigger a notification.
6. When the run finishes, the engine publishes a `runs.completed` event. `billing-service` consumes it to count usage, and the CDC pipeline copies the run summary to `lighthouse`.

For schedule-based triggers, step 1 and 2 are replaced by `flow-scheduler`, which publishes the "run requested" message when a schedule fires.

## 4. Data stores

- **PostgreSQL (Amazon Aurora):** workflow definitions, runs and checkpoints, accounts, billing data. Each service owns its own database; services never read another service's database directly.
- **Kafka (Amazon MSK):** the backbone between services. Main topics: `runs.requested`, `runs.completed`, `usage.events`, `audit.events`.
- **Redis:** caches (workflow definitions, token validation), rate-limit counters, and short-lived locks.
- **S3:** large step payloads (over 256 KB) are stored in S3 and referenced from the checkpoint, and run logs are archived there.
- **ClickHouse (lighthouse):** analytics only. It is never used to serve product requests that need consistency.

Customer workflow payloads are classified as Restricted data. They are encrypted at rest with per-region keys in AWS KMS, application logs that may contain them are retained for 30 days, and engineers access them only through the needs_security track.

## 5. Regions and data residency

Acme Flow runs in two AWS regions:

- **il-central-1 (Tel Aviv):** the original region, serving customers in Israel and the rest of the world by default.
- **eu-central-1 (Frankfurt):** since the Tidewater project went live in October 2025, customers who choose EU data residency have all their workflow data, run history and connector credentials stored and processed only in Frankfurt. EU data residency is part of the Enterprise plan and available as an add-on for Business.

Each region is a full, independent copy of the platform (cells). Only global account metadata (organization name, plan, region assignment) is replicated between regions. A customer cannot be served from both regions at once, and moving a customer between regions is a manual, planned migration.

## 6. Scaling and limits

- `flow-api` scales horizontally on CPU and request rate; it runs at least 6 pods per region.
- `flow-engine` workers scale on Kafka consumer lag. The target is that a run starts within 5 seconds of being requested (p95).
- `flow-scheduler` is deliberately not horizontally scaled: exactly one replica is the leader at any time and fires schedules; standby replicas take over if the leader fails. Leadership uses a lease in PostgreSQL with a fencing token on every published message (added after the March 2026 incident).
- API rate limits per customer depend on the plan: Starter 60 requests per minute, Team 300, Business 1,000, Enterprise 5,000.
- A single run may have at most 500 steps and run for at most 24 hours; longer processes must be split into several workflows.

## 7. Reliability targets

Internal service level objectives (SLOs) are stricter than the contractual SLA so that we notice problems before customers are owed credits:

- `flow-api` availability: 99.97% monthly (the contractual SLA for Enterprise is 99.95%).
- Run start latency: 95% of runs start within 5 seconds.
- `auth-service` token validation: p99 under 50 ms.

Each Tier 1 service has a 24/7 on-call rotation; see the Service Catalog.

## 8. Observability

All services emit structured JSON logs, Prometheus-style metrics and OpenTelemetry traces. Metrics and traces go to Datadog; logs go to Datadog with 15-day hot retention and are archived to S3 for 30 days. Every run carries a `run_id` that appears in logs, traces and the customer-facing run history, which makes it possible to follow a single run across services. Alerts page through PagerDuty.

## 9. Key design decisions

**Asynchronous by default.** The API only accepts work and enqueues it. This keeps the API fast and protects it from slow third-party tools, at the cost of more complex debugging: a "successful" API call does not mean the run succeeded.

**Checkpoint after every step.** This makes runs resumable after crashes and deploys, and lets customers see exactly where a run failed. The cost is write load on the runs database, which is the main reason for the Kestrel project.

**Cells per region instead of a global platform.** Simpler data residency and a smaller blast radius, at the cost of operating two copies of everything.

**One owner per service.** Every service has exactly one owning team, listed in the Service Catalog. Shared ownership has repeatedly led to slow incident response at Acme.

## 10. What is changing

- **Kestrel:** a rewrite of the execution layer of `flow-engine` with a new storage model for checkpoints. Kestrel runs in shadow mode for 5% of runs since June 2026.
- **Config changes through canary:** after the August 2026 incident, configuration changes go through the same canary stage as code (see the Deploy Process).
- **Scheduler ownership:** a proposal to move `flow-scheduler` to the Platform team is under discussion; until the Service Catalog changes, the Engine team owns it.

## 11. Glossary pointers

Internal code names (Kestrel, Tidewater, Orca, Conveyor, Lighthouse and others) are defined in the Acme Glossary.
