# Acme SaaS Access Policy (v2.1), as implemented by this service

Every request goes to exactly one track. If a request matches more than one track, the
strictest track wins: `needs_security` > `needs_manager` > `auto_approve`.

## needs_security (the security team reviews)

Any one of these is enough:

- admin, owner or root rights on any system (`access_level == "admin"`)
- production infrastructure (`production: true`, or the tool is AWS, GCP, Kubernetes, production database)
- customer data (`customer_data: true`) or financial systems (`financial_data: true`, or the tool is NetSuite or Payroll)
- sharing company data with an external party (`external_sharing: true`)

## auto_approve (granted immediately)

All of these must hold:

- the tool is on the approved list: Jira, Confluence, Slack, Google Workspace, Zoom, Miro, Figma, GitHub
- the access level is `read` or `standard`
- nothing from the needs_security list applies

## needs_manager (the employee's manager approves)

Everything else, for example a `write` seat on an approved tool, or a tool that is not on
the approved list and holds no sensitive data.

## Decisions

Requests on the `needs_manager` track wait for a manager decision. Requests on the
`needs_security` track are decided by the security team in another system, never here.
A person can never approve their own request.
