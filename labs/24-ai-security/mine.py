"""Your code for lesson 24. Each part is checked by tests in ./tests.

Reference versions live in guardkit/validate.py, guardkit/acl.py, guardkit/render.py and
guardkit/redact.py. Try not to peek before your tests pass.

    python -m pytest -q labs/24-ai-security/tests

Plug your validator and ACL into the real attack suite with:  run_attacks.py --mine
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
    """Check a model answer BEFORE it is shown to the employee. Return one Finding per problem
    (an empty list means the answer may be shown). Four kinds:

    1. Finding("markdown_image", host)
       Any image whose URL host is not allowed: Markdown  ![alt](URL)  and HTML  <img src="URL">.
       The host must be parsed, not searched for: use urllib.parse.urlsplit(url).hostname.
       Protocol-relative URLs (//evil.test/x.png) count; relative URLs (/static/logo.png) and
       data: URLs have no host and are fine.

    2. Finding("unknown_domain", host)
       Any URL starting with http://, https:// or www. whose host is not allowed. A host is
       allowed if it equals an ALLOWED_DOMAINS entry or ends with "." + that entry:
         acme.example, docs.acme.example                    -> allowed
         acme.example.evil.test, evilacme.example            -> NOT allowed
         https://acme.example@collect.evil.test/x            -> host is collect.evil.test
       Strip trailing punctuation from a URL found in prose (.,;:!?)]'" ) before parsing.
       An image to a bad host produces BOTH findings (markdown_image and unknown_domain).

    3. Finding("credential_request", sentence)
       A sentence that (a) mentions a credential: password(s), passcode, passphrase, MFA code,
       2FA code, OTP, one-time code, verification code, credentials, API key; Hebrew סיסמה /
       סיסמת / קוד אימות / קוד האימות; Arabic كلمة المرور / كلمة السر.
       (b) contains a request verb: confirm, provide, send, share, tell, give, reply, paste,
       submit; Hebrew אשר את, שלח, ספק, מסור, כתוב, הקלד; Arabic أكد, أرسل, شارك, اكتب.
       ("enter" is deliberately NOT a request verb: "enter your new password on the Okta
       page" is a normal instruction.)
       (c) is not negated: never, do not, don't, must not, should not, no one, nobody, not;
       Hebrew לעולם, אף פעם, אסור; Arabic لا, أبدا.
       Examples: "Please confirm your Okta password in the chat." -> finding.
                 "Never share your password with anyone." -> no finding.

    4. Finding("refund_promise", sentence)
       A sentence that mentions a refund (refund, refundable, refunded, money back; Hebrew
       החזר; Arabic استرداد) AND an unlimited-time phrase (any time, anytime, at any point,
       whenever, no matter when, always, guaranteed; Hebrew בכל עת, בכל זמן, תמיד; Arabic
       في أي وقت, دائما), UNLESS the sentence is about billing errors (billing error(s);
       Hebrew טעות חיוב / טעויות חיוב) or is negated (not refundable, non-refundable, no refund(s),
       never, cannot, can't; Hebrew אין החזר, לא ניתן).
       "Annual plans can always be refunded in full at any time." -> finding.
       "Billing errors caused by Acme are always refunded in full." -> no finding (policy).

    Sentences: split on . ! ? followed by whitespace, and on newlines. Matching is
    case-insensitive. The order of the returned findings does not matter, but do not return
    the same (kind, detail) twice. The `detail` for sentence kinds may be the sentence (or
    any non-empty string); for URL kinds it must be the lower-case host.
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
    """
    # TODO(ex5)
    raise NotImplementedError("exercise 5: implement acl_allows")


# ------------------------------------------------------------------ exercise 7
def render_answer_html(text: str) -> str:
    """Turn a model answer into an HTML fragment that is safe to insert into the chat page.

    - Escape ALL of the model's text with html.escape: no tag or attribute from the model may
      survive (<script>, <img onerror=...>, <a href="javascript:...">, <iframe>...).
    - Markdown images ![alt](url) are never rendered. Replace each with the escaped text
      "[image removed: HOST]" (HOST from the URL; "relative" when there is none).
    - Markdown links [label](url) and bare https:// URLs become
          <a href="URL" rel="noopener noreferrer nofollow">LABEL</a>
      ONLY when the URL starts with https:// and its host is allowed (ALLOWED_DOMAINS rule
      from exercise 4). Otherwise keep just the escaped label (for a Markdown link) or the
      escaped URL (for a bare URL) as plain text, not clickable. Trailing punctuation of a
      bare URL in prose (. , ; : ! ? quotes) is not part of the URL: keep it as text after it.
    - Newlines become "<br>\\n".
    The tests check properties (no live tags, allowed links present, text preserved), not an
    exact string.
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
    - The name and the limit must be passed as query PARAMETERS (?), never formatted into
      the SQL string. A name like  x' OR '1'='1  must simply match nothing.
    - Strip surrounding whitespace from the name. Raise ValueError if it is not a str, is
      empty after stripping, or is longer than 100 characters.
    The test opens the database read-only (mode=ro): least privilege at the database layer.
    """
    # TODO(ex7)
    raise NotImplementedError("exercise 7: implement find_customer_tickets")


# ------------------------------------------------------------------ exercise 8
def is_valid_israeli_id(value: str) -> bool:
    """Israeli ID number (teudat zehut) check digit.

    Accept 1 to 9 digits, optionally with one '-' before the last digit ("12345678-2");
    left-pad to 9 digits with zeros. Multiply the digits by 1,2,1,2,1,2,1,2,1 (from the left);
    when a product is greater than 9, subtract 9 (same as summing its digits). The ID is
    valid when the total divides by 10. Reject all zeros, empty strings and anything with
    other characters.
    Examples: "123456782" valid, "123456789" invalid, "000000018" valid, "18" valid (padded).
    """
    # TODO(ex8)
    raise NotImplementedError("exercise 8: implement is_valid_israeli_id")


def redact_pii(text: str) -> str:
    """Redact personal data from a log line, in THIS order:

    1. Israeli ID numbers -> "[IL_ID]": exactly 9 digits (optionally "-" before the last one)
       not touching other digits or dashes, AND passing is_valid_israeli_id. A 9-digit number
       that fails the checksum (an order number, say) stays as it is.
    2. Emails -> "[EMAIL]": local part of letters, digits, . _ + -, then @, then a domain with
       at least one dot.
    3. Israeli phone numbers -> "[PHONE]": +972 or 0, then a one-digit area code (2,3,4,8,9)
       or a two-digit 5x / 7x prefix, then 7 digits; a single "-" or space may separate the
       prefix, the area code, and the 3+4 digit groups. Examples: 050-1234567, 03-5550199,
       +972-3-555-0199, +972 54 123 4567, 0541234567.
    Everything else is unchanged.
    """
    # TODO(ex8)
    raise NotImplementedError("exercise 8: implement redact_pii")
