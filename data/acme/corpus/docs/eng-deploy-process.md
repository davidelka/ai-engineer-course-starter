---
id: eng-deploy-process
title: Deploy Process for Acme Flow
department: engineering
doc_type: guide
version: "2.2"
effective_date: 2026-09-01
owner: Boaz Nahum
classification: internal
language: en
---

# Deploy Process for Acme Flow

All production changes to Acme Flow go through Conveyor, the Platform team's CI/CD pipeline. There is no other supported way to change production. Manual changes with `kubectl` in production are allowed only during an active incident, by the incident's on-call engineer, and must be recorded in the incident channel.

## The pipeline

1. **Pull request.** Every change starts as a pull request with at least one approving review from the owning team. Changes to Tier 1 services need two approvals. CI runs unit tests, linters, and a security scan of dependencies.
2. **Merge to main.** Merging builds a container image tagged with the commit SHA and deploys it automatically to the staging environment.
3. **Staging verification.** Automated end-to-end tests run against staging (about 12 minutes). A failure blocks the release.
4. **Canary.** The new version is deployed to 5% of production pods in one region for 20 minutes. Conveyor compares error rate and p99 latency of the canary with the stable version. If the canary error rate is more than 0.5 percentage points higher, or p99 latency more than 20% higher, Conveyor rolls back automatically.
5. **Progressive rollout.** 25%, 50%, 100% in the first region, then the same in the second region, with 10 minutes between steps.
6. **Post-deploy.** Conveyor posts a summary in #deploys with the version, the author, and links to dashboards.

A typical deploy from merge to 100% in both regions takes about 75 minutes.

## When you cannot deploy

- Production deploys are blocked during Quiet Hours unless a CAB exception is granted.
- `billing-service` is frozen from the 1st of the month at 00:00 UTC until the invoice run finishes on the 2nd.
- During an active SEV1 or SEV2, only fixes for that incident are deployed.

To request an exception, post in #cab with the change, the reason it cannot wait, the rollback plan, and the name of an on-call engineer who will watch the deploy.

## Configuration changes

Until September 2026, configuration-only changes (feature flags, connection pool sizes, timeouts) were applied through Conveyor without the canary stage, because they were considered low risk. This changed after the August 2026 flow-api outage: all configuration changes now go through the canary stage like code changes. Feature flags managed in the flag service are not affected; they have their own gradual rollout.

## Database migrations

- Migrations must be backward compatible with the previous version of the service (expand and contract): add columns before using them, stop using columns before dropping them.
- Migrations that lock large tables (over 10 million rows) must be reviewed by the Platform team and run outside peak hours.

## Rollback

Rollback is a first-class operation: `conveyor rollback <service> --to <previous-sha>` redeploys the previous image to all regions in about 8 minutes, skipping the canary. Rolling back is always acceptable and never needs approval. Roll back first, investigate later.

## Responsibilities

- The author of the change is responsible for watching the canary and the dashboards until the rollout is complete.
- The owning team's on-call engineer must be aware of deploys to Tier 1 services during their shift.
- The Platform team owns Conveyor itself; problems with the pipeline go to #platform-help or the platform-oncall rotation.
