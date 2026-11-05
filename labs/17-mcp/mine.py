"""Lesson 17: your code. Three coding exercises (3, 4 and 7). Each function raises
NotImplementedError until you write it. The tests are in tests/; run them with
    python -m pytest -q labs/17-mcp/tests

Reference implementations exist in mcpkit/ (oncall.py, bridge.py, pinning.py). Don't read them
before your tests pass.

Each docstring is a contract: what goes in, what comes out, and the rules the result must follow.
When you are stuck, HINTS.md has graded hints for every function (direction, structure, full algorithm).
"""

from __future__ import annotations

from typing import Any, Optional

from llmkit.types import Tool, ToolCall, ToolResult
from toolkit import ToolError  # raise this for expected failures: the executor turns it into is_error

# =====================================================================================================
# Exercise 3: a new MCP tool, get_oncall_for_service
# =====================================================================================================
#
# The data: data/acme/corpus/docs/eng-service-catalog.md, section "## Production services".
# Read it with:  from mcpkit.oncall import catalog_text;  text = catalog_text()
# The table (abridged; the real file has these 9 rows exactly):
#
# | Service | Owner team | Team lead | Tier | On-call rotation | PagerDuty service |
# |---|---|---|---|---|---|
# | flow-api | Core API | Itai Barak | 1 | core-api-oncall: weekly, handover Sunday 10:00 | flow-api-prod |
# | flow-engine | Engine | Dana Levi | 1 | engine-oncall: weekly, handover Sunday 10:00 | flow-engine-prod |
# | flow-scheduler | Engine | Dana Levi | 1 | engine-oncall (shared with flow-engine) | flow-scheduler-prod |
# | auth-service | Identity | Gil Avraham | 1 | identity-oncall: weekly, handover Thursday 10:00; secondary is platform-oncall | auth-service-prod |
# | billing-service | Billing | Rina Sasson | 1 | billing-oncall: weekly, handover Wednesday 12:00 | billing-prod |
# | connectors-hub | Integrations | Omer Haddad | 2 | integrations-oncall: weekly, handover Monday 10:00 | connectors-prod |
# | notifications | Integrations | Omer Haddad | 2 | integrations-oncall (shared with connectors-hub) | notifications-prod |
# | web-app | Frontend | Maya Rosen | 2 | frontend-oncall: weekly, handover Sunday 10:00 | web-app-prod |
# | lighthouse | Data | Eitan Klein | 3 | business hours, #data-help | none |
#
# Tier rules from the same document: Tier 1 = 24/7, acknowledge a page within 5 minutes;
# Tier 2 = 24/7, acknowledge within 15 minutes; Tier 3 = business hours only, no pages.
# Runbooks: a corpus document whose front-matter title ends with " - <service>" is that service's
# runbook: "On-call Runbook - flow-api" (eng-runbook-flow-api), "On-call Runbook - flow-engine"
# (eng-runbook-flow-engine), "On-call Runbook - billing-service" (eng-runbook-billing),
# "הערות כונן - flow-scheduler" (eng-oncall-scheduler-he). The other services have none.


def get_oncall_for_service(service: str, catalog: Optional[str] = None) -> dict:
    """Who is on call for one production service, from the catalog's "Production services" table.

    service: matched case-insensitively after strip(); spaces and underscores count as dashes
        ("Flow API" is not a service, "flow_api" -> "flow-api").
    catalog: the catalog Markdown text; None means read the real file (mcpkit.oncall.catalog_text()).
        Only the "## Production services" table counts, not other tables in the document.

    Returns a dict with EXACTLY these keys (values for flow-api unless noted):
        service "flow-api" (as written in the table), owner_team "Core API", team_lead "Itai Barak",
        tier 1 (an int), rotation "core-api-oncall" (None for lighthouse), schedule "weekly, handover
        Sunday 10:00" (a shared rotation gets the schedule of the row that defines it; None when there
        is none), secondary "platform-oncall" for auth-service else None, shared_with "flow-engine" for
        flow-scheduler else None, channel "#data-help" for lighthouse else None, pagerduty_service
        "flow-api-prod" (None for "none"), coverage and ack_minutes from the tier rules above,
        runbook (the doc id from the runbook rule above, or None), source "eng-service-catalog".

    Errors (ToolError, written for the model): empty service -> a message containing "empty";
    unknown service -> the message names the requested service and either close matches
    (difflib.get_close_matches, cutoff 0.5: "flow-ap" -> "flow-api") or, when nothing is close,
    every known service name.

    Stuck? HINTS.md -> get_oncall_for_service
    """
    raise NotImplementedError("exercise 3")


