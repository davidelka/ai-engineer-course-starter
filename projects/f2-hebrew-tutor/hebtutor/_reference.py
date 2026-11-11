"""Reference implementations of the F2 milestones (solutions branch only).

This file exists only on the `solutions` branch of the course repo. On `main` the tutor runs your
functions from mine.py, and a milestone you have not written yet stops the command with a message
that names it. Compare with this file AFTER your tests pass.
"""

from __future__ import annotations


import math
import re
from dataclasses import replace
from datetime import date, timedelta
from typing import Optional

from guardkit.redact import is_valid_israeli_id
from voicekit.text import align, cer, normalize_hebrew

from hebtutor.content import ARB, HEB, Content, arabic_share, levels_up_to, share
from hebtutor.learner import ALPHA, BAND_MID, MARGIN, Card, level_of
from hebtutor.models import LEVELS, Assessment, Finding, SessionState
from hebtutor.prompts import LEVEL_LIMITS, STATIC_RULES, session_block, user_turn
from hebtutor.rules import EXPLAIN_AR
from hebtutor.safety import (_ADDRESS, _EMAIL, _NAME, _PHONE, _STOP_AFTER_NAME, _URL, DISTRESS, FLAG_ORDER, INJECTION,
                             OFF_TOPIC, OUT_BLOCK, PII, UNSAFE, Screen)
from hebtutor.speaking import SpeakingFeedback, WordResult, homophone_key, sound_hint
from hebtutor.validate import FALLBACK_REPLY, MAX_EXPLANATION, MAX_HELP, SEVERITY, cut, sentences


def screen_text(text: str, *, threshold: float = 2.0) -> Screen:
    """The cheap input screen. Highest-severity category whose score reaches the threshold wins."""
    text = text or ""
    found: dict[str, tuple[float, list[str]]] = {}
    for cat, signals in (("distress", DISTRESS), ("unsafe", UNSAFE), ("personal_info", PII)):
        score, reasons = 0.0, []
        for w, name, rx in signals:
            if rx.search(text):
                if name == "id_number" and not any(is_valid_israeli_id(m) for m in re.findall(r"(?<!\d)\d{9}(?!\d)", text)):
                    continue
                score += w
                reasons.append(name)
        found[cat] = (score, reasons)
    inj = INJECTION.detect(text, kind="user message")
    found["injection"] = (inj.score, list(inj.reasons))
    if OFF_TOPIC.search(text):
        found["off_topic"] = (2.0, ["off_topic_topic"])
    for cat in FLAG_ORDER[:-1]:
        score, reasons = found.get(cat, (0.0, []))
        if score >= (3.0 if cat == "injection" else threshold):
            return Screen(cat, reasons, score)
    top = max(found.values(), key=lambda x: x[0])
    return Screen("none", top[1], top[0], borderline=top[0] > 0)


def screen_output(sentence: str) -> Optional[str]:
    """None when the sentence may be shown; else the reason it was dropped."""
    if OUT_BLOCK.search(sentence):
        return "asks_for_personal_info_or_link"
    s = screen_text(sentence)
    if s.flag in ("unsafe", "distress"):
        return f"output_{s.flag}"
    if sentence.strip() and share(HEB, sentence) < 0.6 and share(ARB, sentence) < 0.6:
        return "not_hebrew"
    return None


def redact_for_log(text: str) -> tuple[str, list[str]]:
    """Reference version of milestone 6 (mine.redact_for_log). See the docstring there."""
    kinds: set[str] = set()

    def sub(rx, label, kind, s):
        def f(m):
            kinds.add(kind)
            return label
        return rx.sub(f, s)

    text = sub(_URL, "[קישור]", "url", text)
    text = sub(_EMAIL, "[מייל]", "email", text)
    text = sub(_PHONE, "[טלפון]", "phone", text)

    def ids(m):
        if is_valid_israeli_id(m.group(0)):
            kinds.add("id_number")
            return "[ת״ז]"
        return m.group(0)
    text = re.sub(r"(?<!\d)\d{9}(?!\d)", ids, text)
    text = sub(_ADDRESS, "[כתובת]", "address", text)

    def name(m):
        if m.group(3).split()[-1] in _STOP_AFTER_NAME:
            return m.group(0)
        kinds.add("full_name")
        return m.group(1) + "[שם]"
    text = _NAME.sub(name, text)
    return text, sorted(kinds)


