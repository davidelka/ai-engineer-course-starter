"""Your code for final project F1 (Company Brain): four functions, milestones 3, 5, 6 and 7.

Every command (`python -m cbrain ...`, the service, the MCP server, the evaluation) calls these
through cbrain/hooks.py. While a function still raises NotImplementedError, the reference version
is used instead (with a one-line note on stderr), so the system always runs and you see the effect
of your code on the evaluation the moment it works. `--reference` forces the references.

This file is loaded under the module name "f1_mine" (not "mine"), so it never collides with the
mine.py of a lesson or another project in the same Python process (the test suite runs them all).

Run the tests of one milestone:  python -m pytest -q tests/test_m03_router_rules.py
"""

from __future__ import annotations

from typing import Optional


# ---------------------------------------------------------------- milestone 3: the router's rules
def rule_intent(text: str) -> dict:
    """Classify a message with RULES ONLY. Return {"intent", "confidence", "matched"}.

    intent is "access_request", "knowledge", "data", or None ("not sure: ask the model").
    matched is a list of short labels of the rules that fired (for the trace and the eval).

    Use the regexes in cbrain/router.py (REQUEST_RE, ACCESS_OBJECT_RE, POLICY_QUESTION_RE, DATA_RE,
    QUESTION_RE, ACCESS_WORD_RE) and acmeqa's data router (`from acmeqa.router import route_question`):

    1. Empty or whitespace text -> intent None, confidence 0.0, matched [].
    2. request = REQUEST_RE matches AND ACCESS_OBJECT_RE matches  (label "request")
       ("I need", "can I get", "please grant", "צריכה", "אפשר לקבל"... AND an access word, a level
       or a known system: "access", "seat", "admin", "editor", "figma", "גישה", "הרשאה"...)
       policy_q = POLICY_QUESTION_RE matches  (label "policy_question")
       ("who approves", "how long does it take", "what is the policy", "מי מאשר", "כמה זמן"...)
    3. request and not policy_q -> "access_request", 0.9
    4. request and policy_q     -> None, 0.5      (a mixed message: "what's the process, and can you
                                                 file it for me?" is for the model to decide)
    5. policy_q                 -> "knowledge", 0.85
    6. route_question(text).kind == "data" -> "data", 0.8, and matched = "data:" + each of the
       route's `matched` labels (e.g. ["data:how many"])
    7. DATA_RE matches (people, grants, "per department"... that M1's router does not know)
       -> "data", 0.8, matched ["data_rule"]
    8. ACCESS_WORD_RE matches and the text is NOT a question (QUESTION_RE does not match): it talks
       about access but neither asks for it nor asks a question ("figma editor for dana please")
       -> None, 0.4, matched ["access_word"]
    9. anything else -> "knowledge", 0.6, matched ["default"]  (a question that merely names a
       system, "when is billing-service frozen for deploys?", is a knowledge question)

    Order matters: a request that also mentions "how many" is still a request (rule 3 before 6).
    """
    raise NotImplementedError


# ---------------------------------------------------------------- milestone 5: the approvals inbox
def approvals_for(principal, items: list[dict]) -> list[dict]:
    """The pending approvals one user may decide, oldest first.

    principal: a cbrain.auth.Principal (fields: employee_id, is_security, ...).
    items: one dict per workflow paused at a gate, with at least these keys:
        "gate"          "manager" | "security"
        "employee_id"   who needs the access (e.g. "E016")
        "requester_id"  who filed it (usually the same person)
        "manager_id"    the employee's direct manager in the directory (e.g. "E005")
        "created_at"    ISO timestamp string

    Rules (SPEC-006 REQ-8 and REQ-9, the same ones flowkit enforces when the decision arrives):
    - A principal without an employee_id (the "ops" admin) sees nothing: not in the directory,
      no authority.
    - Nobody sees a request where they are the employee or the requester (no self-approval).
    - A security-team member sees every remaining item, both gates (security may also decide a
      needs_manager request).
    - Anyone else sees only "manager" gate items whose manager_id is their employee_id.
    - Sort by created_at ascending. Do not mutate the input list or its dicts.

    The inbox is a convenience, not the security boundary: flowkit re-checks the directory when
    the decision arrives. But an inbox that shows requests you cannot decide trains people to
    click buttons that fail, and leaks who asked for what.
    """
    raise NotImplementedError


# ---------------------------------------------------------------- milestone 6: suspicious requests
def harden_route(policy: dict, flags: list[str]) -> dict:
    """Make the policy result stricter when the request text looked like an injection attempt.

    policy: flowkit's check_policy result, e.g.
        {"route": "auto_approve", "reasons": ["approved tool", "basic seat"], ...other keys...}
    flags: the reasons guardkit's detector gave for the request text ([] = clean).

    Return a NEW dict (never mutate `policy`), with every original key kept, and:
    - flags empty -> an unchanged copy, with "hardened": False.
    - route "auto_approve" and flags -> route "needs_manager", reasons + one new reason
      "suspicious request text (<flags joined by ', '>): never auto-approved", "hardened": True.
    - route "needs_manager" or "needs_security" and flags -> same route, reasons + the same new
      reason (so the approver sees why), "hardened": True.
    - any other route (unknown, missing) -> route "needs_security", reasons + "unknown route
      <route!r>: failing closed", "hardened": True, whether or not there are flags.

    A rule like this never makes a request LESS strict: it can only move it up.
    """
    raise NotImplementedError


# ---------------------------------------------------------------- milestone 7: data classification
LEVELS = ("public", "internal", "confidential", "restricted")


def request_classification(chunks_meta: list[dict], floor: Optional[str] = "internal") -> str:
    """The data classification of one model call: the highest classification among the chunks
    that go into the prompt, and never lower than `floor`. The gateway uses it to pick which
    deployments may receive the call (policy.yaml) and what to redact.

    chunks_meta: the metadata of every chunk in the prompt, each a dict that may have a
    "classification" key.
    - Order: public < internal < confidential < restricted (LEVELS).
    - A chunk without a classification (missing, None or "") counts as "internal": Acme's policy
      says unlabeled data is internal (sec-data-classification.md).
    - A classification that is not one of LEVELS (a typo, "secret") counts as "restricted":
      fail closed, the gateway will refuse and someone will fix the label.
    - Comparison is case-insensitive and ignores surrounding spaces ("Confidential ").
    - floor None means "internal". An empty chunk list returns the floor.
    """
    raise NotImplementedError
