---
id: it-saas-access-v2-2
title: SaaS Access Policy (v2.2)
department: it_security
doc_type: policy
version: "2.2"
effective_date: 2026-06-01
owner: Tamar Golan
classification: internal
language: en
supersedes: it-saas-access-v2-1
---

# Acme Ltd. — SaaS Access Policy (v2.2)

Version 2.2 keeps the three tracks and the approved tool list of version 2.1 unchanged. It changes the review timelines, adds time-limited access, and moves access reviews from twice a year to quarterly. A summary of changes is at the end.

Every access request is routed to exactly one of three tracks.

## auto_approve
Granted immediately, no human review, when ALL of these hold:
- The tool is on the approved list: Jira, Confluence, Slack, Google Workspace, Zoom, Miro, Figma (viewer), GitHub (read).
- The access level is read-only, viewer, or a standard member seat with no admin rights.
- The data involved is not customer data and not financial data.

## needs_manager
The employee's direct manager approves when:
- The tool is on the approved list but the request is for a paid seat (e.g. Figma editor, Miro paid board owner), OR
- The tool is NOT on the approved list but holds no customer or financial data (e.g. a new design or note-taking tool), OR
- The request is write access to a team-owned resource (e.g. GitHub write on a team repo).

## needs_security
The security team reviews when ANY of these hold:
- Admin, owner, or root rights on any system.
- Access to production infrastructure (AWS, GCP, Kubernetes production clusters, production databases).
- Access to customer data (CRM exports, support tickets with PII) or financial systems (NetSuite, payroll).
- Sharing company data with an external party or connecting a third-party app via OAuth to Google Workspace.

If a request matches more than one track, the strictest track wins (needs_security > needs_manager > auto_approve).

## Process

- Requests are submitted in the #access-requests Slack channel or by email to access@acme.example. The access bot parses the request and routes it.
- Manager approvals are expected within 2 business days.
- Security reviews are completed within 2 business days. Urgent production access for an active incident can be granted by the on-call security engineer within 30 minutes.
- Access granted through the needs_security track is time-limited: by default it expires after 90 days and must be renewed. Incident-time access expires after 24 hours.
- All grants are recorded in the access register and reviewed quarterly by the owners of each system.

## Summary of changes from v2.1

- Security review target: from 3 business days to 2 business days.
- New: needs_security grants expire after 90 days by default; incident access after 24 hours.
- Access reviews: from twice a year to quarterly.