def build_request(content: Content, st: SessionState, text: str, retrieved: list[dict], *, mode: str = "text",
                  max_tokens: int = 700, cache: bool = True, images=None):
    from llmkit.types import Block, ChatRequest, Message

    sc = content.scenarios[st.scenario_id]
    system = [Block(STATIC_RULES, cache="5m" if cache else None), Block(session_block(sc, st, mode))]
    msgs = [Message("user" if role == "student" else "assistant", t) for role, t in st.history[-8:]]
    body = user_turn(text, retrieved)
    msgs.append(Message.user_with(*images, body) if images else Message("user", body))
    return ChatRequest(messages=msgs, system=system, max_tokens=max_tokens)


def validate_assessment(a: Assessment, student_text: str, *, level: str = "A1", mode: str = "text",
                        input_flag: str = "none") -> tuple[Assessment, list[Finding]]:
    from hebtutor.content import render

    a = a.model_copy(deep=True)
    f: list[Finding] = []
    # ---- correction
    c = a.correction
    if c is not None:
        orig, fixed = normalize_hebrew(c.original), normalize_hebrew(c.corrected)
        if not orig or orig not in normalize_hebrew(student_text):
            f.append(Finding("correction_not_grounded", c.original, "block"))
            a.correction = None
        elif orig == fixed:
            f.append(Finding("correction_noop", c.original, "warn"))
            a.correction = None
        elif mode == "voice" and c.error_type == "spelling":
            f.append(Finding("spelling_in_voice", c.original, "info"))
            a.correction = None
        else:
            if arabic_share(c.explanation_ar) < 0.5:
                f.append(Finding("explanation_not_arabic", c.explanation_ar[:40], "warn"))
                c.explanation_ar = EXPLAIN_AR.get(c.error_type, EXPLAIN_AR["other"]).format(fix=c.corrected)
            if len(c.explanation_ar) > MAX_EXPLANATION:
                f.append(Finding("explanation_too_long", str(len(c.explanation_ar)), "warn"))
                c.explanation_ar = cut(c.explanation_ar, MAX_EXPLANATION)
    # ---- reply
    if share(HEB, a.reply_he) < 0.6:
        f.append(Finding("reply_not_hebrew", a.reply_he[:40], "block"))
        a.reply_he = render(FALLBACK_REPLY.get(level, FALLBACK_REPLY["A1"]), "m")
    else:
        lim = LEVEL_LIMITS.get(level, LEVEL_LIMITS["B1"])
        ss = sentences(a.reply_he)
        if len(ss) > lim["sentences"] + 1:
            f.append(Finding("reply_too_long", f"{len(ss)} sentences", "warn"))
            a.reply_he = " ".join(ss[:lim["sentences"] + 1])
    # ---- help
    if a.help_ar is not None:
        if arabic_share(a.help_ar) < 0.5:
            f.append(Finding("help_not_arabic", a.help_ar[:40], "warn"))
            a.help_ar = None
        elif len(a.help_ar) > MAX_HELP:
            f.append(Finding("help_too_long", str(len(a.help_ar)), "warn"))
            a.help_ar = cut(a.help_ar, MAX_HELP)
    # ---- vocabulary
    kept, seen = [], set()
    for v in a.new_vocabulary:
        key = normalize_hebrew(v.he)
        if share(HEB, v.he) < 0.8 or share(ARB, v.ar) < 0.5 or key in seen or len(kept) >= 3:
            f.append(Finding("vocab_dropped", v.he, "info"))
            continue
        seen.add(key)
        kept.append(v)
    a.new_vocabulary = kept
    # ---- safety: the model may raise a flag, never lower the screen's
    if input_flag != "none" and SEVERITY.index(a.safety_flag) > SEVERITY.index(input_flag):
        f.append(Finding("safety_downgrade", f"{input_flag} -> {a.safety_flag}", "block"))
        a.safety_flag = input_flag
    return a, f


def sm2_update(card: Card, quality: int, today: date) -> Card:
    """Reference. quality 0..5 (5 perfect, 3 correct with effort, below 3 failed)."""
    if not 0 <= quality <= 5:
        raise ValueError("quality must be 0..5")
    q = quality
    ef = max(1.3, card.ef + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)))
    if q < 3:
        reps, interval, lapses = 0, 1, card.lapses + 1
    else:
        reps = card.reps + 1
        interval = 1 if reps == 1 else 6 if reps == 2 else math.ceil(round(card.interval * ef, 6))
        lapses = card.lapses
    return replace(card, ef=round(ef, 4), reps=reps, interval=interval, lapses=lapses,
                   due=(today + timedelta(days=interval)).isoformat())


