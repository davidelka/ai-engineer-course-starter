"""Delivery ports: where a digest and the application drafts go.

    DeliveryPort.send(digest)          ConsoleDelivery, FileDelivery, WhatsAppGroupDelivery
    DraftPort.create_draft(draft)      FileDraftAdapter (.eml files), GmailDraftAdapter

Two hard limits, enforced in code and not only in prompts:
  1. The digest goes to ONE configured destination. WhatsAppGroupDelivery refuses any chat
     other than the one it was built with ("משרות"), whatever a post says.
  2. Applications are DRAFTS. There is no send method anywhere in this module, and the Gmail
     adapter calls only users.drafts.create (scope gmail.compose). The owner reviews, attaches
     the CV file himself, and presses send. tests/test_f3_job_agent.py checks that the
     module never references a send endpoint.
"""

from __future__ import annotations

import base64
import os
import sys
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path
from typing import Callable, Optional, Protocol, TextIO, Union

import httpx

from .digest import Digest
from .models import Job


@dataclass
class Receipt:
    ok: bool
    destination: str
    detail: str = ""


class DeliveryPort(Protocol):
    name: str

    def send(self, digest: Digest) -> Receipt: ...


class ConsoleDelivery:
    name = "console"

    def __init__(self, stream: Optional[TextIO] = None):
        self.stream = stream

    def send(self, digest: Digest) -> Receipt:
        out = self.stream or sys.stdout
        out.write(digest.text + "\n")
        return Receipt(True, "console")


class FileDelivery:
    """results/digests/<slot>.txt: what WOULD have been sent. The demo and the eval use it."""

    name = "file"

    def __init__(self, folder: Union[str, Path]):
        self.folder = Path(folder)

    def send(self, digest: Digest) -> Receipt:
        self.folder.mkdir(parents=True, exist_ok=True)
        path = self.folder / (digest.slot_key.replace(":", "") + ".txt")
        path.write_text(digest.text + "\n", encoding="utf-8")
        return Receipt(True, str(path))


class WhatsAppGroupDelivery:
    """Sends through the WhatsApp bridge the owner already runs. The bridge's MCP server has a
    send_message tool (recipient = a phone number or a group JID). This adapter does not talk
    to WhatsApp itself: pass `send_fn(recipient, text)` that calls your bridge, e.g. a thin
    MCP client. Without send_fn it raises, so nothing is sent by accident.

    allowed_chat is fixed at construction. Messages to any other recipient are refused."""

    name = "whatsapp"

    def __init__(self, allowed_chat: str, send_fn: Optional[Callable[[str, str], None]] = None):
        self.allowed_chat = allowed_chat
        self.send_fn = send_fn

    def send(self, digest: Digest, recipient: Optional[str] = None) -> Receipt:
        recipient = recipient or self.allowed_chat
        if recipient != self.allowed_chat:
            return Receipt(False, recipient, "refused: not the configured digest group")
        if self.send_fn is None:
            raise NotImplementedError("connect send_fn to your WhatsApp bridge (see README, milestone 7)")
        self.send_fn(recipient, digest.text)
        return Receipt(True, recipient)


# ---------------------------------------------------------------- drafts
@dataclass
class Draft:
    to: str
    subject: str
    body: str
    cv_file: Optional[str]
    job_fingerprint: str


def draft_for(job: Job, owner: str = "Me") -> Optional[Draft]:
    """An application draft for a match whose apply contact is an email. None otherwise
    (a link means applying on a website: the digest shows the link instead)."""
    p = job.posting
    if not p.apply or "@" not in p.apply or p.apply.startswith("http") or job.suspicious:
        return None
    if p.language == "he":
        subject = f"מועמדות למשרת {p.title}" + (f" ב-{p.company}" if p.company else "")
        body = (f"שלום,\n\nראיתי את הפרסום למשרת {p.title}" + (f" ב-{p.company}" if p.company else "")
                + " ואשמח להגיש מועמדות.\nיש לי 5 שנות ניסיון, רובן באוטומציה, וגם בפיתוח Backend ומערכות.\n"
                f"מצורפים קורות החיים שלי.\n\nבתודה,\n{owner}")
    else:
        subject = f"Application: {p.title}" + (f" at {p.company}" if p.company else "")
        body = (f"Hello,\n\nI saw the {p.title} opening" + (f" at {p.company}" if p.company else "")
                + " and would like to apply.\nI have 5 years of experience, mostly in automation, with backend "
                f"and systems work as well.\nMy CV is attached.\n\nBest regards,\n{owner}")
    if job.cv:
        body += f"\n\n[לצרף ידנית: {job.cv}]"
    return Draft(to=p.apply, subject=subject, body=body, cv_file=job.cv, job_fingerprint=job.fingerprint)


def to_mime(d: Draft, sender: str = "me") -> EmailMessage:
    m = EmailMessage()
    m["To"] = d.to
    m["From"] = sender
    m["Subject"] = d.subject
    m.set_content(d.body)
    return m


class DraftPort(Protocol):
    name: str

    def create_draft(self, draft: Draft) -> Receipt: ...


class FileDraftAdapter:
    name = "file-drafts"

    def __init__(self, folder: Union[str, Path]):
        self.folder = Path(folder)

    def create_draft(self, draft: Draft) -> Receipt:
        self.folder.mkdir(parents=True, exist_ok=True)
        path = self.folder / f"{draft.job_fingerprint}.eml"
        path.write_bytes(bytes(to_mime(draft)))
        return Receipt(True, str(path))


class GmailDraftAdapter:
    """POST https://gmail.googleapis.com/gmail/v1/users/me/drafts  {"message": {"raw": base64url(RFC 822)}}

    Needs an OAuth access token with the scope https://www.googleapis.com/auth/gmail.compose
    (GMAIL_ACCESS_TOKEN). Getting and refreshing it is outside this module (google-auth's
    InstalledAppFlow once, then a refresh token). This adapter only CREATES drafts."""

    name = "gmail-drafts"
    URL = "https://gmail.googleapis.com/gmail/v1/users/me/drafts"

    def __init__(self, token: Optional[str] = None, http: Optional[httpx.Client] = None):
        self.token = token or os.environ.get("GMAIL_ACCESS_TOKEN", "")
        self.http = http or httpx.Client(timeout=15.0)

    def create_draft(self, draft: Draft) -> Receipt:
        if not self.token:
            return Receipt(False, "gmail", "no GMAIL_ACCESS_TOKEN")
        raw = base64.urlsafe_b64encode(bytes(to_mime(draft))).decode("ascii")
        r = self.http.post(self.URL, json={"message": {"raw": raw}}, headers={"Authorization": f"Bearer {self.token}"})
        if r.status_code >= 300:
            return Receipt(False, "gmail", f"HTTP {r.status_code}")
        return Receipt(True, "gmail", r.json().get("id", ""))
