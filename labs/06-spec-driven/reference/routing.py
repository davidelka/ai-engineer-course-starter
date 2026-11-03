"""REQ-4: the routing decision. Pure: no I/O, no LLM, same input -> same route."""

from __future__ import annotations

APPROVED_TOOLS = {"jira", "confluence", "slack", "google workspace", "zoom", "miro", "figma", "github"}
SENSITIVE_TOOLS = {"aws", "gcp", "kubernetes", "netsuite", "payroll"}
READ_ONLY_AUTO = {"figma", "github"}  # standard on these is a paid or write-capable seat
FLAGS = ("production", "customer_data", "financial_data", "external_sharing")


def normalize_tool(tool: str) -> str:
    return " ".join(tool.split()).lower()


def route_for(tool: str, access_level: str, flags: dict[str, bool]) -> str:
    t = normalize_tool(tool)
    # Rule 1: the strictest track is checked first, so "strictest wins" falls out of the order.
    if access_level == "admin" or any(flags.get(f, False) for f in FLAGS) or t in SENSITIVE_TOOLS:
        return "needs_security"
    # Rule 2
    if t not in APPROVED_TOOLS or access_level == "write" or (t in READ_ONLY_AUTO and access_level == "standard"):
        return "needs_manager"
    # Rule 3
    return "auto_approve"
