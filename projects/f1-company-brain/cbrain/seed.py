"""Demo data for a fresh deployment: three requests, so the approvals tab has something to show.

    python -m cbrain seed                       # locally
    docker compose exec brain python -m cbrain seed
    aws ecs execute-command ... python -m cbrain seed       # see the runbook in README.md

Idempotent: a request whose text is already in brain_threads is not filed again.
"""

from __future__ import annotations

SEED = [
    ("dana", "I need a Figma editor seat for the Q4 dashboard designs."),            # -> Michal (manager gate)
    ("avital", "I need write access to GitHub for the engine repo migration."),      # -> Dana (manager gate)
    ("noa", "I need a Miro member account for the design research board."),          # auto_approve
    ("barak", "Please give me read access to Zendesk to see my customers' tickets."),  # -> security gate
]


def seed(brain) -> dict:
    existing = {(t["requester"], t["text_preview"]) for t in brain.requests.threads()}
    out = []
    for uid, text in SEED:
        p = brain.users[uid]
        if (p.email, text[:160]) in existing:
            out.append({"user": uid, "skipped": "already seeded"})
            continue
        st = brain.start_request_unconfirmed(p, text)
        out.append({"user": uid, "thread_id": st["thread_id"], "status": st["status"], "route": st["route"]})
    return {"seeded": out, "inbox_michal": len(brain.requests.inbox(brain.users["michal"])),
            "inbox_tamar": len(brain.requests.inbox(brain.users["tamar"]))}
