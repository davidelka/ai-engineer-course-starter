"""State store: SQLite, one file. What makes runs idempotent and digests "only new".

Tables
    runs         one row per schedule slot (run_id = slot key, e.g. 2026-11-01T08:30). A slot
                 that finished is never run again; a slot stuck in "running" for longer than
                 STALE_MINUTES is taken over (the previous container died).
    posts        every post key ever seen, with a hash of its text. Re-reading the same WhatsApp
                 export or Airtable page costs nothing.
    extractions  cache: text hash + prompt version -> PostExtraction JSON. A repost with the same
                 text, or a re-run after a crash, does not pay the model again.
    jobs         one row per job fingerprint, with the run that first saw it and the run that
                 delivered it. "New" = not delivered before.

Delivery and marking happen in this order: build digest -> send -> mark delivered. If the send
fails, nothing is marked and the next run sends those jobs again (at-least-once). Marking
first would risk losing jobs silently (at-most-once). For a personal digest, a rare repeat is
better than a lost job.

In AWS the task is ephemeral, so the file lives in S3 between runs (S3StateSync): download at
start, upload at the end with If-Match on the ETag we downloaded. Two overlapping runs cannot
both win: the second upload gets 412 Precondition Failed instead of silently overwriting.
"""

from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator, Optional, Union

from .models import Job

