---
id: sec-incident-response
title: Security Incident Response Policy
department: it_security
doc_type: policy
version: "2.0"
effective_date: 2026-02-01
owner: Tamar Golan
classification: internal
language: en
---

# Security Incident Response Policy

## Purpose and scope

This policy defines how Acme detects, reports, handles and learns from security incidents: events that threaten the confidentiality, integrity or availability of Acme or customer data. Pure reliability incidents (for example an outage caused by a bad deploy with no security aspect) follow the Engineering incident process described in the on-call runbooks; when an outage has a possible security cause, this policy applies as well.

## What to report

Report immediately, even if you are not sure:

- A lost or stolen laptop, phone or security key.
- A suspicious email that you clicked, or in which you entered credentials.
- Customer data or secrets sent to the wrong person, pasted in a public place, or shared with an unapproved tool (including AI tools).
- Unexpected admin access, unknown devices in your Okta account, or MFA prompts you did not initiate.
- Any sign of unauthorized access to production systems.

## How to report

- Slack: #sec-incidents (monitored 24/7 by the on-call security engineer).
- Email: security@acme.example.
- Phone: the security hotline, +972-3-555-0199, for urgent cases outside working hours.

Never try to investigate on your own by logging in to systems you do not normally use, and never delete evidence.

## Severity levels

- **SEV1 (critical):** confirmed access to customer data by an unauthorized party, active attacker in production, or ransomware. Response begins within 15 minutes, 24/7.
- **SEV2 (high):** likely compromise of an employee account with access to Confidential data, or exposure of production secrets. Response within 1 hour, 24/7.
- **SEV3 (medium):** policy violation with limited exposure, for example Internal data shared with an unapproved tool. Response within 1 business day.
- **SEV4 (low):** suspicious activity with no evidence of compromise. Response within 3 business days.

## Roles

- **Incident Commander (IC):** the on-call security engineer at first; for SEV1 the CISO, Tamar Golan, or her delegate takes over as IC. The IC coordinates, makes decisions, and owns communication.
- **Technical lead:** the engineer driving the investigation and containment.
- **Scribe:** keeps a timeline in the incident document.
- **Communications lead:** for SEV1 and SEV2, someone from Customer Support or Legal handles customer and regulator communication.

For a SEV1, the IC notifies the ERT within 30 minutes of declaring the incident.

## Phases

1. **Detect and triage:** confirm the event, assign severity, open an incident channel named #inc-sec-YYYYMMDD-short-name.
2. **Contain:** revoke sessions and credentials, isolate hosts, block indicators. Containment beats perfect forensics.
3. **Eradicate and recover:** remove the root cause, restore from clean sources, monitor closely.
4. **Notify:** see below.
5. **Learn:** a blameless postmortem within 10 business days for SEV1 and SEV2, reviewed in Blue Room.

## Notification obligations

- Personal data breaches affecting EU residents must be reported to the competent data protection authority within 72 hours of becoming aware of the breach, unless the breach is unlikely to result in a risk to individuals (GDPR Article 33). The Legal team, together with the CISO, decides and files the notification.
- Severe security incidents involving databases of Israeli residents must be reported to the Privacy Protection Authority according to the Israeli Privacy Protection (Data Security) Regulations.
- Enterprise contracts require Acme to notify affected customers of a confirmed security incident involving their data within 48 hours of confirmation.

## Evidence and records

The incident document, Slack channel export and relevant logs are kept for at least 3 years. Logs relevant to an open incident must not be deleted by retention jobs; the IC asks the Platform team to place a legal hold.

## Exercises

The Security team runs a tabletop exercise twice a year with the ERT and a technical drill once a year with the on-call engineers of Tier 1 services.
