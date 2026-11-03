---
id: eng-pm-2026-03-scheduler
title: "Postmortem: Duplicate scheduled runs (March 12, 2026)"
department: engineering
doc_type: postmortem
version: "1.0"
effective_date: 2026-03-19
owner: Dana Levi
classification: confidential
language: en
---

# Postmortem: Duplicate scheduled runs from flow-scheduler

- **Date of incident:** March 12, 2026
- **Severity:** SEV2
- **Duration of customer impact:** 2 hours 14 minutes (09:52 to 12:06 Israel time)
- **Affected service:** flow-scheduler (region il-central-1)
- **Incident commander:** Yonatan Peled (engine-oncall primary)
- **Status:** all action items completed as of April 20, 2026
- **Reviewed in:** Blue Room, March 19, 2026

This postmortem is blameless. It describes what happened and how our systems allowed it, not who made a mistake.

## Summary

During a planned upgrade of the Kubernetes node pool in il-central-1, two replicas of flow-scheduler acted as leader at the same time for 2 hours and 14 minutes. Both replicas fired every schedule that came due, so scheduled workflows ran twice. In total, 4,812 duplicate runs were executed for 167 customers. Some of these runs had side effects in third-party tools (duplicate emails, duplicate tickets, duplicate rows in spreadsheets).

## Impact

- 4,812 duplicate runs, 167 customer organizations affected.
- 38 customers exceeded their monthly run quota because of the duplicates and would have been charged overage; Billing excluded the duplicate runs from metering before the April invoice run.
- 61 support tickets were opened; 9 of them by Enterprise customers.
- No data was lost and no run was skipped.

## Timeline (Israel time)

- 09:41: Platform starts the planned node pool upgrade for the post-Orca node groups in il-central-1.
- 09:47: The flow-scheduler leader pod is evicted and rescheduled onto a new node.
- 09:52: The new node's clock is 7 seconds ahead because the time sync agent (chrony) was missing from the new node template. The old leader's lease appears expired to the new pod; it takes leadership while the old leader, still running on a draining node, keeps firing schedules. Duplicate runs begin.
- 09:58: First customer ticket about duplicate emails (Business customer).
- 10:20: The alert TriggerDuplicateRate fires after the duplicate rate exceeds its threshold for 15 minutes.
- 10:34: SEV2 declared in #incidents; Yonatan Peled is incident commander.
- 10:51: Root cause suspected: two leaders. Confirmed from logs showing two pods publishing with different lease holder ids.
- 11:05: Mitigation attempt: scaled flow-scheduler to 1 replica. Duplicate rate drops but does not reach zero because the old pod on the draining node is outside the deployment's control after a stuck termination.
- 11:58: The stuck pod is force-deleted.
- 12:06: Duplicate rate at zero. Customer impact ends.
- 12:40: Platform adds chrony to the node template and recreates the affected nodes.
- 14:30: Customer Support sends proactive emails to the 167 affected customers.

## Root cause

flow-scheduler used a lease row in PostgreSQL to elect a leader, with time-based expiry computed on each pod's local clock. The design assumed synchronized clocks and did not use fencing: messages published by a former leader were accepted downstream. When a new node joined without time synchronization, two pods believed they were leader, and nothing downstream rejected the stale leader's messages.

## Contributing factors

- The new node template created during the Orca migration did not include chrony; this was not covered by node acceptance tests.
- The TriggerDuplicateRate alert had a 15-minute evaluation window, so detection took 28 minutes after the first duplicates.
- Scaling down did not stop the old pod, because its termination was stuck on a draining node.

## What went well

- Customer Support identified the pattern from tickets quickly and linked them to the incident.
- Billing excluded duplicate runs from usage before invoicing, so no customer was overcharged.

## Action items

1. Add fencing tokens: every message published by flow-scheduler carries the lease epoch, and flow-engine rejects messages from an older epoch. Owner: Dana Levi (Engine). Done April 2, 2026.
2. Add chrony to the node template and a clock-skew check to node acceptance tests. Owner: Boaz Nahum (Platform). Done March 13, 2026.
3. Reduce the TriggerDuplicateRate evaluation window from 15 minutes to 5 minutes. Owner: Yonatan Peled. Done March 20, 2026.
4. Add a runbook section on stuck pods on draining nodes. Owner: Engine team. Done April 20, 2026 (in the Hebrew scheduler on-call notes).
