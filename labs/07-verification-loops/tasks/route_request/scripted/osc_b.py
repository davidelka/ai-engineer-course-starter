APPROVED = {"jira", "confluence", "slack", "google workspace", "zoom", "miro", "figma", "github"}
ACCESS = {"read", "standard", "write", "paid_seat", "admin"}


def route_request(tool, access, customer_data=False, financial_data=False, production=False,
                  external_sharing=False):
    if access not in ACCESS:
        raise ValueError(access)
    if access == "admin" or production or customer_data or financial_data or external_sharing:
        return "needs_security"
    if tool.strip().lower() not in APPROVED or access == "paid_seat":
        return "needs_manager"
    return "auto_approve"
