"""Three versions of the same six tools, for exercise 5 (route_eval.py).

good    the descriptions in toolkit/acme.py: what the tool returns, when to use it, when NOT to
        (and which tool to use instead), what the inputs look like
bad     the same names, one vague line each (what many first drafts look like)
opaque  vague names AND vague descriptions: the model has almost nothing to go on
"""

from toolkit.acme import DESCRIPTIONS

GOOD = dict(DESCRIPTIONS)

BAD = {
    "lookup_employee": "Employee tool.",
    "get_system_info": "Gets info.",
    "list_access_grants": "Returns grants.",
    "check_policy": "Policy check.",
    "read_document": "Docs.",
    "create_access_request": "Creates a request.",
}

OPAQUE_NAMES = {
    "lookup_employee": "tool_1", "get_system_info": "tool_2", "list_access_grants": "tool_3",
    "check_policy": "tool_4", "read_document": "tool_5", "create_access_request": "tool_6",
}

VARIANTS = {"good": (GOOD, {}), "bad": (BAD, {}), "opaque": (BAD, OPAQUE_NAMES)}
