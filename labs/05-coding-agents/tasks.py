"""The two tasks the agent gets in exercise 8, with their hidden acceptance tests.

The prompts are what a teammate would write in a ticket: they state the requirement
precisely, but they do not say which file to change or how to run the tests. Finding that
out is exactly where project configuration (CLAUDE.md, skills, hooks) should help.
"""

from __future__ import annotations

TASKS = {
    "bugfix": {
        "title": "ACME-142: sensitive requests on approved tools are auto-approved",
        "acceptance": "acceptance/test_task_bugfix.py",
        "prompt": """Bug report ACME-142.

A request for read access to Slack with customer_data=true was auto-approved yesterday.
According to the access policy (docs/policy.md), any request that involves customer data,
financial data, production, admin rights or external sharing must go to needs_security,
and when several tracks match, the strictest one wins.

Fix the bug, add a regression test, and make sure the whole test suite and the linter pass.
Reply with a two-line summary of the root cause and the fix.""",
    },
    "feature": {
        "title": "Manager decision endpoint",
        "acceptance": "acceptance/test_task_feature.py",
        "prompt": """Add an endpoint that lets a manager decide on a pending access request.

POST /requests/{id}/decision
Body: {"decision": "approve" | "deny", "approver_email": "<email>", "comment": "<optional text>"}

Rules, checked in this order:
- unknown id -> 404
- the request is not pending (for example it was auto-approved, or already decided) -> 409
- the request is on the needs_security track -> 403 (the security team decides those elsewhere)
- approver_email equals the requester_email (case-insensitive) -> 403 (no self-approval)
- an invalid body (for example decision "maybe") -> 422

On success return 200 with the updated request: status "approved" or "denied", plus two
new fields on the stored request, decided_by (the approver email) and decided_at (UTC
timestamp). GET /requests/{id} must show the same values afterwards. Both new fields are
null on requests nobody has decided yet.

Add tests for the success path and for every error case, and make sure the whole test
suite and the linter pass. Reply with a short summary of what you changed.""",
    },
}
