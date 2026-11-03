APPROVED = ["Jira", "Confluence", "Slack", "Google Workspace", "Zoom", "Miro", "Figma", "GitHub"]


def route_request(tool, access, customer_data=False, financial_data=False, production=False,
                  external_sharing=False):
    if access == "admin" or production or customer_data:
        return "needs_security"
    if tool not in APPROVED:
        return "needs_manager"
    if access == "paid_seat":
        return "needs_manager"
    return "auto_approve"
