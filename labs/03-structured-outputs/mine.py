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
      - markdown fences:                  ```json\\n{"a": 1}\\n```
      - prose around it:                  Sure! Here it is: {"a": 1} Hope this helps.
      - nested objects:                   {"a": {"b": 1}}
      - braces inside strings:            {"a": "use {x} here"}
    Raise ValueError when there is no object, or when it is never closed
    (a truncated reply).
    """
    # TODO(ex3)
    raise NotImplementedError("exercise 3: implement extract_json")


# ------------------------------------------------------------------ exercise 4
def format_errors(exc: Exception, max_errors: int = 8) -> str:
    """Turn a failure into short lines the model can act on in a repair turn.

    For a pydantic ValidationError, one line per error:
        - <field path joined by dots>: <message> (got <the input value as JSON>)
      e.g. - duration_days: Input should be less than or equal to 365 (got 100000)
    Use exc.errors(): each error is a dict with "loc" (tuple), "msg" and "input".
    Keep each "got" value short: at most 60 characters, cut with "...".
    Show at most max_errors lines, then "- ... and N more errors".
    For anything else (bad JSON, no object found): a single line starting with
    "- the reply is not valid JSON:" followed by the exception text.
    """
    # TODO(ex4)
    raise NotImplementedError("exercise 4: implement format_errors")


# ------------------------------------------------------------------ exercise 5
class MyAccessRequest(AccessRequest):
    """Rules that the JSON Schema cannot express. Add them as validators.

    1. requester_email: strip spaces and lowercase it (normalize, don't reject).
    2. If ANY of these hold, route must be "needs_security":
         access_level == "admin", production, customer_data, financial_data, external_sharing
       Otherwise raise ValueError with a message that names the rule, e.g.
       "route must be needs_security because access_level is admin".
    3. route == "auto_approve" is only allowed for access_level "read" or "standard".

    Hints: @field_validator("requester_email") with a classmethod for 1;
    @model_validator(mode="after") returning self for 2 and 3.
    """

    # TODO(ex5)
    pass
