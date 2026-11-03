---
id: sales-sla-2025
title: Acme Flow Service Level Agreement (2025)
department: sales_support
doc_type: contract_terms
version: "1.0"
effective_date: 2025-01-01
owner: Shira Levin
classification: public
language: en
---

# Acme Flow Service Level Agreement (2025)

This Service Level Agreement ("SLA") applies to customers on the Business and Enterprise plans. Starter and Team plans are provided without an uptime commitment.

## 1. Uptime commitment

Acme will make the Acme Flow service available at least 99.9% of the time in each calendar month, for both Business and Enterprise customers.

"Available" means that the public API and the web application respond successfully to requests, measured every minute from at least three external locations. A minute counts as unavailable when more than 5% of requests fail with server errors.

## 2. Service credits

If monthly uptime falls below the commitment, the customer is entitled to a credit on the monthly fee of the affected plan:

| Monthly uptime | Credit |
|---|---|
| below 99.9% but at least 99.0% | 10% |
| below 99.0% | 25% |

The maximum credit for a month is 25% of the monthly fee.

## 3. Requesting credits

Customers must request credits through Customer Support within 30 days after the end of the affected month. Credits are applied to the next invoice and are not paid out in cash.

## 4. Exclusions

Downtime does not count against uptime when caused by scheduled maintenance announced at least 72 hours in advance (up to 4 hours per month), by third-party services outside Acme's control (including connected third-party tools), by the customer's own actions, or by force majeure.

## 5. Sole remedy

Service credits are the customer's sole and exclusive remedy for failure to meet the uptime commitment.