STALE_MINUTES = 30

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY, status TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT,
  posts_in INTEGER DEFAULT 0, posts_new INTEGER DEFAULT 0, jobs_new INTEGER DEFAULT 0,
  matches INTEGER DEFAULT 0, cost_usd REAL DEFAULT 0, extractor TEXT, digest TEXT, error TEXT, report_path TEXT
);
CREATE TABLE IF NOT EXISTS posts (
  post_key TEXT PRIMARY KEY, text_hash TEXT NOT NULL, source TEXT, channel TEXT, ts TEXT, run_id TEXT,
  repost_of TEXT, text TEXT
);
CREATE TABLE IF NOT EXISTS extractions (
  text_hash TEXT NOT NULL, prompt_version TEXT NOT NULL, extractor TEXT NOT NULL, json TEXT NOT NULL,
  cost_usd REAL DEFAULT 0, created_at TEXT, PRIMARY KEY (text_hash, prompt_version, extractor)
);
CREATE TABLE IF NOT EXISTS jobs (
  fingerprint TEXT PRIMARY KEY, first_run TEXT, delivered_run TEXT, post_key TEXT, job_index INTEGER,
  title TEXT, company TEXT, location TEXT, tier TEXT, score INTEGER, category TEXT, json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS jobs_tier ON jobs(tier);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: Union[str, Path] = ":memory:"):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        if self.path != ":memory:":
            self.db.execute("PRAGMA journal_mode=WAL")  # the admin API reads while a run writes
        self.db.executescript(SCHEMA)

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield self.db
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    # ------------------------------------------------------------ runs
    def claim_run(self, run_id: str, *, force: bool = False, now: Optional[datetime] = None) -> bool:
        """Atomically mark the slot as running. False if it is done, or running and not stale."""
        now = now or datetime.now(timezone.utc)
        with self.tx() as db:
            row = db.execute("SELECT status, started_at FROM runs WHERE run_id=?", (run_id,)).fetchone()
            if row and not force:
                if row["status"] == "done":
                    return False
                if row["status"] == "running":
                    started = datetime.fromisoformat(row["started_at"])
                    if now - started < timedelta(minutes=STALE_MINUTES):
                        return False
            db.execute("INSERT OR REPLACE INTO runs (run_id, status, started_at) VALUES (?, 'running', ?)",
                       (run_id, now.isoformat(timespec="seconds")))
        return True

    def finish_run(self, run_id: str, *, status: str = "done", **fields) -> None:
        cols = ["status=?", "finished_at=?"] + [f"{k}=?" for k in fields]
        self.db.execute(f"UPDATE runs SET {', '.join(cols)} WHERE run_id=?",
                        [status, now_iso(), *fields.values(), run_id])

    def runs(self, limit: int = 50) -> list[dict]:
        return [dict(r) for r in self.db.execute("SELECT * FROM runs ORDER BY run_id DESC LIMIT ?", (limit,))]

    def run(self, run_id: str) -> Optional[dict]:
        r = self.db.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
        return dict(r) if r else None

    def done_slots(self) -> set[str]:
        return {r[0] for r in self.db.execute("SELECT run_id FROM runs WHERE status='done'")}

    def last_done(self) -> Optional[str]:
        r = self.db.execute("SELECT run_id FROM runs WHERE status='done' ORDER BY run_id DESC LIMIT 1").fetchone()
        return r[0] if r else None

    # ------------------------------------------------------------ posts
    def seen_post(self, post_key: str) -> bool:
        return self.db.execute("SELECT 1 FROM posts WHERE post_key=?", (post_key,)).fetchone() is not None

    def recent_texts(self, limit: int = 500) -> list[tuple[str, str]]:
        """(post_key, redacted text) of recent original posts, for repost detection."""
        return [(r[0], r[1] or "") for r in self.db.execute(
            "SELECT post_key, text FROM posts WHERE repost_of IS NULL ORDER BY rowid DESC LIMIT ?", (limit,))]

    def add_post(self, post_key: str, text_hash: str, source: str, channel: str, ts: Optional[str], run_id: str,
                 repost_of: Optional[str] = None, text: str = "") -> None:
        """text: store it REDACTED (safety.redact): the state file is a copy of personal data."""
        self.db.execute("INSERT OR IGNORE INTO posts VALUES (?,?,?,?,?,?,?,?)",
                        (post_key, text_hash, source, channel, ts, run_id, repost_of, text))

    # ------------------------------------------------------------ extraction cache
    def cached_extraction(self, text_hash: str, prompt_version: str, extractor: str) -> Optional[dict]:
        r = self.db.execute("SELECT json FROM extractions WHERE text_hash=? AND prompt_version=? AND extractor=?",
                            (text_hash, prompt_version, extractor)).fetchone()
        return json.loads(r[0]) if r else None

    def cache_extraction(self, text_hash: str, prompt_version: str, extractor: str, data: dict, cost: float) -> None:
        self.db.execute("INSERT OR REPLACE INTO extractions VALUES (?,?,?,?,?,?)",
                        (text_hash, prompt_version, extractor, json.dumps(data, ensure_ascii=False), cost, now_iso()))

    # ------------------------------------------------------------ jobs
    def known_job(self, fingerprint: str) -> bool:
        return self.db.execute("SELECT 1 FROM jobs WHERE fingerprint=?", (fingerprint,)).fetchone() is not None

    def all_postings(self, limit: int = 2000) -> list[tuple[str, dict]]:
        return [(r[0], json.loads(r[1])["posting"]) for r in
                self.db.execute("SELECT fingerprint, json FROM jobs ORDER BY rowid DESC LIMIT ?", (limit,))]

    def add_job(self, job: Job, run_id: str) -> None:
        p = job.posting
        self.db.execute("INSERT OR IGNORE INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (job.fingerprint, run_id, None, job.post_key, job.job_index, p.title, p.company, p.location,
                         job.tier, job.score, job.category, job.model_dump_json()))

    def mark_delivered(self, fingerprints: list[str], run_id: str) -> None:
        with self.tx() as db:
            db.executemany("UPDATE jobs SET delivered_run=? WHERE fingerprint=? AND delivered_run IS NULL",
                           [(run_id, f) for f in fingerprints])

    def undelivered(self) -> list[Job]:
        return [Job.model_validate_json(r[0]) for r in
                self.db.execute("SELECT json FROM jobs WHERE delivered_run IS NULL ORDER BY rowid")]

    def jobs(self, *, tier: Optional[str] = None, category: Optional[str] = None, limit: int = 100) -> list[dict]:
        q, args = "SELECT * FROM jobs WHERE 1=1", []
        if tier:
            q += " AND tier=?"
            args.append(tier)
        if category:
            q += " AND category=?"
            args.append(category)
        q += " ORDER BY rowid DESC LIMIT ?"
        args.append(limit)
        out = []
        for r in self.db.execute(q, args):
            d = dict(r)
            d["job"] = json.loads(d.pop("json"))
            out.append(d)
        return out

    def close(self) -> None:
        self.db.close()


