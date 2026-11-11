"""Reference implementations of the M2 milestones (solutions branch only).

This file exists only on the `solutions` branch of the course repo. On `main` the tool runs your
functions from mine.py, and a milestone you have not written yet stops the command with a message
that names it. Compare with this file AFTER your tests pass.
"""

from __future__ import annotations

import re
from fnmatch import fnmatchcase
from typing import Callable, Optional
from xml.sax.saxutils import escape, quoteattr

from guardkit.redact import redact_pii
from llmkit import ChatRequest, Message
from ragkit.rag import parse_citations
from ragkit.types import Chunk, Document, Hit

from .answer import SYSTEM, Citation
from .dedup import jaccard, shingles
from .manifest import SyncPlan
from .privacy import BANK_ACCOUNT_RE, CARD_RE, IBAN_RE, LABELS, luhn_ok
from .query import KEYS, LANGS, TOKEN, TYPES, ParsedQuery, norm_date


def _glob_regex(pattern: str) -> re.Pattern:
    """Translate a path pattern with ** into a regex over the whole relative path."""
    i, out = 0, []
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append(r"(?:[^/]*/)*")
            i += 3
        elif pattern.startswith("**", i):
            out.append(r".*")
            i += 2
        elif pattern[i] == "*":
            out.append(r"[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append(r"[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("".join(out) + r"\Z")


def is_excluded(rel_path: str, patterns: list[str]) -> Optional[str]:
    """Reference implementation. Returns the FIRST pattern (in list order) that excludes
    rel_path, or None. See the module docstring for the semantics."""
    path = rel_path.replace("\\", "/").lower()
    while path.startswith("./"):
        path = path[2:]
    path = path.strip("/")
    parts = path.split("/")
    dirs, name = parts[:-1], parts[-1]
    for raw in patterns:
        pat = raw.strip().lower()
        if not pat or pat.startswith("#"):
            continue
        if pat.endswith("/"):
            body = pat.rstrip("/")
            if "/" in body:
                if any(_glob_regex(body).match("/".join(dirs[: i + 1])) for i in range(len(dirs))):
                    return raw
            elif any(fnmatchcase(d, body) for d in dirs):
                return raw
        elif "/" in pat:
            if _glob_regex(pat.lstrip("/")).match(path):
                return raw
        elif any(fnmatchcase(c, pat) for c in dirs + [name]):
            return raw
    return None


def plan_sync(manifest: dict[str, dict], current: dict[str, dict],
              hash_fn: Callable[[str], str]) -> SyncPlan:
    """Reference implementation (see mine.plan_sync for the contract)."""
    plan = SyncPlan()
    for fid in sorted(current):
        st = current[fid]
        old = manifest.get(fid)
        if old is None:
            plan.hashes[fid] = hash_fn(fid)
            plan.added.append(fid)
            continue
        if old.get("size") == st.get("size") and old.get("mtime") == st.get("mtime"):
            plan.unchanged.append(fid)
            continue
        h = hash_fn(fid)
        plan.hashes[fid] = h
        (plan.touched if h == old.get("hash") else plan.changed).append(fid)
    plan.removed = sorted(fid for fid in manifest if fid not in current)
    return plan


def parse_query(q: str) -> ParsedQuery:
    """Reference implementation (see mine.parse_query for the contract)."""
    filters: dict = {}
    warnings: list[str] = []
    keep: list[str] = []
    pos = 0
    for m in TOKEN.finditer(q):
        key = KEYS.get(m.group(1).lower())
        if key is None:
            continue
        keep.append(q[pos:m.start()])
        pos = m.end()
        value = m.group(2) if m.group(2) is not None else m.group(3)
        if key == "type":
            for v in value.split(","):
                t = TYPES.get(v.strip().lower())
                if t:
                    filters.setdefault("type", [])
                    if t not in filters["type"]:
                        filters["type"].append(t)
                else:
                    warnings.append(f"unknown type {v!r}")
        elif key == "folder":
            for v in value.split(","):
                v = v.strip().strip("/").lower()
                if v:
                    filters.setdefault("folder", []).append(v)
        elif key in ("after", "before"):
            d = norm_date(value)
            if d:
                filters[key] = d
            else:
                warnings.append(f"bad date {value!r} (use YYYY, YYYY-MM or YYYY-MM-DD)")
                keep.append(m.group(0))
        elif key == "lang":
            lang = LANGS.get(value.strip().lower())
            if lang:
                filters["lang"] = lang
            else:
                warnings.append(f"unknown language {value!r}")
    keep.append(q[pos:])
    text = " ".join("".join(keep).split())
    return ParsedQuery(text=text, filters=filters, warnings=warnings)


def near_duplicate_groups(docs: dict[str, str], threshold: float = 0.8, k: int = 3) -> list[list[str]]:
    """Reference implementation (see mine.near_duplicate_groups for the contract)."""
    ids = sorted(docs)
    sh = {i: shingles(docs[i], k) for i in ids}
    parent = {i: i for i in ids}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for n, a in enumerate(ids):
        if not sh[a]:
            continue
        for b in ids[n + 1:]:
            if sh[b] and jaccard(sh[a], sh[b]) >= threshold:
                ra, rb = find(a), find(b)
                if ra != rb:
                    parent[max(ra, rb)] = min(ra, rb)
    groups: dict[str, list[str]] = {}
    for i in ids:
        groups.setdefault(find(i), []).append(i)
    return sorted((sorted(g) for g in groups.values() if len(g) > 1), key=lambda g: g[0])


def redact_for_cloud(text: str) -> tuple[str, dict[str, int]]:
    """Reference implementation (see mine.redact_for_cloud for the contract)."""
    counts = {k: 0 for k in LABELS}

    def sub_iban(m: re.Match) -> str:
        counts["IBAN"] += 1
        return "[IBAN]"

    def sub_card(m: re.Match) -> str:
        digits = re.sub(r"\D", "", m.group(0))
        if 13 <= len(digits) <= 19 and luhn_ok(digits):
            counts["CARD"] += 1
            return "[CARD]"
        return m.group(0)

    text = IBAN_RE.sub(sub_iban, text)
    text = CARD_RE.sub(sub_card, text)
    before = {k: text.count(f"[{k}]") for k in ("IL_ID", "EMAIL", "PHONE")}
    text = redact_pii(text)
    for k in ("IL_ID", "EMAIL", "PHONE"):
        counts[k] += text.count(f"[{k}]") - before[k]

    def sub_acct(m: re.Match) -> str:
        counts["BANK_ACCOUNT"] += 1
        return "[BANK_ACCOUNT]"

    text = BANK_ACCOUNT_RE.sub(sub_acct, text)
    return text, {k: v for k, v in counts.items() if v}


def format_source(n: int, hit: Hit, max_chars: Optional[int] = None) -> str:
    c = hit.chunk
    attrs = {"file": c.doc_id, "page": str(c.meta.get("page") or ""), "date": c.meta.get("date") or "",
             "title": c.title.split(" | ")[0]}
    a = " ".join(f"{k}={quoteattr(v)}" for k, v in attrs.items() if v)
    body = c.text if not max_chars or len(c.text) <= max_chars else c.text[:max_chars] + " …"
    return f'<source id="{n}" {a}>\n{escape(body)}\n</source>'


def build_request(question: str, hits: list[Hit], *, max_chars: Optional[int] = None,
                  max_tokens: int = 400) -> ChatRequest:
    sources = "\n".join(format_source(i + 1, h, max_chars) for i, h in enumerate(hits)) or "(no sources found)"
    user = f"<sources>\n{sources}\n</sources>\n\n<question>{escape(question)}</question>"
    return ChatRequest(messages=[Message("user", user)], system=SYSTEM, max_tokens=max_tokens)


def resolve_citations(text: str, hits: list[Hit]) -> tuple[list[Citation], list[int]]:
    nums = parse_citations(text)
    good = [Citation(n, hits[n - 1].chunk.doc_id, hits[n - 1].chunk.meta.get("page"),
                     hits[n - 1].chunk.title.split(" | ")[0], hits[n - 1].chunk.text)
            for n in nums if 1 <= n <= len(hits)]
    return good, [n for n in nums if not 1 <= n <= len(hits)]


# ------------------------------------------------------------------ M3b: a file becomes chunks
def file_to_chunks(ex, entry, chunker) -> list[Chunk]:
    out: list[Chunk] = []
    title = f"{ex.title} | {ex.id}"
    for u in ex.units:
        if not u.text.strip():
            continue
        doc = Document(id=ex.id, text=u.text, meta={"title": title, "language": ex.language,
                                                     "format": ex.format, "source_path": str(entry.path)})
        for c in chunker.split(doc):
            n = len(out)
            c.id = f"{ex.id}#p{u.page}.{c.index}" if u.page else f"{ex.id}#{c.index}"
            c.index = n
            c.meta.update({"file": ex.id, "folder": entry.folder, "date": ex.date, "page": u.page,
                           "format": ex.format, "language": ex.language})
            out.append(c)
    return out


# ------------------------------------------------------------------ M8b: what may go to the cloud
def select_for_cloud(hits: list[Hit], never_send: list[str], max_sources: int) -> tuple[list[Hit], list[str]]:
    from . import hooks
    excluded = hooks.get("is_excluded")
    withheld = sorted({h.chunk.doc_id for h in hits if excluded(h.chunk.doc_id, never_send) is not None})
    send = [h for h in hits if h.chunk.doc_id not in withheld][:max_sources]
    return send, withheld


# ------------------------------------------------------------------ M4: retrieval metrics per question
def retrieval_row(q: dict, ranked: list[tuple[str, Optional[int]]]) -> dict:
    ids = [f for f, _ in ranked]
    rel = set(q["relevant"])
    first = next((i for i, f in enumerate(ids) if f in rel), None)
    page_ok = None
    if q.get("pages"):
        pf = next(((f, p) for f, p in ranked if f in q["pages"]), None)
        page_ok = bool(pf and pf[1] in q["pages"][pf[0]])
    row = {"rr": 1.0 / (first + 1) if first is not None else 0.0, "page_ok": page_ok,
           "must_not_hit": sorted(set(q.get("must_not", [])) & set(ids))}
    for k in (1, 5, 10):
        row[f"r{k}"] = (len(rel & set(ids[:k])) / len(rel)) if rel else 0.0
    return row
