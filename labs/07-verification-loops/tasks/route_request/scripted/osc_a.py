APPROVED = {"jira", "confluence", "slack", "google workspace", "zoom", "miro", "figma", "github"}


def route_request(tool, access, customer_data=False, financial_data=False, production=False,
                  external_sharing=False):
    if access == "admin" or production or customer_data or financial_data or external_sharing:
        return "needs_security"
    if tool.strip().lower() not in APPROVED or access in ("write", "paid_seat"):
        return "needs_manager"
    return "auto_approve"
