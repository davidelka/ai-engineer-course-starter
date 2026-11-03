---
id: eng-runbook-billing
title: On-call Runbook - billing-service
department: engineering
doc_type: runbook
version: "2.3"
effective_date: 2026-07-01
owner: Rina Sasson
classification: internal
language: en
---

# On-call Runbook: billing-service

`billing-service` meters usage, calculates invoices and talks to the payment provider. It is a Tier 1 service owned by the Billing team (lead: Rina Sasson). Mistakes here cost customers money and trust, so the rule is simple: when in doubt, stop the invoice run and ask.

## Rotation

- Rotation name: billing-oncall. Weekly, handover on Wednesday at 12:00 Israel time in #billing-oncall. The handover is in the middle of the week so that the person on call during the invoice run (1st and 2nd of the month) is never in their first or last day of the shift.
- Primary and secondary. Acknowledge within 5 minutes.
- Escalation: Rina Sasson, then the CFO's delegate for anything that affects invoices already sent (Keren Amar, Controller).

## The monthly calendar

- 1st of the month, 00:00 UTC: deploy freeze for billing-service begins.
- 1st of the month, 02:00 UTC: usage for the previous month is closed. Late usage events are added to the next month.
- 2nd of the month, 04:00 UTC: the dry run produces draft invoices and a shadow comparison with the previous month (added after the June 2026 incident).
- 2nd of the month, 06:00 UTC: the invoice run creates final invoices and sends them by email; card payments are charged at 09:00 UTC.
- The freeze ends when the invoice run is marked complete by the on-call engineer.

## Alerts and what to do

### InvoiceShadowDiffHigh
Fires when the dry run shows that more than 1% of customers would be charged more than 20% above their previous invoice, without a matching change in seats or usage.

1. Do not let the invoice run start. Pause it: `acmectl billing invoice-run pause --month <YYYY-MM>`.
2. Page Rina Sasson. Look at the sample of affected customers in the alert.
3. The run may be resumed only with the approval of the Billing team lead.

### UsageEventsLagHigh
Fires when `usage.events` consumer lag exceeds 30 minutes. Usage is eventually consistent; lag during the month is not urgent, but lag on the 1st of the month before 02:00 UTC is. Page platform-oncall if Kafka is the cause.

### PaymentProviderErrors
Fires when more than 5% of charge attempts fail with provider errors (not card declines). Pause charging, check the provider's status page, and inform Customer Support. Declined cards are normal and handled by dunning emails automatically.

### InvoiceEmailBounces
A spike in bounces usually means the email provider is blocking us. Inform integrations-oncall (notifications service).

## Corrections and refunds

- Corrections to sent invoices are made only through `acmectl billing credit-note create`, never by editing the database.
- Refunds follow the Refund Policy owned by Customer Support. Billing errors caused by Acme are always refunded in full.
- Any correction affecting more than 10 customers must be reported to Rina Sasson and Keren Amar the same day.

## Severity guide for billing-service

- SEV1: customers charged incorrectly (wrong amounts sent or charged), or invoices sent to the wrong customer.
- SEV2: the invoice run is delayed by more than 12 hours, or charging is failing broadly.
- SEV3: usage lag or metering errors that are caught before invoicing.

## Data handling

Billing data is Restricted when it contains payment details and Confidential otherwise. Do not paste invoice contents into Slack threads; link to the invoice in the admin console instead.
