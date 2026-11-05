"""Your code for lesson 24. Each part is checked by tests in ./tests.

Reference versions live in guardkit/validate.py, guardkit/acl.py, guardkit/render.py and
guardkit/redact.py. Try not to peek before your tests pass.

    python -m pytest -q labs/24-ai-security/tests

Plug your validator and ACL into the real attack suite with:  run_attacks.py --mine
Stuck? HINTS.md in this folder has graded hints.
"""

from __future__ import annotations

import html  # noqa: F401  (exercise 7)
import re  # noqa: F401
import sqlite3  # noqa: F401  (exercise 7)
from urllib.parse import urlsplit  # noqa: F401  (exercise 4)

from guardkit.types import ROLE_DEPARTMENT, ROLES, Finding  # noqa: F401

ALLOWED_DOMAINS = ("acme.example",)


# ------------------------------------------------------------------ exercise 4
def validate_output(text: str) -> list[Finding]:
    """Check a model answer BEFORE it is shown to the employee. Return a list of
    Finding(kind, detail), one per problem; [] means the answer may be shown.
    No (kind, detail) pair twice; order does not matter; matching is case-insensitive.

    Allowed host: equal to an ALLOWED_DOMAINS entry or a subdomain of it.
      acme.example, docs.acme.example -> allowed;  acme.example.evil.test, evilacme.example,
      https://acme.example@collect.evil.test/x (host collect.evil.test) -> NOT allowed.

    Kinds (detail = the lower-case host for URL kinds, any non-empty string for the others):
    - "markdown_image": an image whose host is not allowed, Markdown ![alt](URL) or HTML
      <img src="URL">. Protocol-relative //evil.test/x.png counts; relative and data: URLs
      have no host and are fine. Such an image ALSO yields "unknown_domain".
    - "unknown_domain": a URL (http://, https://, www.) with a host that is not allowed.
      Trailing punctuation in prose (.,;:!?)]'" ) is not part of the URL.
    - "credential_request": a sentence that asks for a credential and is not negated.
        credentials: password(s), passcode, passphrase, MFA/2FA code, OTP, one-time code,
          verification code, credentials, API key; סיסמה, סיסמת, קוד אימות, קוד האימות;
          كلمة المرور, كلمة السر
        request verbs: confirm, provide, send, share, tell, give, reply, paste, submit;
          אשר את, שלח, ספק, מסור, כתוב, הקלד; أكد, أرسل, شارك, اكتب  ("enter" is NOT one)
        negations: never, do not, don't, must not, should not, no one, nobody, not;
          לעולם, אף פעם, אסור; لا, أبدا
    - "refund_promise": a sentence promising refunds without a time limit.
        refund words: refund, refundable, refunded, money back; החזר; استرداد
        unlimited time: any time, anytime, at any point, whenever, no matter when, always,
          guaranteed; בכל עת, בכל זמן, תמיד; في أي وقت, دائما
        not when about billing errors (billing error(s); טעות חיוב, טעויות חיוב) or negated
          (not refundable, non-refundable, no refund(s), never, cannot, can't; אין החזר, לא ניתן)

    Examples: "Please confirm your Okta password in the chat." -> credential_request;
              "Never share your password with anyone." -> nothing;
              "Annual plans can always be refunded in full at any time." -> refund_promise;
              "Billing errors caused by Acme are always refunded in full." -> nothing.

    Stuck? HINTS.md -> validate_output
    """
    # TODO(ex4)
    raise NotImplementedError("exercise 4: implement validate_output")


# ------------------------------------------------------------------ exercise 5
def acl_allows(role: str, meta: dict) -> bool:
    """May a user with this role see a chunk with this metadata? Runs BEFORE ranking.

    role: one of ROLES = ("contractor", "employee", "support", "engineering", "security", "hr").
    meta: the chunk's metadata, e.g. {"classification": "confidential", "department": "engineering"}.
          ROLE_DEPARTMENT maps roles to departments: support -> sales_support,
          engineering -> engineering, hr -> hr, security -> it_security.

    Rules:
      public        -> every role, including contractor
      internal      -> every role except contractor
      confidential  -> role "security", or a role whose department equals meta["department"]
                       (contractor and employee have no department: never)
      classification is compared case-insensitively and with surrounding spaces ignored.
      Anything else -> False: "restricted", a missing or empty classification, a misspelled
      one ("confidental"), an unknown role. Fail closed.

    Stuck? HINTS.md -> acl_allows
    """
    # TODO(ex5)
    raise NotImplementedError("exercise 5: implement acl_allows")


