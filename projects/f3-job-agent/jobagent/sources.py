"""Sources as ports: everything that brings posts in implements `Source.fetch(since)`.

    WhatsAppExportSource   reads files: a WhatsApp chat export (.txt, Android or iOS format)
                           or a JSON list of messages produced by the bridge you already run.
    AirtableAPISource      the Airtable REST API (list records, paginated, 5 req/s per base).
    AirtableCSVSource      a CSV downloaded from a SHARED view (when you are not a member of
                           the base, the REST API cannot see it, but a shared view can allow
                           "Download CSV").
    FixtureSource          a JSON list of RawPost dicts (tests, the eval set, demos).

What is deliberately NOT here: code that logs into WhatsApp or scrapes WhatsApp Web.
The owner's agent reads the groups through a local bridge (an MCP server over the whatsmeow
library, e.g. github.com/lharries/whatsapp-mcp, which keeps messages in a local SQLite
store). The production adapter is therefore "whatever the bridge exports": a small job
that dumps new messages of the three groups to JSON in the format below, and this module
reads that file. The pipeline never talks to WhatsApp itself, which keeps the account
safe and the pipeline testable.

JSON message format (one list per file):
    [{"id": "3EB0C1...", "chat": "Tech Referrals Senior 5+", "sender": "+972...",
      "timestamp": "2026-11-02T07:58:00+02:00", "text": "..."}]
"""

from __future__ import annotations

import csv
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Optional, Protocol, Union
from zoneinfo import ZoneInfo

import httpx

from .models import RawPost

TZ = ZoneInfo("Asia/Jerusalem")


class Source(Protocol):
    name: str

    def fetch(self, since: Optional[datetime] = None) -> list[RawPost]:
        """Posts newer than `since` (all of them when None). Must not raise for an empty source."""
        ...


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=TZ)


def _newer(ts: Optional[datetime], since: Optional[datetime]) -> bool:
    return since is None or ts is None or _aware(ts) > _aware(since)


# ---------------------------------------------------------------- WhatsApp
# Android: "02/11/2026, 08:15 - Dana: text"     iOS: "[02/11/2026, 08:15:32] Dana: text"
# Exports may carry invisible direction marks (U+200E/U+200F) at line starts.
_ANDROID = re.compile(r"^(\d{1,2})[./](\d{1,2})[./](\d{2,4}),? (\d{1,2}):(\d{2})(?::(\d{2}))? - ([^:]+?): (.*)$")
_IOS = re.compile(r"^\[(\d{1,2})[./](\d{1,2})[./](\d{2,4}),? (\d{1,2}):(\d{2})(?::(\d{2}))?\] ([^:]+?): (.*)$")
_MARKS = dict.fromkeys(map(ord, "‎‏‪‫‬﻿"), None)
SYSTEM_LINES = ("<Media omitted>", "<המדיה הושמטה>", "This message was deleted", "הודעה זו נמחקה")


def parse_whatsapp_txt(text: str, chat: str) -> list[RawPost]:
    """Parse a chat export. Continuation lines belong to the previous message.
    Dates are day/month/year (the Israeli locale). Ids are stable: chat + timestamp + n."""
    posts: list[dict] = []
    for raw_line in text.splitlines():
        line = raw_line.translate(_MARKS)
        m = _ANDROID.match(line) or _IOS.match(line)
        if m:
            d, mo, y, hh, mm, ss, sender, body = m.groups()
            year = int(y) + (2000 if len(y) == 2 else 0)
            ts = datetime(year, int(mo), int(d), int(hh), int(mm), int(ss or 0), tzinfo=TZ)
            posts.append({"ts": ts, "sender": sender.strip(), "lines": [body]})
        elif posts:
            posts[-1]["lines"].append(line)
    out, seen = [], {}
    for p in posts:
        body = "\n".join(p["lines"]).strip()
        if not body or body in SYSTEM_LINES:
            continue
        base = f"{chat}|{p['ts'].isoformat()}"
        seen[base] = seen.get(base, 0) + 1
        out.append(RawPost(source="whatsapp", source_id=f"{base}|{seen[base]}", channel=chat,
                           sender=p["sender"], ts=p["ts"], text=body))
    return out


def parse_whatsapp_json(items: list[dict]) -> list[RawPost]:
    out = []
    for it in items:
        text = (it.get("text") or "").strip()
        if not text:
            continue
        ts = datetime.fromisoformat(it["timestamp"]) if it.get("timestamp") else None
        out.append(RawPost(source="whatsapp", source_id=str(it["id"]), channel=it.get("chat", ""),
                           sender=it.get("sender", ""), ts=_aware(ts), text=text))
    return out


class WhatsAppExportSource:
    """Reads every *.txt and *.json under `folder`. For .txt files the chat name is the file
    name (e.g. "Tech Referrals Senior 5+.txt"); .json files carry it per message.
    `groups`: only these chats (None = all)."""

    name = "whatsapp"

    def __init__(self, folder: Union[str, Path], groups: Optional[Iterable[str]] = None):
        self.folder = Path(folder)
        self.groups = set(groups) if groups else None

    def fetch(self, since: Optional[datetime] = None) -> list[RawPost]:
        posts: list[RawPost] = []
        if not self.folder.exists():
            return posts
        for f in sorted(self.folder.iterdir()):
            if f.suffix == ".txt":
                posts += parse_whatsapp_txt(f.read_text(encoding="utf-8"), chat=f.stem)
            elif f.suffix == ".json":
                posts += parse_whatsapp_json(json.loads(f.read_text(encoding="utf-8")))
        return [p for p in posts if (self.groups is None or p.channel in self.groups) and _newer(p.ts, since)]


