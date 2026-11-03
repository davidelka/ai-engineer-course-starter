APPROVED = {"jira", "confluence", "slack", "google workspace", "zoom", "miro", "figma", "github"}
ACCESS = {"read", "standard", "write", "paid_seat", "admin"}


def route_request(tool: str, access: str, *, customer_data: bool = False, financial_data: bool = False,
                  production: bool = False, external_sharing: bool = False) -> str:
    level = access.strip().lower()
    if level not in ACCESS:
        raise ValueError(f"unknown access level: {access!r}")
    if level == "admin" or production or customer_data or financial_data or external_sharing:
        return "needs_security"
    if tool.strip().lower() not in APPROVED or level in {"write", "paid_seat"}:
        return "needs_manager"
    return "auto_approve"
