"""M4: build_request and partial_json_field (mine.py). The prompt, and the reply decoded while it streams."""

import json

from hebtutor.content import Content
from hebtutor.hooks import load_mine
from hebtutor.models import SessionState
from hebtutor.prompts import STATIC_RULES, session_block, user_turn

mine = load_mine()
RET = [{"he": "כמה עולה כרטיס?", "ar": "كم سعر التذكرة؟"}]


def test_system_blocks_and_cache():
    c = Content()
    st = SessionState("bus_station", "A2", "f", turn_index=3)
    req = mine.build_request(c, st, "אני רוצה כרטיס", RET, mode="voice", max_tokens=321)
    assert [b.text for b in req.system] == [STATIC_RULES, session_block(c.scenarios["bus_station"], st, "voice")]
    assert req.system[0].cache == "5m" and req.system[1].cache is None
    assert req.max_tokens == 321
    assert mine.build_request(c, st, "x", RET, cache=False).system[0].cache is None


def test_history_window_and_turn():
    c = Content()
    hist = [("student" if i % 2 == 0 else "tutor", f"t{i}") for i in range(12)]
    st = SessionState("bus_station", "A1", "m", history=hist)
    req = mine.build_request(c, st, "אני רוצה כרטיס", RET)
    assert [m.role for m in req.messages[:-1]] == ["user", "assistant"] * 4
    assert [m.text for m in req.messages[:-1]] == [f"t{i}" for i in range(4, 12)]
    assert req.messages[-1].role == "user" and req.messages[-1].text == user_turn("אני רוצה כרטיס", RET)


FULL = json.dumps({"help_ar": "", "reply_he": 'שלום "נועה"\nמה\tשלומך? א', "safety_flag": "none"}, ensure_ascii=True)


def test_complete_field():
    assert mine.partial_json_field(FULL) == ('שלום "נועה"\nמה\tשלומך? א', True)


def test_every_prefix_is_a_prefix_of_the_answer():
    whole, _ = mine.partial_json_field(FULL)
    prev = ""
    for i in range(len(FULL) + 1):
        val, done = mine.partial_json_field(FULL[:i])
        assert whole.startswith(val) and val.startswith(prev)        # never decodes half an escape
        prev = val
    assert done is True


def test_not_started_and_other_field():
    assert mine.partial_json_field('{"help_ar": "x", "reply') == ("", False)
    assert mine.partial_json_field('{"reply_he"') == ("", False)
    assert mine.partial_json_field('{"reply_he": ') == ("", False)
    assert mine.partial_json_field('{"a": "b", "x": "yz"}', "x") == ("yz", True)
