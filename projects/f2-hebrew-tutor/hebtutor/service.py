"""The application layer: everything the API (and the CLI demo) does, in one place.

The API is a thin HTTP shell over TutorService, so the same behavior is testable without HTTP
and reusable from the owner's React app through the API.
"""

from __future__ import annotations

import hashlib
import io
import re
from dataclasses import asdict
from datetime import date
from typing import Iterator, Optional

from .config import Settings
from .content import Content, check_submission, render
from .hooks import Hooks, pick_hooks
from .learner import POINTS, Card, scenario_done, turn_points
from .models import LEVELS, SessionState
from .safety import screen_text
from .store import Store
from .tutor import Tutor, TurnOutcome
from .voice import SpokenTurn

NICK = re.compile(r"^[\wא-תؠ-ي]{2,20}$")


class ServiceError(Exception):
    def __init__(self, status: int, title: str, detail: str = ""):
        super().__init__(detail or title)
        self.status, self.title, self.detail = status, title, detail


class TutorService:
    def __init__(self, settings: Optional[Settings] = None, *, content: Optional[Content] = None,
                 store: Optional[Store] = None, llm=None, stt=None, tts=None, hooks: Optional[Hooks] = None):
        self.s = settings or Settings.from_env()
        self.content = content or Content()
        self.store = store or Store(self.s.db_path)
        self.hooks = hooks or pick_hooks(quiet=True)
        self.llm = llm or self.s.make_llm(self.content)
        safety_llm = self.llm if self.s.safety_llm else None
        self.tutor = Tutor(self._instrument(self.llm), self.content, hooks=self.hooks, safety_llm=safety_llm)
        self._stt, self._tts = stt, tts
        self._spoken: Optional[SpokenTurn] = None

    def _instrument(self, llm):
        if not self.s.traces:
            return llm
        from obskit import InstrumentedLLM
        return InstrumentedLLM(llm, prompt_name="tutor", prompt_version="tutor-v2", capture_content=False)

    @property
    def spoken(self) -> SpokenTurn:
        if self._spoken is None:
            self._spoken = SpokenTurn(self._stt or self.s.make_stt(), self.tutor, self._tts or self.s.make_tts())
        return self._spoken

    # ------------------------------------------------------------ classes, students
    def create_class(self, name: str) -> dict:
        code, token = self.store.create_class(name)
        return {"class_code": code, "teacher_token": token}

    def join(self, class_code: str, nickname: str, addressing: str = "m") -> dict:
        nickname = nickname.strip()
        if not NICK.match(nickname) or screen_text(nickname).flag in ("unsafe", "personal_info"):
            raise ServiceError(422, "bad-nickname", "a nickname is one word of 2-20 letters, not a full name")
        if addressing not in ("m", "f"):
            raise ServiceError(422, "bad-addressing", "addressing must be m or f")
        try:
            sid, token = self.store.join(class_code.strip().upper(), nickname, addressing)
        except KeyError:
            raise ServiceError(404, "unknown-class", "no class with this code") from None
        except Exception as exc:  # sqlite IntegrityError: nickname taken in this class
            raise ServiceError(409, "nickname-taken", str(type(exc).__name__)) from None
        return {"student_id": sid, "student_token": token}

    # ------------------------------------------------------------ sessions
    def start_session(self, student: dict, scenario_id: str, level: Optional[str] = None) -> dict:
        sc = self.content.scenarios.get(scenario_id)
        if not sc:
            raise ServiceError(404, "unknown-scenario", scenario_id)
        lv = level or student["level"]
        if lv not in sc.levels:  # clip to what the scenario offers
            lv = min(sc.levels, key=lambda x: abs(LEVELS.index(x) - LEVELS.index(lv)))
        st = SessionState(scenario_id, lv, student["addressing"])
        line = self.tutor.start(st)
        sid = self.store.create_session(student["id"], scenario_id, lv, asdict(st))
        return {"session_id": sid, "scenario": sc.public(lv), "level": lv, "tutor_says": line,
                "ai_disclosure_ar": "أنت تتحدث مع برنامج ذكاء اصطناعي، وليس مع إنسان."}

    def practice(self, student: dict, session_id: str, phrase: Optional[str] = None) -> dict:
        """"Say this phrase": sets the phrase the next audio turn is compared with (speaking feedback).
        Without `phrase`, the next scenario phrase of the session's level, in order."""
        _, st = self._load(student, session_id)
        sc = self.content.scenarios[st.scenario_id]
        options = sc.phrases_for(st.level)
        if phrase is None:
            p = options[st.turn_index % len(options)]
        else:
            p = next((o for o in options if o["he"] == phrase), {"he": phrase[:120], "ar": ""})
        st.expected_phrase = p["he"]
        self.store.save_state(session_id, asdict(st))
        return {"say_he": p["he"], "meaning_ar": p["ar"]}

    def _load(self, student: dict, session_id: str) -> tuple[dict, SessionState]:
        sess = self.store.session(session_id)
        if not sess or sess["student_id"] != student["id"]:
            raise ServiceError(404, "unknown-session", session_id)
        d = sess["state"]
        d["history"] = [tuple(x) for x in d["history"]]
        return sess, SessionState(**d)

    def _after(self, student: dict, session_id: str, st: SessionState, out: TurnOutcome, mode: str) -> dict:
        a = out.assessment
        self.tutor.record(st, out)
        self.store.save_state(session_id, asdict(st))
        self.store.add_turn(session_id, student["id"], mode, out.redacted_text, a.model_dump(), out.screen.flag,
                            out.cost_usd, out.timings_ms)
        result = out.to_dict()
        flag = a.safety_flag
        if flag in ("distress", "unsafe", "personal_info"):
            self.store.add_safety_event(student["id"], student["class_code"], flag, out.screen.reasons, out.redacted_text)
        if flag != "none" or not out.model_called:
            result.update(points=student["points"], level=student["level"], points_earned=0)
            return result
        pts = turn_points(a.correction is not None, len(a.new_vocabulary))
        score, level = self.hooks.update_level(student["level_score"], student["level"], a.level_signal)
        p = self.store.bump_progress(student["id"], st.scenario_id, a.correction is None,
                                     a.correction.error_type if a.correction else None)
        if not p["done"] and scenario_done(p["turns"], p["clean_turns"]):
            self.store.mark_done(student["id"], st.scenario_id)
            pts += POINTS["scenario_done"]
            result["scenario_completed"] = True
        self.store.update_student(student["id"], points=student["points"] + pts, level=level, level_score=score)
        self._cards_from(student, a)
        result.update(points=student["points"] + pts, points_earned=pts, level=level, level_score=score,
                      level_changed=level != student["level"])
        return result

    def _cards_from(self, student: dict, a) -> None:
        """Missed and new words become review cards, due tomorrow."""
        today = date.today()
        words = [(v.he, v.ar) for v in a.new_vocabulary]
        if a.correction:
            for v in self.content.vocab:
                if v["he"] in a.correction.corrected and len(v["he"]) > 2:
                    words.append((v["he"], v["ar"]))
        for he, ar in words:
            vid = next((v["id"] for v in self.content.vocab if v["he"] == he),
                       "w_" + hashlib.sha1(he.encode()).hexdigest()[:8])
            if self.store.card(student["id"], vid) is None:
                c = self.hooks.sm2_update(Card(vid, he, ar), 2, today)  # "not known yet": due tomorrow
                self.store.put_card(student["id"], c)

    def text_turn(self, student: dict, session_id: str, text: str) -> dict:
        _, st = self._load(student, session_id)
        out = self.tutor.turn(st, text[:500], mode="text")
        return self._after(student, session_id, st, out, "text")

    def stream_text_turn(self, student: dict, session_id: str, text: str) -> Iterator[tuple[str, dict]]:
        _, st = self._load(student, session_id)
        for ev, val in self.tutor.stream_turn(st, text[:500], mode="text"):
            if ev == "sentence":
                yield "sentence", {"text": val}
            else:
                yield "assessment", self._after(student, session_id, st, val, "text")

    def audio_turn(self, student: dict, session_id: str, audio: bytes, *, filename: str = "audio.webm",
                   say: Optional[str] = None) -> dict:
        _, st = self._load(student, session_id)
        if say and self.s.stt == "fake":
            # Offline simulation: the fake recognizer cannot hear a browser recording, so the
            # "said" text is spoken by the fake TTS and heard back by the fake STT.
            from voicekit import FakeTTS
            audio, filename = FakeTTS().synthesize(say[:300]).audio, "audio.wav"
        vt = self.spoken.run(st, audio, filename=filename)
        d = vt.to_dict()
        if vt.outcome is not None:
            d["result"] = self._after(student, session_id, st, vt.outcome, "voice")
        d["audio_wav_b64"] = __import__("base64").b64encode(vt.audio_wav).decode() if vt.audio_wav else None
        return d

    def image_turn(self, student: dict, session_id: str, image: bytes, text: str) -> dict:
        """A photo (a sign, a form, a menu) plus a question. Metadata (EXIF, GPS) is stripped by
        re-encoding before the image goes anywhere; the image itself is not stored."""
        from llmkit.types import Image
        _, st = self._load(student, session_id)
        clean = strip_metadata(image)
        out = self.tutor.turn(st, (text or "מה כתוב כאן?")[:300], mode="text", images=[Image(data=clean)])
        return self._after(student, session_id, st, out, "image")

    # ------------------------------------------------------------ vocabulary review
    def due(self, student: dict, today: Optional[date] = None) -> list[dict]:
        return [c.to_dict() for c in self.store.due_cards(student["id"], today or date.today())]

    def review(self, student: dict, vocab_id: str, quality: int, today: Optional[date] = None) -> dict:
        c = self.store.card(student["id"], vocab_id)
        if c is None:
            raise ServiceError(404, "unknown-card", vocab_id)
        if not 0 <= quality <= 5:
            raise ServiceError(422, "bad-quality", "quality is 0..5")
        c = self.hooks.sm2_update(c, quality, today or date.today())
        self.store.put_card(student["id"], c)
        pts = POINTS["review_ok"] if quality >= 3 else POINTS["review_fail"]
        self.store.update_student(student["id"], points=student["points"] + pts)
        return {"card": c.to_dict(), "points_earned": pts}

    def progress(self, student: dict) -> dict:
        return {"nickname": student["nickname"], "level": student["level"], "level_score": student["level_score"],
                "points": student["points"], "scenarios": self.store.progress(student["id"]),
                "due_reviews": len(self.store.due_cards(student["id"], date.today()))}

    # ------------------------------------------------------------ teacher content
    def submit(self, class_code: str, item: dict) -> dict:
        findings = check_submission(item, self.content)
        status = "rejected" if any(f.severity == "block" for f in findings) else "pending"
        sid = self.store.add_submission(class_code, item, status, findings)
        return {"id": sid, "status": status, "findings": [asdict(f) for f in findings]}

    def decide(self, sub_id: str, approve: bool, note: str = "") -> dict:
        r = self.store.decide(sub_id, "approved" if approve else "rejected", note)
        if not r:
            raise ServiceError(404, "unknown-submission", sub_id)
        if r["status"] == "approved" and approve:
            self.content.add_approved({"id": sub_id, "kind": r["kind"], "he": r["he"], "ar": r["ar"],
                                       "transliteration": r["transliteration"], "level": r["level"],
                                       "scenario": r["scenario"], "pos": "teacher", "gender": None,
                                       "source": "teacher", "status": "approved"})
        return {k: r[k] for k in ("id", "status", "he", "scenario", "level", "decided")}

    def load_approved(self) -> int:
        """On startup: approved teacher items from the store join the corpus."""
        n = 0
        for r in self.store.submissions("approved"):
            if r["id"] not in self.content.by_id:
                self.content.add_approved({"id": r["id"], "kind": r["kind"], "he": r["he"], "ar": r["ar"],
                                           "transliteration": r["transliteration"], "level": r["level"],
                                           "scenario": r["scenario"], "pos": "teacher", "gender": None,
                                           "source": "teacher", "status": "approved"})
                n += 1
        return n


def strip_metadata(image: bytes) -> bytes:
    try:
        from PIL import Image as PILImage
    except ImportError:  # pragma: no cover
        raise ServiceError(501, "pillow-missing", "pip install pillow to accept images")
    img = PILImage.open(io.BytesIO(image))
    img = img.convert("RGB")
    if max(img.size) > 1568:  # Anthropic's recommended long edge: bigger only costs tokens
        s = 1568 / max(img.size)
        img = img.resize((round(img.width * s), round(img.height * s)))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)  # a fresh JPEG carries no EXIF unless we pass it
    return buf.getvalue()


__all__ = ["TutorService", "ServiceError", "strip_metadata", "render"]
