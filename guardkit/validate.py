"""Reference output validator (lesson 24, exercise 4). Students write their own in mine.py.

check_output(text) returns a list of Finding. Four kinds:

  markdown_image     an image (Markdown ![..](url) or HTML <img src=..>) whose URL points to a
                     host outside the allowlist. Rendering it makes the browser send a GET
                     request, and anything in the URL (a query string with stolen data) leaves.
  unknown_domain     any http(s):// or www. URL whose host is not an allowed domain or one of
                     its subdomains. The host is parsed with urllib (userinfo tricks such as
                     https://acme.example@evil.test/ are caught).
  credential_request a sentence that asks the reader for a password, MFA code or other
                     credential, and is not negated ("never share your password" is fine).
  refund_promise     a sentence that promises refunds without a time limit ("at any time",
                     "always"), outside the refund policy. Billing errors ARE always refunded,
                     so a sentence about billing errors is allowed.

All rules are deliberately sentence-level regexes: cheap, deterministic, explainable, and
easy to test. They are a last line of defense, not the only one.
"""

from __future__ import annotations

import re
from typing import Iterable
from urllib.parse import urlsplit

from .types import Finding

ALLOWED_DOMAINS = ("acme.example",)

URL_RE = re.compile(r"(?i)(?:\bhttps?://|(?<![\w/])//(?=[\w.-]+\.[a-z])|\bwww\.)[^\s<>\"'\]\[)(]+")
MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(\s*<?([^)\s>]+)")
MD_REF_IMAGE_RE = re.compile(r"!\[[^\]]*\]\[([^\]]+)\]")
MD_REF_DEF_RE = re.compile(r"(?m)^\s*\[([^\]]+)\]:\s*<?(\S+?)>?(?:\s|$)")
HTML_IMG_RE = re.compile(r"(?is)<img\b[^>]*?\bsrc\s*=\s*[\"']?([^\"'\s>]+)")
TRAILING = ".,;:!?)]}'\""

CRED_RE = re.compile(
    r"(?i)\b(?:password|passwords|passcode|passphrase|mfa code|2fa code|otp|one[- ]time (?:code|password)"
    r"|verification code|security code|credentials?|login details|api key|secret key)\b"
    r"|סיסמ|קוד (?:ה)?אימות|קוד חד[- ]פעמי|פרטי (?:ה)?התחברות"
    r"|كلمة (?:المرور|السر)|رمز التحقق")
ASK_RE = re.compile(
    r"(?i)\b(?:confirm|provide|send|share|tell|give|reply|paste|submit)\b"
    r"|אשר את|אשרו|תאשר|שלח|תשלח|ספק|מסור|תן לי|כתוב|כתבו|הקלד"
    r"|أكد|أرسل|شارك|اكتب|أدخل")
NEG_RE = re.compile(
    r"(?i)\b(?:never|don't|do not|must not|should not|no one|nobody|not)\b"
    r"|לעולם|אף פעם|אסור|אל ת|אין ל"
    r"|(?:^|\s)لا\s|أبدا|أبدًا|لن\s")

REFUND_RE = re.compile(r"(?i)\brefund\w*|\bmoney back\b|החזר|استرداد|استرجاع")
UNLIMITED_RE = re.compile(
    r"(?i)\b(?:any ?time|at any point|whenever|no matter when|always|guaranteed|forever|no questions asked)\b"
    r"|בכל עת|בכל זמן|בכל שלב|תמיד|מובטח"
    r"|في أي وقت|دائما|دائمًا|مضمون")
BILLING_ERR_RE = re.compile(r"(?i)\bbilling (?:error|mistake)s?\b|טעו(?:ת|יות) (?:ב)?חיוב|خطأ في الفوترة")
REFUND_NEG_RE = re.compile(
    r"(?i)\bnot refundable\b|\bnon-refundable\b|\bno refunds?\b|\bnever\b|\bcannot\b|\bcan't\b"
    r"|אין החזר|לא ניתן|לא זכאי|لا يمكن|غير قابل")

_SENT_SPLIT = re.compile(r"(?<=[.!?。])\s+|\n+")


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT_SPLIT.split(text or "") if s.strip()]


def host_of(url: str) -> str:
    """Lower-case host of a URL; '' when there is none (relative URL, mailto:, data:)."""
    u = url.strip().strip(TRAILING)
    if u.lower().startswith("www."):
        u = "http://" + u
    elif u.startswith("//"):
        u = "http:" + u
    try:
        host = urlsplit(u).hostname or ""
    except ValueError:
        return "invalid"
    return host.rstrip(".").lower()


def host_allowed(host: str, allowed: Iterable[str] = ALLOWED_DOMAINS) -> bool:
    host = host.rstrip(".").lower()
    return any(host == d or host.endswith("." + d) for d in allowed)


def image_urls(text: str) -> list[str]:
    urls = MD_IMAGE_RE.findall(text) + HTML_IMG_RE.findall(text)
    refs = {k.lower(): v for k, v in MD_REF_DEF_RE.findall(text)}
    urls += [refs[r.lower()] for r in MD_REF_IMAGE_RE.findall(text) if r.lower() in refs]
    return urls


def check_output(text: str, allowed_domains: Iterable[str] = ALLOWED_DOMAINS) -> list[Finding]:
    allowed = tuple(allowed_domains)
    out: list[Finding] = []
    seen: set[tuple[str, str]] = set()

    def add(kind: str, detail: str) -> None:
        if (kind, detail) not in seen:
            seen.add((kind, detail))
            out.append(Finding(kind, detail))

    for url in image_urls(text):
        host = host_of(url)
        if host and not host_allowed(host, allowed):
            add("markdown_image", host)
    for m in URL_RE.finditer(text):
        host = host_of(m.group(0))
        if host and not host_allowed(host, allowed):
            add("unknown_domain", host)
    for s in split_sentences(text):
        if CRED_RE.search(s) and ASK_RE.search(s) and not NEG_RE.search(s):
            add("credential_request", s[:120])
        if (REFUND_RE.search(s) and UNLIMITED_RE.search(s) and not BILLING_ERR_RE.search(s)
                and not REFUND_NEG_RE.search(s)):
            add("refund_promise", s[:120])
    return out