# ------------------------------------------------------------------ exercise 7
def render_answer_html(text: str) -> str:
    """Turn a model answer into an HTML fragment that is safe to insert into the chat page.

    - No tag or attribute from the model may survive (<script>, <img onerror=...>,
      <a href="javascript:...">, <iframe>...): all of the model's text ends up escaped.
    - Markdown images ![alt](url) are never rendered: each becomes the text
      "[image removed: HOST]" ("relative" when the URL has no host).
    - Markdown links [label](url) and bare https:// URLs become
          <a href="URL" rel="noopener noreferrer nofollow">LABEL</a>
      ONLY for an https:// URL on an allowed host (the rule of exercise 4). Otherwise only the
      label (Markdown link) or the URL (bare URL) remains, as plain, non-clickable text.
      Trailing punctuation after a bare URL in prose stays as text after it.
    - Newlines become "<br>\\n".
    The tests check properties (no live tags, allowed links present, text preserved), not an
    exact string.

    Stuck? HINTS.md -> render_answer_html
    """
    # TODO(ex7)
    raise NotImplementedError("exercise 7: implement render_answer_html")


def find_customer_tickets(con: sqlite3.Connection, customer_name: str, limit: int = 20) -> list[dict]:
    """The SQL tool the agent calls: tickets of one customer, by exact customer name.

    Tables (data/acme/corpus/structured/acme.db):
      customers(id TEXT, name TEXT, plan TEXT, ...)
      tickets(id TEXT, customer_id TEXT -> customers.id, subject TEXT, priority TEXT, status TEXT, ...)

    Return a list of dicts with keys: id, customer (the customer's name), subject, priority,
    status; ordered by ticket id; at most `limit` rows, with limit clamped to 1..50.
    - Injection-proof: a name like  x' OR '1'='1  must simply match nothing.
    - Surrounding whitespace of the name is ignored. ValueError if it is not a str, is
      empty after stripping, or is longer than 100 characters.
    The test opens the database read-only (mode=ro): least privilege at the database layer.

    Stuck? HINTS.md -> find_customer_tickets
    """
    # TODO(ex7)
    raise NotImplementedError("exercise 7: implement find_customer_tickets")


# ------------------------------------------------------------------ exercise 8
def is_valid_israeli_id(value: str) -> bool:
    """Israeli ID number (teudat zehut) check digit.

    - Input: 1 to 9 digits, optionally with one '-' before the last digit ("12345678-2").
      Shorter numbers count as left-padded with zeros to 9 digits.
    - Valid when the last digit is the correct check digit of the official algorithm (a
      Luhn-like weighted sum; look it up or see the hints).
    - False for all zeros, an empty string, or any other character.
    Examples: "123456782" valid, "123456789" invalid, "000000018" valid, "18" valid (padded).

    Stuck? HINTS.md -> is_valid_israeli_id
    """
    # TODO(ex8)
    raise NotImplementedError("exercise 8: implement is_valid_israeli_id")


def redact_pii(text: str) -> str:
    """Redact personal data from a log line, in THIS order:

    1. Israeli ID numbers -> "[IL_ID]": a standalone 9-digit number (optionally "-" before
       the last digit) that passes is_valid_israeli_id. A 9-digit number that fails the
       checksum (an order number, say) stays as it is.
    2. Emails -> "[EMAIL]": local part of letters, digits, . _ + -, then @, then a domain with
       at least one dot.
    3. Israeli phone numbers -> "[PHONE]": mobile (05x), VoIP (07x) and landline (02, 03,
       04, 08, 09) numbers, with 0 or +972, with or without one "-" or space between groups:
       050-1234567, 03-5550199, +972-3-555-0199, +972 54 123 4567, 0541234567.
    Everything else is unchanged.

    Stuck? HINTS.md -> redact_pii
    """
    # TODO(ex8)
    raise NotImplementedError("exercise 8: implement redact_pii")
