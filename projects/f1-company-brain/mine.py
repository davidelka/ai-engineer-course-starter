"""Your code for final project F1 (Company Brain): eleven functions, milestones 3, 4, 5, 6 and 9.

You build the parts of Company Brain that the course taught: the intent router (rules, then a
structured-output model with a safe fallback), the approvals inbox, the security layers (route
hardening, the context screen, spotlighting, the output check), the classification that decides
which model may see a request, the SLO report from the traces, and the routing metrics. The course
gives you the rest ready: the HTTP service and UI, identity and API keys, the LangGraph workflow
engine (flowkit), the gateway, the MCP server, the deployment files.

    M3   rule_intent              classify a message with rules only
    M3   route_message            rules first, then the model, with a safe fallback
    M3   route_metrics            accuracy, per-class precision and recall, errors by direction
    M4   approvals_for            whose requests this person may approve
    M5   harden_route             a suspicious request is never auto-approved
    M5   screen_hits              drop retrieved chunks that carry an injection
    M5   spotlight_sources        mark every source as untrusted data inside the prompt
    M5   validate_output          check the answer before the user sees it
    M6   request_classification   the most sensitive document in the prompt sets the level
    M9   request_rows             one row per request, from the traces
    M9   slo_report               availability, latency and cost per request type, against targets

After milestone 6 every path of Company Brain runs on your code; milestone 7 is the whole story.

Every command (`python -m cbrain ...`, the service, the MCP server, the evaluation) calls these
through cbrain/hooks.py; a command that needs one you have not written yet stops and names the
milestone. Company Brain also runs YOUR M1 for the knowledge path, so finish M1 first. The
reference implementations are on the repo's `solutions` branch, for comparing AFTER your tests
pass. Stuck? HINTS.md has three graded hints per function.

This file is loaded under the module name "f1_mine" (not "mine"), so it never collides with the
mine.py of a lesson or another project in the same Python process (the test suite runs them all).

Run the tests of one milestone:  python -m pytest -q tests/test_m03_router_rules.py
"""

from __future__ import annotations

import re  # noqa: F401
from collections import Counter  # noqa: F401
from dataclasses import replace  # noqa: F401
from typing import Any, Callable, Iterable, Optional  # noqa: F401

from cbrain.guards import _SOURCE_RE, LEVELS  # noqa: F401
from cbrain.obs import AVAILABILITY, COST_USD, LATENCY_MS  # noqa: F401
from cbrain.router import INTENTS, ROUTER_SYSTEM, IntentDecision, RouteResult  # noqa: F401
from guardkit.answerer import CANARY  # noqa: F401
from guardkit.models import DATAMARK  # noqa: F401
from guardkit.validate import check_output  # noqa: F401
from obskit.analyze import percentile, span_cost  # noqa: F401
from obskit.exporters import by_trace, root_of  # noqa: F401


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


# ---------------------------------------------------------------- milestone 3: rules, then the model
def route_message(text: str, *, rules: Callable, llm: Any = None, llm_mode: str = "auto",
                  min_confidence: float = 0.5) -> RouteResult:
    """Route one message: RouteResult(intent, confidence, source, matched, reason="", llm=None).

    `rules(text)` is your rule_intent. `llm_mode` is "auto" (rules first), "always" (always ask the
    model) or "never" (rules only). `matched` is always the rules' matched list.
    - rules gave an intent and llm_mode != "always"  -> that intent and confidence, source "rules".
    - no model (llm is None) or llm_mode == "never"  -> the rules' intent, or "knowledge" when they had
      none, with the rules' confidence (0.0 when missing), source "fallback",
      reason "rules unsure, no model: safe default".
    - otherwise ask the model with llmkit.structured.complete_structured(llm, prompt, IntentDecision,
      system=ROUTER_SYSTEM, max_repairs=1, max_tokens=200), where prompt is
      "<message>\n" + text + "\n</message>". The result's .value is an IntentDecision (intent,
      confidence, reason); llm is {"intent", "confidence", "cost_usd" (res.cost_usd or 0.0),
      "input_tokens", "output_tokens"}.
      - StructuredError or LLMError (llmkit.errors) -> "knowledge", 0.0, source "fallback",
        reason "router model failed (<exception class name>): safe default", llm None.
      - confidence below min_confidence -> "knowledge", the model's confidence, source "fallback",
        reason f"model unsure ({intent}, {confidence:.2f}): safe default", and llm filled.
      - else -> the model's intent and confidence, source "llm", reason = the model's reason, llm filled.
    "knowledge" is the safe default: a wrong answer there is a question, a wrong access request is a
    ticket in someone's inbox.

    Stuck? HINTS.md -> route_message
    """
    # TODO(milestone 3)
    raise NotImplementedError("milestone 3: implement route_message")


# ---------------------------------------------------------------- milestone 3: routing metrics
def route_metrics(rows: list[dict]) -> dict:
    """The routing evaluation for one router mode, from one row per labeled message.

    A row: {"id", "label", "pred", "source" ("rules" | "llm" | "fallback"), "llm_called" (bool),
    "cost" (USD)}. Returns:
        "n", "accuracy" (pred == label share, 0.0 when empty), "ci95": _wilson-style 95% interval of
        the accuracy, as (low, high) rounded to 3 places (evalkit.stats.wilson_ci(k, n)),
        "per_class": {intent: {"precision", "recall", "n" (rows with that label)}} for each intent in
        INTENTS, where precision or recall is None when its denominator is 0,
        "llm_calls": rows whose source is "llm" or that have llm_called,
        "llm_rate": the share of rows with llm_called (0.0 when empty),
        "errors_by_direction": {"<label>-><pred>": count} over the wrong rows,
        "cost_usd": the sum of cost, rounded to 6 places,
        "errors": [{"id", "label", "pred", "source"}] for the wrong rows, in order.

    Stuck? HINTS.md -> route_metrics
    """
    # TODO(milestone 3)
    raise NotImplementedError("milestone 3: implement route_metrics")


