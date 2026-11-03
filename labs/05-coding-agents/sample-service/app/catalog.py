"""Which tools and systems Acme knows about. Source: docs/policy.md (SaaS Access Policy v2.1)."""

APPROVED_TOOLS = {
    "jira",
    "confluence",
    "slack",
    "google workspace",
    "zoom",
    "miro",
    "figma",
    "github",
}

PRODUCTION_SYSTEMS = {
    "aws",
    "gcp",
    "kubernetes",
    "production database",
}

FINANCIAL_SYSTEMS = {
    "netsuite",
    "payroll",
}


def normalize_tool(name: str) -> str:
    """Lowercase and collapse spaces, so "Google  Workspace" matches "google workspace"."""
    return " ".join(name.lower().split())