# ---------------------------------------------------------------- Airtable
DEFAULT_FIELDS = ("Title", "Company", "Location", "Description", "Link")


def airtable_record_to_post(rec: dict, view: str, fields: Iterable[str] = DEFAULT_FIELDS) -> Optional[RawPost]:
    """One Airtable record -> RawPost. The text is the fields joined as 'Field: value' lines,
    so the extractor sees a post-like text. Empty fields are absent in API responses."""
    f = rec.get("fields", {})
    lines = [f"{k}: {f[k]}" for k in fields if f.get(k) not in (None, "")]
    if not lines:
        return None
    ts = datetime.fromisoformat(rec["createdTime"].replace("Z", "+00:00")) if rec.get("createdTime") else None
    return RawPost(source="airtable", source_id=rec["id"], channel=view, ts=ts, text="\n".join(lines))


class AirtableAPISource:
    """GET https://api.airtable.com/v0/{base}/{table}?view=...&pageSize=100&offset=...

    Auth: a personal access token with scope data.records:read, from AIRTABLE_TOKEN in .env.
    Pagination: the response carries `offset` while more pages exist.
    Rate limit: 5 requests per second per base; a 429 means wait 30 seconds.
    `http` can be an httpx.Client with a MockTransport (tests)."""

    name = "airtable"
    URL = "https://api.airtable.com/v0/{base}/{table}"

    def __init__(self, base_id: str, table: str, view: str, token: str, *, fields: Iterable[str] = DEFAULT_FIELDS,
                 http: Optional[httpx.Client] = None, sleep: Callable[[float], None] = time.sleep, max_pages: int = 20):
        self.base_id, self.table, self.view, self.token = base_id, table, view, token
        self.fields = tuple(fields)
        self.http = http or httpx.Client(timeout=httpx.Timeout(15.0, connect=5.0))
        self.sleep = sleep
        self.max_pages = max_pages

    def fetch(self, since: Optional[datetime] = None) -> list[RawPost]:
        url = self.URL.format(base=self.base_id, table=self.table)
        params: dict = {"view": self.view, "pageSize": 100}
        if since is not None:
            iso = _aware(since).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
            params["filterByFormula"] = f"IS_AFTER(CREATED_TIME(), '{iso}')"
        headers = {"Authorization": f"Bearer {self.token}"}
        out: list[RawPost] = []
        for _ in range(self.max_pages):
            r = self.http.get(url, params=params, headers=headers)
            if r.status_code == 429:  # documented: wait 30 seconds before the next request
                self.sleep(30)
                r = self.http.get(url, params=params, headers=headers)
            r.raise_for_status()
            body = r.json()
            for rec in body.get("records", []):
                p = airtable_record_to_post(rec, self.view, self.fields)
                if p and _newer(p.ts, since):
                    out.append(p)
            if not body.get("offset"):
                break
            params["offset"] = body["offset"]
            self.sleep(0.25)  # stay under 5 requests per second
        return out


class AirtableCSVSource:
    """A CSV downloaded from a shared view. No API access needed. Record ids are not in the
    CSV, so the id is a hash of the row (the same row always gets the same id)."""

    name = "airtable"

    def __init__(self, path: Union[str, Path], view: str = "New Jobs", fields: Iterable[str] = DEFAULT_FIELDS):
        self.path, self.view, self.fields = Path(path), view, tuple(fields)

    def fetch(self, since: Optional[datetime] = None) -> list[RawPost]:
        import hashlib

        if not self.path.exists():
            return []
        out = []
        with self.path.open(encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                rid = "csv" + hashlib.sha1(json.dumps(row, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]
                rec = {"id": rid, "fields": row}
                if row.get("Created"):
                    rec["createdTime"] = row["Created"]
                p = airtable_record_to_post(rec, self.view, self.fields)
                if p and _newer(p.ts, since):
                    out.append(p)
        return out


class AirtableFixtureSource:
    """A saved API response (or a list of them): the same parsing as the live API."""

    name = "airtable"

    def __init__(self, path: Union[str, Path], view: str = "New Jobs"):
        self.path, self.view = Path(path), view

    def fetch(self, since: Optional[datetime] = None) -> list[RawPost]:
        if not self.path.exists():
            return []
        body = json.loads(self.path.read_text(encoding="utf-8"))
        pages = body if isinstance(body, list) else [body]
        out = []
        for page in pages:
            for rec in page.get("records", []):
                p = airtable_record_to_post(rec, self.view)
                if p and _newer(p.ts, since):
                    out.append(p)
        return out


class FixtureSource:
    """A JSON/JSONL file of RawPost dicts, or an in-memory list."""

    def __init__(self, posts: Union[str, Path, list[RawPost]], name: str = "fixture"):
        self.name = name
        if isinstance(posts, (str, Path)):
            text = Path(posts).read_text(encoding="utf-8")
            items = [json.loads(l) for l in text.splitlines() if l.strip()] if str(posts).endswith(".jsonl") \
                else json.loads(text)
            self.posts = [RawPost(**it) for it in items]
        else:
            self.posts = list(posts)

    def fetch(self, since: Optional[datetime] = None) -> list[RawPost]:
        return [p for p in self.posts if _newer(p.ts, since)]
