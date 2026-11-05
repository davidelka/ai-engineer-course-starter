"""Your code for lesson 3. Each part is checked by tests in ./tests.

llmkit/structured.py has reference versions of extract_json and format_errors.
Try not to peek before your tests pass.

    python -m pytest -q labs/03-structured-outputs/tests
"""

from __future__ import annotations

import json  # noqa: F401  (you will likely need it)
import re  # noqa: F401

from pydantic import ValidationError, field_validator, model_validator  # noqa: F401

from acme_schema import AccessRequest


# ------------------------------------------------------------------ exercise 3
def extract_json(text: str) -> str:
    """Return the JSON object inside a model reply, as a string.

    Must handle:
      - a bare object:                    {"a": 1}
      - markdown fences:                  ```json\\n{"a": 1}\\n```  (with or without "json")
      - prose around it:                  Sure! Here it is: {"a": 1} Hope this helps.
      - nested objects:                   {"a": {"b": 1}}
      - braces and escaped quotes inside strings: {"a": "a \\" and a } brace"}
      - two objects in one reply: return the first.
    Raise ValueError when there is no object (a JSON array is not an object), or when
    the object is never closed (a truncated reply).

    Stuck? HINTS.md -> extract_json
    """
    # TODO(ex3)
    raise NotImplementedError("exercise 3: implement extract_json")


# ------------------------------------------------------------------ exercise 4
def format_errors(exc: Exception, max_errors: int = 8) -> str:
    """Turn a failure into short lines the model can act on in a repair turn.

    For a pydantic ValidationError, one line per error, in this format:
        - <field path joined by dots>: <message> (got <the input value as JSON>)
      e.g. - duration_days: Input should be less than or equal to 365 (got 100000)
    The "got" value is at most 60 characters, cut with "...".
    At most max_errors such lines, then a last line "- ... and N more errors".
    For any other exception (bad JSON, no object found): a single line
        - the reply is not valid JSON: <the exception text>

    Stuck? HINTS.md -> format_errors
    """
    # TODO(ex4)
    raise NotImplementedError("exercise 4: implement format_errors")


# ------------------------------------------------------------------ exercise 5
class MyAccessRequest(AccessRequest):
    """Rules that the JSON Schema cannot express, added as pydantic validators.

    1. requester_email is normalized, not rejected: surrounding spaces removed and
       lowercased. None stays None.
    2. If ANY of these hold, route must be "needs_security":
         access_level == "admin", production, customer_data, financial_data, external_sharing
       Otherwise validation fails with a message that names the rule and contains
       "needs_security", e.g. "route must be needs_security because access_level is admin".
    3. route == "auto_approve" is only allowed for access_level "read" or "standard".
    When both 2 and 3 are broken, the rule-2 message is the one reported.

    Stuck? HINTS.md -> MyAccessRequest
    """
    # TODO(ex5)
    pass