# ---------------------------------------------------------------- milestone 4: the approvals inbox
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


# ---------------------------------------------------------------- milestone 5: suspicious requests
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


# ---------------------------------------------------------------- milestone 5: the context screen
def screen_hits(hits: list, screen: Callable) -> tuple[list, list[dict]]:
    """Drop retrieved chunks that look like an injection, before they reach the prompt.

    `hits` are ragkit Hits (h.chunk.text, h.chunk.doc_id, h.chunk.id), best first. `screen(text)`
    returns a ScreenResult with .flagged (bool) and .reasons (list).
    Returns (kept, dropped):
    - kept: the hits that were not flagged, in order, as NEW Hits with rank renumbered 1..n
      (dataclasses.replace); the input is not modified;
    - dropped: one dict per flagged hit, in order: {"doc_id", "chunk_id", "reasons"}.

    Stuck? HINTS.md -> screen_hits
    """
    # TODO(milestone 5)
    raise NotImplementedError("milestone 5: implement screen_hits")


# ---------------------------------------------------------------- milestone 5: spotlighting
def spotlight_sources(user: str, nonce: str) -> str:
    """Mark the body of every source in the prompt as untrusted data (lesson 24, spotlighting).

    `user` is the user message M1 builds: blocks of '<source id="2" ...>\n' + body + '\n</source>'
    (the regex _SOURCE_RE, from cbrain/guards.py, finds them with three groups: the opening tag
    line, the body, and the closing line). Everything outside the blocks stays exactly as it is.
    In each block:
    - the body's runs of spaces and tabs become DATAMARK (one marker per run; newlines stay);
    - the body is wrapped: "<<untrusted id=N nonce=NONCE>>\n" + body + "\n<</untrusted nonce=NONCE>>",
      where N is the number in the tag's id attribute ("?" when there is none);
    - the opening and closing tag lines stay around it, so the result is
      opening + wrapped + closing.
    The nonce changes per request, so a document cannot forge a closing marker in advance.

    Stuck? HINTS.md -> spotlight_sources
    """
    # TODO(milestone 5)
    raise NotImplementedError("milestone 5: implement spotlight_sources")


# ---------------------------------------------------------------- milestone 5: the output check
def validate_output(text: str) -> list[dict]:
    """Check an answer before the user sees it. [] means clean.

    One {"kind": f.kind, "detail": f.detail} for each finding of guardkit.validate.check_output(text)
    (markdown images that could leak data, requests for credentials, ...), in its order; then, when
    the system prompt's canary (CANARY, from guardkit.answerer) appears in the text, one more:
    {"kind": "secret_leak", "detail": "system prompt canary"}. None or "" is clean.

    Stuck? HINTS.md -> validate_output
    """
    # TODO(milestone 5)
    raise NotImplementedError("milestone 5: implement validate_output")


# ---------------------------------------------------------------- milestone 6: data classification
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


# ---------------------------------------------------------------- milestone 9: requests from the traces
def request_rows(spans: Iterable[dict]) -> list[dict]:
    """One row per Company Brain request, built from exported spans (obskit's JSON format).

    Group the spans by trace (obskit.exporters.by_trace) and take each trace's root (root_of). A trace
    is a brain request when its root's attributes have "brain.request_type" ("ask", "request" or
    "decide"); skip the others. The row:
        {"trace_id", "type": the request type, "t_ms": root["start_ms"], "duration_ms": root["duration_ms"],
         "error": root.get("status") == "ERROR", "cost_usd": the sum of span_cost(s) over ALL the trace's
         spans, "llm_calls": how many spans have attributes["gen_ai.operation.name"] in ("chat",
         "text_completion"), "intent": root attributes.get("brain.intent"), "spans": the number of spans}
    Rows sorted by t_ms.

    Stuck? HINTS.md -> request_rows
    """
    # TODO(milestone 9)
    raise NotImplementedError("milestone 9: implement request_rows")


def slo_report(spans: Iterable[dict]) -> dict:
    """The SLO report: {"requests": <number of rows>, "by_type": {type: metrics}}, types sorted.

    Rows come from request_rows(spans). For each type, with rs its rows, ok the rows without error,
    d the durations of ok, c the costs of rs, lat_t = LATENCY_MS.get(type, 8000.0) and
    cost_t = COST_USD.get(type, 0.005):
        "n": len(rs), "errors": len(rs) - len(ok),
        "availability": len(ok) / len(rs), "availability_ok": availability >= AVAILABILITY,
        "p50_ms", "p95_ms": percentile(d, 50) and percentile(d, 95) (0.0 when d is empty),
        "latency_target_ms": lat_t, "latency_sli": the share of d that is <= lat_t (1.0 when empty),
        "latency_ok": p95 <= lat_t,
        "cost_mean_usd", "cost_p95_usd" (percentile(c, 95)), "cost_total_usd", "cost_target_usd": cost_t,
        "cost_ok": cost_mean_usd <= cost_t,
        "llm_calls_mean": the mean of llm_calls over rs.
    Latency is measured on successful requests only: a fast error is not a good request.

    Stuck? HINTS.md -> slo_report
    """
    # TODO(milestone 9)
    raise NotImplementedError("milestone 9: implement slo_report")
