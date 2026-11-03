---
id: sec-data-classification
title: Data Classification Policy
department: it_security
doc_type: policy
version: "1.1"
effective_date: 2025-06-01
owner: Tamar Golan
classification: internal
language: en
---

# Data Classification Policy

Every piece of information at Acme has a classification. The classification decides who may see it, where it may be stored, and with which tools it may be processed. When in doubt, choose the higher level and ask in #ask-security.

## The four levels

### Public
Information intended for anyone outside Acme. Examples: the marketing website, published pricing, public API documentation, job postings, published blog posts.
Handling: no restrictions, but only Marketing and the document owner may publish it.

### Internal
Information for Acme employees and contractors with a signed NDA. Examples: most policies, the org chart, internal meeting notes, the architecture overview, the service catalog.
Handling: may be stored in any approved tool (Google Workspace, Confluence, Slack, Jira). Must not be shared outside Acme without a business reason.

### Confidential
Information whose disclosure could harm Acme or a customer. Examples: unreleased financial results, contracts and prices negotiated with specific customers, security reports and penetration test results, postmortems that mention customers by name, salary data in aggregate.
Handling: access on a need-to-know basis. Shared through restricted Google Drive folders or Confluence spaces with explicit permissions. Never sent to personal email. External sharing requires approval through the needs_security track of the SaaS Access Policy.

### Restricted
The most sensitive information. Examples: customer workflow payloads and customer personal data, payment card and bank details, passwords, API keys and other secrets, individual salary and payroll records, health information of employees.
Handling: stored only in the systems designed for it (production databases, the secret manager, the payroll system). Access only through the needs_security track. Never copied to laptops, spreadsheets, Slack, tickets or any AI tool, including Acme-approved AI tools.

## Labeling

Documents should state their classification at the top or in their metadata. Documents without a label are treated as Internal. Restricted data does not live in documents at all.

## The Knowledge Assistant

Acme's internal Knowledge Assistant indexes documents classified Public, Internal and Confidential. Confidential documents are indexed with their access permissions, and the assistant only retrieves them for employees who are allowed to open the source. Restricted information is never indexed. If you find Restricted information in an indexed document, report it in #sec-incidents.

## Retention

- Internal and Confidential documents are reviewed by their owners at least once a year; outdated documents are archived, not deleted, unless the retention schedule requires deletion.
- Customer data is deleted within 30 days after the end of the customer's contract, unless the contract states otherwise.
- Application logs that may contain customer data are retained for 30 days; audit logs for 1 year (3 years for Enterprise customers).

## Responsibilities

- Every document owner sets the classification of their documents.
- The Security team, led by the CISO Tamar Golan, owns this policy and reviews it yearly.
- Violations are handled according to the Security Incident Response Policy.