class S3StateSync:
    """Keeps the SQLite file in S3 between ECS task runs, with optimistic concurrency.

        sync = S3StateSync("my-bucket", "job-agent/state.db", "/tmp/state.db")
        sync.download()          # remembers the ETag (or that the object did not exist)
        ... run ...
        sync.upload()            # If-Match: <etag>, or If-None-Match: * for the first upload

    A 412 on upload means another run wrote the state meanwhile: this run's result is NOT
    saved, and the error is raised so the task fails visibly (and the next slot re-does it).
    Requires boto3 (requirements-aws.txt). Conditional writes: S3 docs, "conditional writes"."""

    def __init__(self, bucket: str, key: str, local_path: Union[str, Path], client=None):
        self.bucket, self.key, self.local = bucket, key, Path(local_path)
        self._client = client
        self.etag: Optional[str] = None

    @property
    def client(self):
        if self._client is None:
            import boto3  # optional dependency: only the AWS deployment needs it

            self._client = boto3.client("s3")
        return self._client

    def download(self) -> bool:
        try:
            obj = self.client.get_object(Bucket=self.bucket, Key=self.key)
        except Exception as exc:  # NoSuchKey on the first run
            code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
            if code in ("NoSuchKey", "404", "AccessDenied") or "NoSuchKey" in type(exc).__name__:
                self.etag = None
                return False
            raise
        self.local.parent.mkdir(parents=True, exist_ok=True)
        self.local.write_bytes(obj["Body"].read())
        self.etag = obj["ETag"]
        return True

    def upload(self) -> str:
        body = self.local.read_bytes()
        kw = {"IfMatch": self.etag} if self.etag else {"IfNoneMatch": "*"}
        r = self.client.put_object(Bucket=self.bucket, Key=self.key, Body=body, **kw)
        self.etag = r.get("ETag", self.etag)
        return self.etag or ""


class S3Folder:
    """The bridge between the cloud run and the owner's computer, where the WhatsApp session lives:
    the computer pushes exports to inbox/, the task pulls them; the task writes digests to
    outbox/, the computer's sender pulls them and sends them to the group."""

    def __init__(self, bucket: str, client=None):
        self.bucket = bucket
        self._client = client

    @property
    def client(self):
        if self._client is None:
            import boto3

            self._client = boto3.client("s3")
        return self._client

    def download_prefix(self, prefix: str, local_dir: Union[str, Path]) -> int:
        """inbox/whatsapp/a.json -> <local_dir>/whatsapp/a.json. Returns the number of files."""
        n, token = 0, None
        while True:
            kw = {"Bucket": self.bucket, "Prefix": prefix, **({"ContinuationToken": token} if token else {})}
            page = self.client.list_objects_v2(**kw)
            for obj in page.get("Contents", []):
                rel = obj["Key"][len(prefix):]
                if not rel or rel.endswith("/") or ".." in Path(rel).parts:
                    continue
                dest = Path(local_dir) / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(self.client.get_object(Bucket=self.bucket, Key=obj["Key"])["Body"].read())
                n += 1
            if not page.get("IsTruncated"):
                return n
            token = page.get("NextContinuationToken")

    def put_text(self, key: str, text: str) -> None:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=text.encode("utf-8"),
                               ContentType="text/plain; charset=utf-8")
