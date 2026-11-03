"""SQLite state: classes, students, sessions, turns, vocabulary cards, progress, teacher content,
safety events. One file, one writer: right for a pilot with a few classes (see README for
when to move to Postgres).

Data minimization (students are minors):
- A student is a class code + a nickname + the grammatical gender they chose for Hebrew. No
  real name, no phone, no email, no birth date. The student token is stored only as a sha256.
- Turn text is stored REDACTED (redact_for_log ran before). Audio is never stored: it lives in
  memory for the length of one request.
- purge(retention_days) deletes turns older than the retention window (default 30 days) and
  safety events older than 90 days; progress, points and cards stay, because they hold no text
  the student wrote. Run it daily (python -m hebtutor purge, or a cron / scheduled task).
"""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import threading
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Union

from .learner import Card

SCHEMA = """
CREATE TABLE IF NOT EXISTS classes (code TEXT PRIMARY KEY, name TEXT, teacher_token_sha TEXT, created TEXT);
CREATE TABLE IF NOT EXISTS students (id TEXT PRIMARY KEY, class_code TEXT REFERENCES classes(code), nickname TEXT,
    addressing TEXT, token_sha TEXT UNIQUE, level TEXT DEFAULT 'A1', level_score REAL DEFAULT 1.5,
    points INTEGER DEFAULT 0, created TEXT, UNIQUE(class_code, nickname));
CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, student_id TEXT, scenario_id TEXT, level TEXT,
    state TEXT, created TEXT, updated TEXT);
CREATE TABLE IF NOT EXISTS turns (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, student_id TEXT, ts TEXT,
    mode TEXT, text_redacted TEXT, assessment TEXT, input_flag TEXT, cost_usd REAL, timings TEXT);
CREATE TABLE IF NOT EXISTS cards (student_id TEXT, vocab_id TEXT, he TEXT, ar TEXT, ef REAL, reps INTEGER,
    interval INTEGER, due TEXT, lapses INTEGER, PRIMARY KEY(student_id, vocab_id));
CREATE TABLE IF NOT EXISTS progress (student_id TEXT, scenario_id TEXT, turns INTEGER DEFAULT 0,
    clean_turns INTEGER DEFAULT 0, done INTEGER DEFAULT 0, errors TEXT DEFAULT '{}', PRIMARY KEY(student_id, scenario_id));
CREATE TABLE IF NOT EXISTS submissions (id TEXT PRIMARY KEY, class_code TEXT, kind TEXT, scenario TEXT, level TEXT,
    he TEXT, ar TEXT, transliteration TEXT, status TEXT, findings TEXT, created TEXT, decided TEXT, note TEXT);
CREATE TABLE IF NOT EXISTS safety_events (id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT, class_code TEXT,
    ts TEXT, flag TEXT, reasons TEXT, text_redacted TEXT, seen INTEGER DEFAULT 0);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_code(n: int = 6) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I: codes are read aloud in class
    return "".join(secrets.choice(alphabet) for _ in range(n))


class Store:
    def __init__(self, path: Union[str, Path] = ":memory:"):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        with self.lock:
            self.db.executescript(SCHEMA)
            if self.path != ":memory:":
                self.db.execute("PRAGMA journal_mode=WAL")
            self.db.commit()

    def _x(self, sql: str, args=()) -> sqlite3.Cursor:
        with self.lock:
            cur = self.db.execute(sql, args)
            self.db.commit()
            return cur

    def _one(self, sql: str, args=()) -> Optional[dict]:
        with self.lock:
            r = self.db.execute(sql, args).fetchone()
        return dict(r) if r else None

    def _all(self, sql: str, args=()) -> list[dict]:
        with self.lock:
            return [dict(r) for r in self.db.execute(sql, args).fetchall()]

    # ------------------------------------------------------------ classes and students
    def create_class(self, name: str) -> tuple[str, str]:
        code, token = new_code(), secrets.token_urlsafe(18)
        self._x("INSERT INTO classes VALUES (?,?,?,?)", (code, name, sha(token), now()))
        return code, token

    def class_by_teacher(self, token: str) -> Optional[dict]:
        return self._one("SELECT code, name FROM classes WHERE teacher_token_sha=?", (sha(token or ""),))

    def join(self, class_code: str, nickname: str, addressing: str = "m") -> tuple[str, str]:
        if not self._one("SELECT code FROM classes WHERE code=?", (class_code,)):
            raise KeyError("unknown class code")
        sid, token = "s_" + secrets.token_hex(6), secrets.token_urlsafe(18)
        self._x("INSERT INTO students (id, class_code, nickname, addressing, token_sha, created) VALUES (?,?,?,?,?,?)",
                (sid, class_code, nickname, addressing, sha(token), now()))
        return sid, token

    def student_by_token(self, token: str) -> Optional[dict]:
        return self._one("SELECT * FROM students WHERE token_sha=?", (sha(token or ""),))

    def student(self, sid: str) -> Optional[dict]:
        return self._one("SELECT * FROM students WHERE id=?", (sid,))

    def update_student(self, sid: str, **kw) -> None:
        sets = ", ".join(f"{k}=?" for k in kw)
        self._x(f"UPDATE students SET {sets} WHERE id=?", (*kw.values(), sid))

    # ------------------------------------------------------------ sessions and turns
    def create_session(self, student_id: str, scenario_id: str, level: str, state: dict) -> str:
        sid = "x_" + secrets.token_hex(6)
        self._x("INSERT INTO sessions VALUES (?,?,?,?,?,?,?)",
                (sid, student_id, scenario_id, level, json.dumps(state, ensure_ascii=False), now(), now()))
        return sid

    def session(self, sid: str) -> Optional[dict]:
        r = self._one("SELECT * FROM sessions WHERE id=?", (sid,))
        if r:
            r["state"] = json.loads(r["state"])
        return r

    def save_state(self, sid: str, state: dict) -> None:
        self._x("UPDATE sessions SET state=?, updated=? WHERE id=?", (json.dumps(state, ensure_ascii=False), now(), sid))

    def add_turn(self, session_id: str, student_id: str, mode: str, text_redacted: str, assessment: dict,
                 input_flag: str, cost: float, timings: dict) -> None:
        self._x("INSERT INTO turns (session_id, student_id, ts, mode, text_redacted, assessment, input_flag, cost_usd, timings)"
                " VALUES (?,?,?,?,?,?,?,?,?)", (session_id, student_id, now(), mode, text_redacted,
                                               json.dumps(assessment, ensure_ascii=False), input_flag, cost,
                                               json.dumps(timings)))

    def turns(self, session_id: str) -> list[dict]:
        return self._all("SELECT * FROM turns WHERE session_id=? ORDER BY id", (session_id,))

    # ------------------------------------------------------------ progress
    def bump_progress(self, student_id: str, scenario_id: str, clean: bool, error_type: Optional[str]) -> dict:
        self._x("INSERT OR IGNORE INTO progress (student_id, scenario_id) VALUES (?,?)", (student_id, scenario_id))
        p = self._one("SELECT * FROM progress WHERE student_id=? AND scenario_id=?", (student_id, scenario_id))
        errors = json.loads(p["errors"])
        if error_type:
            errors[error_type] = errors.get(error_type, 0) + 1
        self._x("UPDATE progress SET turns=turns+1, clean_turns=clean_turns+?, errors=? WHERE student_id=? AND scenario_id=?",
                (1 if clean else 0, json.dumps(errors), student_id, scenario_id))
        return self._one("SELECT * FROM progress WHERE student_id=? AND scenario_id=?", (student_id, scenario_id))

    def mark_done(self, student_id: str, scenario_id: str) -> None:
        self._x("UPDATE progress SET done=1 WHERE student_id=? AND scenario_id=?", (student_id, scenario_id))

    def progress(self, student_id: str) -> list[dict]:
        rows = self._all("SELECT scenario_id, turns, clean_turns, done, errors FROM progress WHERE student_id=?", (student_id,))
        for r in rows:
            r["errors"] = json.loads(r["errors"])
            r["done"] = bool(r["done"])
        return rows

    # ------------------------------------------------------------ cards
    def card(self, student_id: str, vocab_id: str) -> Optional[Card]:
        r = self._one("SELECT * FROM cards WHERE student_id=? AND vocab_id=?", (student_id, vocab_id))
        if not r:
            return None
        r.pop("student_id")
        return Card(**r)

    def put_card(self, student_id: str, c: Card) -> None:
        self._x("INSERT OR REPLACE INTO cards VALUES (?,?,?,?,?,?,?,?,?)",
                (student_id, c.vocab_id, c.he, c.ar, c.ef, c.reps, c.interval, c.due, c.lapses))

    def due_cards(self, student_id: str, today: date, limit: int = 20) -> list[Card]:
        rows = self._all("SELECT * FROM cards WHERE student_id=? AND due<=? ORDER BY due, vocab_id LIMIT ?",
                         (student_id, today.isoformat(), limit))
        out = []
        for r in rows:
            r.pop("student_id")
            out.append(Card(**r))
        return out

    # ------------------------------------------------------------ teacher content
    def add_submission(self, class_code: str, item: dict, status: str, findings: list) -> str:
        sid = "c_" + secrets.token_hex(5)
        self._x("INSERT INTO submissions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (sid, class_code, item.get("kind", "vocab"), item.get("scenario"), item.get("level"), item.get("he"),
                 item.get("ar"), item.get("transliteration", ""), status,
                 json.dumps([asdict(f) for f in findings], ensure_ascii=False), now(), None, None))
        return sid

    def submissions(self, status: Optional[str] = None) -> list[dict]:
        q, args = "SELECT * FROM submissions", ()
        if status:
            q, args = q + " WHERE status=?", (status,)
        rows = self._all(q + " ORDER BY created", args)
        for r in rows:
            r["findings"] = json.loads(r["findings"])
        return rows

    def decide(self, sub_id: str, status: str, note: str = "") -> Optional[dict]:
        self._x("UPDATE submissions SET status=?, decided=?, note=? WHERE id=? AND status='pending'",
                (status, now(), note, sub_id))
        return self._one("SELECT * FROM submissions WHERE id=?", (sub_id,))

    # ------------------------------------------------------------ safety
    def add_safety_event(self, student_id: str, class_code: str, flag: str, reasons: list[str], text_redacted: str) -> None:
        self._x("INSERT INTO safety_events (student_id, class_code, ts, flag, reasons, text_redacted) VALUES (?,?,?,?,?,?)",
                (student_id, class_code, now(), flag, ",".join(reasons), text_redacted))

    def safety_events(self, class_code: str) -> list[dict]:
        return self._all("SELECT e.id, s.nickname, e.ts, e.flag, e.reasons, e.text_redacted, e.seen FROM safety_events e "
                         "JOIN students s ON s.id=e.student_id WHERE e.class_code=? ORDER BY e.id DESC", (class_code,))

    # ------------------------------------------------------------ teacher dashboard
    def dashboard(self, class_code: str) -> dict:
        students = self._all("SELECT id, nickname, level, level_score, points FROM students WHERE class_code=? "
                             "ORDER BY nickname", (class_code,))
        week = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        for s in students:
            s["turns_7d"] = (self._one("SELECT COUNT(*) n FROM turns WHERE student_id=? AND ts>=?", (s["id"], week)) or {}).get("n", 0)
            errs: dict[str, int] = {}
            for p in self.progress(s["id"]):
                for k, v in p["errors"].items():
                    errs[k] = errs.get(k, 0) + v
            s["top_errors"] = sorted(errs.items(), key=lambda kv: -kv[1])[:3]
            s["scenarios_done"] = sum(1 for p in self.progress(s["id"]) if p["done"])
            s.pop("id")
        return {"class_code": class_code, "students": students, "safety_events": self.safety_events(class_code)}

    # ------------------------------------------------------------ retention
    def purge(self, retention_days: int = 30, safety_days: int = 90, *, today: Optional[datetime] = None) -> dict:
        t = today or datetime.now(timezone.utc)
        a = self._x("DELETE FROM turns WHERE ts < ?", ((t - timedelta(days=retention_days)).isoformat(),)).rowcount
        b = self._x("DELETE FROM safety_events WHERE ts < ?", ((t - timedelta(days=safety_days)).isoformat(),)).rowcount
        return {"turns_deleted": a, "safety_events_deleted": b}
