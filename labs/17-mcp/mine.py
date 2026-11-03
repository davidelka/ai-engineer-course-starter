"""Lesson 17: your code. Three coding exercises (3, 4 and 7). Each function raises
NotImplementedError until you write it. The tests are in tests/; run them with
    python -m pytest -q labs/17-mcp/tests

Reference implementations exist in mcpkit/ (oncall.py, bridge.py, pinning.py). Don't read them
before your tests pass.
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

    Returns a dict with EXACTLY these keys:
        service            the name as written in the table ("flow-api")
        owner_team         "Core API"
        team_lead          "Itai Barak"
        tier               int, 1..3
        rotation           "core-api-oncall"; None for business-hours services (lighthouse)
        schedule           "weekly, handover Sunday 10:00": the text after "<rotation>:" up to ";" if any.
                           For a shared rotation ("engine-oncall (shared with flow-engine)") copy the
                           schedule from the row that defines that rotation. None when there is none.
        secondary          "platform-oncall" from "...; secondary is platform-oncall", else None
        shared_with        "flow-engine" from "(shared with flow-engine)", else None
        channel            "#data-help" for "business hours, #data-help", else None
        pagerduty_service  "flow-api-prod"; None when the cell is "none"
        coverage           "24/7" for tiers 1-2, "business hours" for tier 3
        ack_minutes        5 for tier 1, 15 for tier 2, None for tier 3
        runbook            the runbook doc id (see above) or None
        source             always "eng-service-catalog"

    Errors: empty service -> raise ToolError("service is empty. ..."). Unknown service -> raise ToolError
    whose message contains the requested name and either close matches (difflib.get_close_matches,
    cutoff 0.5: "flow-ap" -> "flow-api") or, when nothing is close, the list of known service names.
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
    """One MCP tool (the JSON dict above) -> llmkit Tool.

    name:  f"{server}__{tool['name']}" when server is given, else tool["name"]. Then replace every
           character outside [a-zA-Z0-9_-] with "_". If the result is longer than 64 characters, keep the
           first 55, then "_", then the first 8 hex chars of sha256(<the name BEFORE replacing>, utf-8).
    description: tool["description"], or tool["title"] if there is no description, or the name;
           stripped of surrounding whitespace.
    input_schema: a DEEP copy of tool["inputSchema"] (or {} if missing) without the top-level "title"
           key, with "type": "object" and "properties": {} added when missing. Never mutate the input dict.
    strict: False.
    """
    raise NotImplementedError("exercise 4a")


def call_result_to_tool_result(call: ToolCall, result: dict) -> ToolResult:
    """One MCP tools/call result (the JSON dict above) -> llmkit ToolResult for `call`.

    Build the text from result["content"] (a list, maybe empty or missing), one part per block:
        {"type": "text", "text": t}                          -> t
        {"type": "resource", "resource": {"uri": u, "text": t}} -> "[resource u]\\n" + t   (rstrip the part)
        {"type": "resource_link", "uri": u, ...}              -> "[resource link u]"
        any other type (image, audio)                       -> "[<type> omitted: <mimeType>]"  ("?" if missing)
    Join the non-empty parts with "\\n\\n". If that text is empty and "structuredContent" is present, use
    json.dumps(structuredContent, ensure_ascii=False) instead.
    Return ToolResult(call.id, text, is_error=bool(result.get("isError")), name=call.name).
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
    """sha256 hex digest of the canonical JSON of {"name", "description", "inputSchema"} only:
    json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8").
    A missing description counts as "" and a missing inputSchema as {}. title, annotations and _meta
    are ignored (they do not reach the model's prompt)."""
    raise NotImplementedError("exercise 7a")


def diff_tool_pins(pinned: dict, current: list[dict]) -> dict:
    """Compare pins with what the server lists now.

    pinned: a lockfile body as above, OR just its "tools" mapping (accept both: use pinned["tools"] when
            the key exists). current: a list of MCP tool dicts (tools/list JSON).
    Returns {"ok": bool, "added": [...], "removed": [...], "changed": [...]}:
        added    sorted names listed now but not pinned
        removed  sorted names pinned but not listed now
        changed  for names in both whose tool_fingerprint differs from the pinned sha256, sorted by name:
                 {"name", "old_sha256", "new_sha256",
                  "description_diff": "\\n".join(difflib.unified_diff(old.splitlines(), new.splitlines(),
                                                 "pinned", "current", lineterm=""))  or "" if the text is equal,
                  "schema_changed": pinned inputSchema != current inputSchema (missing counts as {})}
        ok       True only when added, removed and changed are all empty.
    """
    raise NotImplementedError("exercise 7b")
