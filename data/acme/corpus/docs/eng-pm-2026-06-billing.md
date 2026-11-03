---
id: eng-pm-2026-06-billing
title: "Postmortem: EUR invoices overcharged (June 2026 invoice run)"
department: engineering
doc_type: postmortem
version: "1.1"
effective_date: 2026-06-15
owner: Rina Sasson
classification: confidential
language: en
---

# Postmortem: EUR invoices overcharged in the June 2026 invoice run

- **Date of incident:** June 2-3, 2026 (detected June 3)
- **Severity:** SEV1 (incorrect charges to customers)
- **Affected service:** billing-service
- **Incident commander:** Rina Sasson (Billing team lead)
- **Reviewed in:** Blue Room, June 11, 2026

## Summary

The June 2 invoice run (for May usage) overcharged 312 customers who are billed in euros. The total overcharge was €48,900, an average of about €157 per affected customer. The cause was a combination of a rounding change deployed on June 1 and an existing currency conversion bug in the overage calculation. Customers billed in US dollars or shekels were not affected. All affected customers received corrected invoices, full refunds of the overcharged amount, and a goodwill credit.

## Impact

- 312 customers overcharged, all billed in EUR (mostly customers served by the Berlin team).
- Total overcharge: €48,900. The largest single overcharge was €2,310.
- 171 of the 312 customers were charged automatically by card on June 2 at 09:00 UTC before the problem was found. The others pay by bank transfer and had not yet paid.
- 94 support tickets in 36 hours, most of them handled by the EMEA support team in Berlin.

## Timeline (UTC)

- May 31, 21:10: billing-service v4.18.0 is deployed, 2 hours and 50 minutes before the monthly deploy freeze starts (see the note below the timeline).
- June 2, 06:00: The invoice run creates and emails final invoices.
- June 2, 09:00: Card payments are charged.
- June 3, 05:15: A Berlin support agent notices three tickets complaining about unusually high overage charges and opens a P2 escalation.
- June 3, 06:40: Billing on-call (Nadav Eshel) confirms that overage lines on EUR invoices are wrong. SEV1 declared; Rina Sasson takes over as incident commander.
- June 3, 07:30: Charging of pending invoices is paused; the scope (312 customers) is identified.
- June 3, 11:00: Customer Support sends a first email to affected customers.
- June 5: Corrected invoices issued to all 312 customers.
- June 10: All refunds issued (card refunds) and corrected payment instructions sent (bank transfers).

Note on the deploy time: the original version of this document said the deploy happened on June 1. The Conveyor log shows the deploy happened on May 31 at 21:10 UTC, before the freeze. The deploy did not violate the freeze.

## Root cause

Version 4.18.0 changed how overage charges are rounded: from rounding once per invoice to rounding each usage line separately, to match how line items are displayed. For EUR invoices, overage prices are converted from the USD price list. An older bug applied the USD-to-EUR conversion to each line after rounding, and then again on the invoice total. With per-invoice rounding the double conversion only touched one number that was later recomputed; with per-line rounding it was applied to every line and kept. Our tests had no fixtures for EUR invoices with overage.

## Contributing factors

- No comparison between draft invoices and the previous month existed; a 20%+ jump for hundreds of customers went unnoticed.
- The invoice run was not gated on any human review.
- EUR customers are a minority (about 16% of customers), so overall revenue metrics looked normal.

## What went well

- The Berlin support team escalated quickly after only three tickets.
- Pausing charges early prevented a further 141 customers from being charged.

## Customer remediation

- Billing errors caused by Acme are refunded in full, as stated in the Refund Policy; all 312 customers received the full overcharged amount back.
- In addition, the VP Customer Support approved a goodwill credit of 10% of the May invoice for every affected customer.

## Action items

1. Add a dry run with a shadow comparison against the previous month, two hours before the invoice run, and the InvoiceShadowDiffHigh alert. Owner: Rina Sasson. Done June 28, 2026.
2. Add EUR and ILS fixtures with overage to the billing test suite. Owner: Nadav Eshel. Done June 20, 2026.
3. Fix the double currency conversion. Owner: Billing team. Done June 4, 2026 (hotfix v4.18.1).
4. Require Billing team lead approval in Conveyor for any billing-service deploy in the last 3 days of the month. Owner: Boaz Nahum (Platform). Done July 2, 2026.