# =====================================================================================================
# Exercise 4: the MCP -> llmkit bridge
# =====================================================================================================
#
# An MCP tool, as JSON (exactly what tools/list returns; this is acme-mcp's get_oncall_for_service,
# description cut short):
#   {"name": "get_oncall_for_service",
#    "title": "get oncall for service",
#    "description": "Who is on call for ONE Acme production service ...",
#    "inputSchema": {"type": "object", "title": "get_oncall_for_serviceArguments",
#                    "properties": {"service": {"type": "string", "title": "Service", "description": "..."}},
#                    "required": ["service"]},
#    "annotations": {"title": "get oncall for service", "readOnlyHint": true, "openWorldHint": false}}
#
# An MCP tools/call result, as JSON:
#   {"content": [{"type": "text", "text": "{\"service\": \"flow-api\", ...}"}],
#    "structuredContent": {"service": "flow-api", ...},
#    "isError": false}
#
# llmkit's Tool: Tool(name, description, input_schema, strict=False). Names must match
# ^[a-zA-Z0-9_-]{1,64}$ on all three providers.


def mcp_tool_to_llmkit(tool: dict, server: Optional[str] = None) -> Tool:
    """One MCP tool (the JSON dict above) -> llmkit Tool. The input dict is never mutated.

    name: f"{server}__{tool['name']}" when server is given, else tool["name"], made legal for every
        provider: each character outside [a-zA-Z0-9_-] becomes "_". A name still longer than 64
        characters becomes its first 55 characters + "_" + the first 8 hex characters of the sha256
        (utf-8) of the name BEFORE the replacement, so long names stay unique.
    description: tool["description"], else tool["title"], else the name; stripped.
    input_schema: an independent (deep) copy of tool["inputSchema"] (or {} if missing) without the
        top-level "title" key, and always with "type": "object" and a "properties" mapping.
    strict: False.

    Stuck? HINTS.md -> mcp_tool_to_llmkit
    """
    raise NotImplementedError("exercise 4a")


def call_result_to_tool_result(call: ToolCall, result: dict) -> ToolResult:
    """One MCP tools/call result (the JSON dict above) -> llmkit ToolResult for `call`.

    The text has one part per block of result["content"] (a list, maybe empty or missing),
    non-empty parts joined with "\n\n":
        {"type": "text", "text": t}                             -> t
        {"type": "resource", "resource": {"uri": u, "text": t}} -> "[resource u]\n" + t, rstripped
        {"type": "resource_link", "uri": u, ...}                -> "[resource link u]"
        any other type (image, audio)                           -> "[<type> omitted: <mimeType>]" ("?" if missing)
    No text but a "structuredContent" -> that object as JSON (ensure_ascii=False, Hebrew stays readable).
    Returns ToolResult(call.id, text, is_error=bool(result.get("isError")), name=call.name).

    Stuck? HINTS.md -> call_result_to_tool_result
    """
    raise NotImplementedError("exercise 4b")


# =====================================================================================================
# Exercise 7: pin tool descriptions, detect a rug pull
# =====================================================================================================
#
# A lockfile body, written after a human reviewed the full descriptions (mcpkit.pinning.pin_tools):
#   {"server": "acme-helpers", "pinned_at": "2026-11-02T08:00:00+00:00",
#    "tools": {"business_days_between": {"sha256": "<64 hex>", "description": "Count business days ...",
#                                        "inputSchema": {...}}}}


def tool_fingerprint(tool: dict) -> str:
    """sha256 hex digest of what reaches the model's prompt: the tool's name, description and
    inputSchema only. It must equal mcpkit.pinning's fingerprint, so the canonical form is fixed:
    json.dumps({"name", "description", "inputSchema"}, sort_keys=True, separators=(",", ":"),
    ensure_ascii=False), encoded as utf-8. A missing description counts as "" and a missing
    inputSchema as {}. title, annotations and _meta are ignored (they do not reach the prompt).

    Stuck? HINTS.md -> tool_fingerprint
    """
    raise NotImplementedError("exercise 7a")


def diff_tool_pins(pinned: dict, current: list[dict]) -> dict:
    """Compare pins with what the server lists now.

    pinned: a lockfile body as above, OR just its "tools" mapping (accept both).
    current: a list of MCP tool dicts (tools/list JSON).
    Returns {"ok": bool, "added": [...], "removed": [...], "changed": [...]}:
        added    sorted names listed now but not pinned
        removed  sorted names pinned but not listed now
        changed  names in both whose tool_fingerprint differs from the pinned sha256, sorted by name,
                 each {"name", "old_sha256", "new_sha256", "description_diff", "schema_changed"}:
                   description_diff: a unified diff of the description lines, labelled "pinned" and
                     "current", lines joined with "\n" and no line terminators (difflib.unified_diff
                     with lineterm=""); "" when the text is equal. It must match mcpkit.pinning exactly.
                   schema_changed: the inputSchemas differ (missing counts as {}).
        ok       True only when added, removed and changed are all empty.

    Stuck? HINTS.md -> diff_tool_pins
    """
    raise NotImplementedError("exercise 7b")
