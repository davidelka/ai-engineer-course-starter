"""Routing rules from the Acme SaaS Access Policy (docs/policy.md)."""

from __future__ import annotations

from app.catalog import APPROVED_TOOLS, FINANCIAL_SYSTEMS, PRODUCTION_SYSTEMS, normalize_tool
from app.models import AccessRequestIn, Route


def is_sensitive(req: AccessRequestIn) -> bool:
    """True when the request touches something the security team must review."""
    tool = normalize_tool(req.tool)
    return (
        req.access_level == "admin"
        or req.production
        or req.customer_data
        or req.financial_data
        or req.external_sharing
        or tool in PRODUCTION_SYSTEMS
        or tool in FINANCIAL_SYSTEMS
    )


def route(req: AccessRequestIn) -> Route:
    """Pick exactly one track for a request."""
    tool = normalize_tool(req.tool)

    # Fast path: the common case is a read or standard seat on an approved tool.
    if tool in APPROVED_TOOLS and req.access_level in ("read", "standard"):
        return "auto_approve"

    if is_sensitive(req):
        return "needs_security"

    return "needs_manager"