def update_level(score: float, level: str, signal: Optional[str]) -> tuple[float, str]:
    """Reference. Returns (new score, displayed level)."""
    if signal not in BAND_MID:
        return score, level
    s = min(3.99, max(1.0, score + ALPHA * (BAND_MID[signal] - score)))
    s = round(s, 4)
    i = LEVELS.index(level)
    lo, hi = float(i + 1), float(i + 2)  # band of the displayed level
    if s >= hi + MARGIN and i < 2:
        level = level_of(s)
    elif s < lo - MARGIN and i > 0:
        level = level_of(s)
    return s, level


def word_feedback(expected: str, heard: str) -> SpeakingFeedback:
    ref, hyp = normalize_hebrew(expected, finals=False).split(), normalize_hebrew(heard, finals=False).split()
    fb = SpeakingFeedback()
    for op, r, h in align(ref, hyp):
        if op == "ok":
            fb.words.append(WordResult(r, "ok", h, 0.0))
        elif op == "sub":
            c = round(cer(r, h).rate, 3)
            if homophone_key(r) == homophone_key(h):
                status = "homophone"
            elif c <= 0.34:
                status = "close"
            else:
                status = "wrong"
            fb.words.append(WordResult(r, status, h, c, sound_hint(r, h)))
        elif op == "del":
            fb.words.append(WordResult(r, "missing", "", 1.0))
        else:
            fb.extra.append(h)
    return fb


# ------------------------------------------------------------------ milestone 3: retrieval
def retrieve_phrases(content: Content, scenario_id: str, level: str, query: str, k: int = 6) -> list[dict]:
    where = {"scenario": scenario_id, "level": levels_up_to(level)}
    hits = content.index.search(query, k=k, where=where) if query.strip() else []
    out = [{"id": h.chunk.id, "he": h.chunk.text, "ar": h.chunk.meta["ar"], "kind": h.chunk.meta["kind"],
            "level": h.chunk.meta["level"], "score": round(h.score, 3)} for h in hits]
    if len(out) < 3:
        seen = {o["he"] for o in out}
        for p in content.scenarios[scenario_id].phrases_for(level):
            if p["he"] not in seen and len(out) < 3:
                out.append({"id": None, "he": p["he"], "ar": p["ar"], "kind": "phrase", "level": p["level"],
                            "score": 0.0})
    return out


# ------------------------------------------------------------------ milestone 4: streaming the reply
_ESC = {"n": "\n", "t": "\t", "r": "", "b": "", "f": ""}


def partial_json_field(buffer: str, field_name: str = "reply_he") -> tuple[str, bool]:
    key = f'"{field_name}"'
    k = buffer.find(key)
    if k < 0:
        return "", False
    colon = buffer.find(":", k + len(key))
    if colon < 0:
        return "", False
    q = buffer.find('"', colon + 1)
    if q < 0:
        return "", False
    out, i = [], q + 1
    while i < len(buffer):
        c = buffer[i]
        if c == "\\":
            if i + 1 >= len(buffer):
                break
            n = buffer[i + 1]
            if n == "u":
                if i + 6 > len(buffer):
                    break
                out.append(chr(int(buffer[i + 2:i + 6], 16)))
                i += 6
                continue
            out.append(_ESC.get(n, n))
            i += 2
            continue
        if c == '"':
            return "".join(out), True
        out.append(c)
        i += 1
    return "".join(out), False


# ------------------------------------------------------------------ milestone 9: correction metrics
def correction_metrics(rows: list[dict]) -> dict:
    tp = pred = gold_err = fp = 0
    per_type: dict[str, list[int]] = {}
    hits = []
    for r in rows:
        c, g = r.get("pred"), r["gold"]
        hit = bool(c and g["error_type"] and c["error_type"] == g["error_type"]
                   and (g.get("must_contain") or "") in (c.get("corrected") or ""))
        hits.append(hit)
        if c:
            pred += 1
        if g["error_type"]:
            gold_err += 1
            per_type.setdefault(g["error_type"], [0, 0])
            per_type[g["error_type"]][1] += 1
            if hit:
                per_type[g["error_type"]][0] += 1
        elif c:
            fp += 1
        tp += hit
    return {"tp": tp, "predicted": pred, "gold_errors": gold_err, "false_positive_on_correct": fp,
            "per_type": {k: v for k, v in sorted(per_type.items())}, "hits": hits}
