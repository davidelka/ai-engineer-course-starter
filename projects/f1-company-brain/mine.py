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

    intent: "access_request", "knowledge", "data", or None ("not sure: ask the model").
    matched: short labels of the rules that fired (for the trace and the eval).
    The cues come from cbrain/router.py (REQUEST_RE, ACCESS_OBJECT_RE, POLICY_QUESTION_RE, DATA_RE,
    QUESTION_RE, ACCESS_WORD_RE) and acmeqa.router.route_question. The required outcomes, where
    the first description that fits wins:
      empty or whitespace                          -> None, 0.0, []
      asks for access (a request phrase AND an access object), not a policy question
                                                   -> "access_request", 0.9, ["request"]
      asks for access AND asks a policy question   -> None, 0.5, ["request", "policy_question"]
      a policy question ("who approves", "מי מאשר") -> "knowledge", 0.85, ["policy_question"]
      M1's router says data                        -> "data", 0.8, "data:" + each of its matched
                                                      labels (e.g. ["data:how many"])
      DATA_RE matches (people, grants, "per department")
                                                   -> "data", 0.8, ["data_rule"]
      mentions access but is not a question ("figma editor for dana please")
                                                   -> None, 0.4, ["access_word"]
      anything else                                -> "knowledge", 0.6, ["default"]
    A request that also mentions "how many" is still a request.

    Stuck? HINTS.md -> rule_intent
    """
    raise NotImplementedError


# ---------------------------------------------------------------- milestone 5: the approvals inbox
def approvals_for(principal, items: list[dict]) -> list[dict]:
    """The pending approvals one user may decide, oldest first (sorted by created_at).

    principal: a cbrain.auth.Principal (fields: employee_id, is_security, ...).
    items: one dict per workflow paused at a gate, with at least these keys:
        "gate"          "manager" | "security"
        "employee_id"   who needs the access (e.g. "E016")
        "requester_id"  who filed it (usually the same person)
        "manager_id"    the employee's direct manager in the directory (e.g. "E005")
        "created_at"    ISO timestamp string
    Rules (SPEC-006 REQ-8 and REQ-9, which flowkit enforces again when the decision arrives):
    - a principal without an employee_id (the "ops" admin) sees nothing;
    - nobody sees a request where they are the employee or the requester (no self-approval);
    - a security-team member sees every other item, both gates;
    - anyone else sees only "manager" gate items whose manager_id is their employee_id.
    Do not mutate the input list or its dicts.

    Stuck? HINTS.md -> approvals_for
    """
    raise NotImplementedError


# ---------------------------------------------------------------- milestone 6: suspicious requests
def harden_route(policy: dict, flags: list[str]) -> dict:
    """Make the policy result stricter when the request text looked like an injection attempt.

    policy: flowkit's check_policy result, e.g.
        {"route": "auto_approve", "reasons": ["approved tool", "basic seat"], ...other keys...}
    flags: the reasons guardkit's detector gave for the request text ([] = clean).
    Return a NEW dict (never mutate `policy`) that keeps every original key, plus "hardened":
    - no flags (and a known route) -> an unchanged copy, "hardened": False.
    - flags: "auto_approve" becomes "needs_manager"; "needs_manager" and "needs_security" stay.
      reasons gets one new last line, exactly:
      "suspicious request text (<flags joined by ', '>): never auto-approved"; "hardened": True.
    - any other route (unknown or missing), flags or not -> "needs_security", reasons + the line
      "unknown route <route!r>: failing closed", "hardened": True.
    A rule like this never makes a request LESS strict.

    Stuck? HINTS.md -> harden_route
    """
    raise NotImplementedError


# ---------------------------------------------------------------- milestone 7: data classification
LEVELS = ("public", "internal", "confidential", "restricted")


def request_classification(chunks_meta: list[dict], floor: Optional[str] = "internal") -> str:
    """The data classification of one model call: the highest classification among the chunks
    in the prompt, never lower than `floor`. The gateway uses it to choose which deployments may
    receive the call (policy.yaml) and what to redact. Returns one of LEVELS.

    chunks_meta: one metadata dict per chunk; it may have a "classification" key.
    - Order: public < internal < confidential < restricted (LEVELS).
    - No classification (missing, None or "") counts as "internal" (sec-data-classification.md:
      unlabeled data is internal).
    - A value that is not in LEVELS (a typo, "secret") counts as "restricted": fail closed.
    - Case-insensitive, surrounding spaces ignored ("Confidential ").
    - floor None means "internal". An empty chunk list returns the floor.

    Stuck? HINTS.md -> request_classification
    """
    raise NotImplementedError
