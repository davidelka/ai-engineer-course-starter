"""The content corpus (scenarios, phrases, vocabulary), retrieval of relevant phrases, and the
teacher-content approval workflow's validation.

Retrieval uses ragkit's BM25Index (lesson 9) with its Hebrew prefix analysis: each phrase and
vocabulary item is one Chunk with metadata {scenario, level, kind}, and the filter
`where={"scenario": ..., "level": [...]}` runs BEFORE ranking, so the tutor never gets a B1
phrase in an A1 session. The corpus is small (about 250 items): BM25 is enough, fast, free and
explainable. An embedding model would help with paraphrases ("כואבת לי הבטן" vs "יש לי כאבי
בטן"); measure before you add one.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ragkit.retrieval.bm25 import BM25Index
from ragkit.types import Chunk

from .models import LEVELS, Finding

DATA = Path(__file__).resolve().parent.parent / "data"
HEB = re.compile(r"[א-ת]")
ARB = re.compile(r"[ؠ-يٮ-ۓڤپچگ]")
NIQQUD = re.compile(r"[֑-ׇ]")
_TEMPLATE = re.compile(r"\{([^{}|]*)\|([^{}|]*)\}")


def levels_up_to(level: str) -> list[str]:
    return list(LEVELS[: LEVELS.index(level) + 1])


def render(text: str, addressing: str = "m") -> str:
    """'{ספר|ספרי} לי' -> 'ספר לי' (m) or 'ספרי לי' (f). Hebrew addresses the listener by gender."""
    return _TEMPLATE.sub(lambda m: m.group(1) if addressing != "f" else m.group(2), text)


def share(rx: re.Pattern, text: str) -> float:
    """Share of letters in `text` that match rx (Hebrew or Arabic letters)."""
    letters = [c for c in text if c.isalpha()]
    return sum(1 for c in letters if rx.match(c)) / len(letters) if letters else 0.0


def arabic_share(text: str) -> float:
    """Share of Arabic letters, ignoring Hebrew ones: an Arabic explanation that quotes the
    Hebrew fix ("نقول: בית הספר") is still Arabic."""
    return share(ARB, HEB.sub("", text))


@dataclass
class Scenario:
    id: str
    title_he: str
    title_ar: str
    levels: list[str]
    role_en: str
    goal_ar: dict[str, str]
    opening_he: dict[str, str]
    tutor_lines: dict[str, list[str]]
    phrases: list[dict]
    vocab_ids: list[str]
    map: dict = field(default_factory=dict)

    def phrases_for(self, level: str) -> list[dict]:
        allowed = levels_up_to(level)
        return [p for p in self.phrases if p["level"] in allowed]

    def public(self, level: Optional[str] = None) -> dict:
        """The shape the API returns (and the owner's React app reads)."""
        d = {"id": self.id, "title_he": self.title_he, "title_ar": self.title_ar, "levels": self.levels,
             "map": self.map, "goal_ar": self.goal_ar}
        if level:
            d["goal_ar"] = self.goal_ar.get(level)
            d["phrases"] = self.phrases_for(level)
        return d


class Content:
    def __init__(self, data_dir: Path = DATA):
        raw = json.loads((data_dir / "scenarios.json").read_text(encoding="utf-8"))
        self.version = raw["version"]
        self.scenarios: dict[str, Scenario] = {s["id"]: Scenario(**s) for s in raw["scenarios"]}
        self.vocab: list[dict] = [json.loads(l) for l in (data_dir / "vocab.jsonl").read_text(encoding="utf-8").splitlines()
                                  if l.strip()]
        self.by_id = {v["id"]: v for v in self.vocab}
        self.extra_words: list[str] = raw.get("extra_words", [])
        self.index = BM25Index(with_context=False)
        self._build_index()

    # ------------------------------------------------------------ retrieval
    def _build_index(self) -> None:
        chunks = []
        for s in self.scenarios.values():
            for i, p in enumerate(s.phrases):
                chunks.append(Chunk(id=f"{s.id}#p{i}", doc_id=s.id, text=p["he"], start=0, end=len(p["he"]),
                                    meta={"scenario": s.id, "level": p["level"], "kind": "phrase", "ar": p["ar"]}))
        for v in self.vocab:
            if v.get("status", "approved") == "approved":
                chunks.append(self._vocab_chunk(v))
        self.index.add(chunks)

    @staticmethod
    def _vocab_chunk(v: dict) -> Chunk:
        return Chunk(id=v["id"], doc_id=v["scenario"], text=v["he"], start=0, end=len(v["he"]),
                     meta={"scenario": v["scenario"], "level": v["level"], "kind": "vocab", "ar": v["ar"],
                           "transliteration": v["transliteration"]})

    def add_approved(self, item: dict) -> None:
        """An approved teacher submission becomes searchable immediately."""
        self.vocab.append(item)
        self.by_id[item["id"]] = item
        if item.get("kind", "vocab") == "phrase":
            self.index.add([Chunk(id=item["id"], doc_id=item["scenario"], text=item["he"], start=0, end=len(item["he"]),
                                  meta={"scenario": item["scenario"], "level": item["level"], "kind": "phrase",
                                        "ar": item["ar"]})])
        else:
            self.index.add([self._vocab_chunk(item)])

    def retrieve(self, scenario_id: str, level: str, query: str, k: int = 6) -> list[dict]:
        """Phrases and words of this scenario, at or below the level, relevant to what the student said.
        Falls back to the scenario's own phrases when nothing matches (a short "כן" matches nothing)."""
        where = {"scenario": scenario_id, "level": levels_up_to(level)}
        hits = self.index.search(query, k=k, where=where) if query.strip() else []
        out = [{"id": h.chunk.id, "he": h.chunk.text, "ar": h.chunk.meta["ar"], "kind": h.chunk.meta["kind"],
                "level": h.chunk.meta["level"], "score": round(h.score, 3)} for h in hits]
        if len(out) < 3:
            seen = {o["he"] for o in out}
            for p in self.scenarios[scenario_id].phrases_for(level):
                if p["he"] not in seen and len(out) < 3:
                    out.append({"id": None, "he": p["he"], "ar": p["ar"], "kind": "phrase", "level": p["level"],
                                "score": 0.0})
        return out

    # ------------------------------------------------------------ lexicon (used by the rule tutor)
    def lexicon(self) -> set[str]:
        words = set(self.extra_words)
        for v in self.vocab:
            words.update(v["he"].split())
        for s in self.scenarios.values():
            for p in s.phrases:
                words.update(re.findall(r"[א-ת'\"]+", p["he"]))
        return {w.strip("'\"") for w in words if w}

    def noun_genders(self) -> dict[str, str]:
        return {v["he"]: v["gender"] for v in self.vocab if v["pos"] == "noun" and v.get("gender") and " " not in v["he"]}

    def stats(self) -> dict:
        per_level = {lv: sum(1 for v in self.vocab if v["level"] == lv) for lv in LEVELS}
        return {"version": self.version, "scenarios": len(self.scenarios),
                "phrases": sum(len(s.phrases) for s in self.scenarios.values()),
                "vocab": len(self.vocab), "vocab_per_level": per_level}


# ---------------------------------------------------------------- teacher submissions
SUBMISSION_STATUSES = ("pending", "approved", "rejected")


def check_submission(item: dict, content: Content) -> list[Finding]:
    """Automatic checks before a teacher's item reaches the admin queue. An item with any "block"
    finding is rejected right away; the rest wait for a human admin (status "pending").
    The admin still decides: these checks catch mistakes, not bad pedagogy."""
    from .safety import screen_text  # local import: safety imports content helpers

    f: list[Finding] = []
    he, ar = (item.get("he") or "").strip(), (item.get("ar") or "").strip()
    if item.get("kind", "vocab") not in ("vocab", "phrase"):
        f.append(Finding("bad_kind", str(item.get("kind")), "block"))
    if item.get("scenario") not in content.scenarios:
        f.append(Finding("unknown_scenario", str(item.get("scenario")), "block"))
    if item.get("level") not in LEVELS:
        f.append(Finding("bad_level", str(item.get("level")), "block"))
    if not he or share(HEB, he) < 0.8:
        f.append(Finding("hebrew_missing", he, "block"))
    if NIQQUD.search(he):
        f.append(Finding("niqqud", "store Hebrew without niqqud; the TTS adds vowels itself", "warn"))
    if not ar or share(ARB, ar) < 0.6:
        f.append(Finding("arabic_gloss_missing", ar, "block"))
    tr = (item.get("transliteration") or "").strip()
    if item.get("kind", "vocab") == "vocab" and (not tr or share(ARB, tr) < 0.6):
        f.append(Finding("transliteration_missing", "write how to say it in Arabic letters", "warn"))
    if len(he) > (40 if item.get("kind", "vocab") == "vocab" else 120):
        f.append(Finding("too_long", str(len(he)), "warn"))
    flag = screen_text(he + " " + ar)
    if flag.flag in ("unsafe", "personal_info", "injection"):
        f.append(Finding(f"content_{flag.flag}", ", ".join(flag.reasons), "block"))
    if he and any(v["he"] == he and v["scenario"] == item.get("scenario") for v in content.vocab):
        f.append(Finding("duplicate", he, "warn"))
    return f
