"""Exercise 6: compaction of a long conversation under a token budget."""

import copy

from llmkit import Message
from conftest import words
from mine import compact


def convo(n_pairs=6, filler=8):
    msgs = []
    for i in range(n_pairs):
        msgs += [Message("user", f"u{i} " + "w " * filler), Message("assistant", f"a{i} " + "w " * filler)]
    msgs.append(Message("user", "final question here"))
    return msgs


class Spy:
    def __init__(self, text="SUMMARY"):
        self.calls, self.text = [], text

    def __call__(self, old):
        self.calls.append(list(old))
        return self.text


def size(msgs):
    return sum(words(m.text) for m in msgs)


def test_fits_already_returns_a_copy_without_summarizing():
    msgs, spy = convo(2), Spy()
    out = compact(msgs, 10_000, words, spy)
    assert out == msgs and out is not msgs and spy.calls == []


def test_summarizes_old_and_keeps_recent_verbatim():
    msgs, spy = convo(6), Spy()
    before = copy.deepcopy(msgs)
    out = compact(msgs, 60, words, spy, keep_last=3)
    assert msgs == before, "do not modify the input"
    assert spy.calls == [msgs[:-3]]
    assert out[0].role == "user"
    assert out[0].text == "<conversation_summary>\nSUMMARY\n</conversation_summary>\n\n" + msgs[-3].text
    assert out[1:] == msgs[-2:]


def test_recent_part_must_start_with_a_user_message():
    msgs, spy = convo(6), Spy()
    out = compact(msgs, 60, words, spy, keep_last=4)  # last 4 starts with an assistant: take 5
    assert spy.calls == [msgs[:-5]]
    assert len(out) == 5 and out[1:] == msgs[-4:]
    assert [m.role for m in out] == ["user", "assistant", "user", "assistant", "user"]


def test_shrinks_keep_last_until_it_fits():
    msgs, spy = convo(6), Spy()
    out = compact(msgs, 30, words, spy, keep_last=5)  # 5 messages (~30 words) + summary does not fit
    assert size(out) <= 30
    assert len(spy.calls) >= 2 and len(spy.calls[-1]) > len(spy.calls[0])
    assert out[-1] == msgs[-1]


def test_gives_up_at_one_message():
    msgs, spy = convo(6), Spy("a very long summary " * 20)
    out = compact(msgs, 5, words, spy, keep_last=3)
    assert len(out) == 1 and out[0].role == "user" and out[0].text.endswith("final question here")


def test_compacting_again_feeds_the_old_summary_back():
    msgs, spy = convo(6), Spy("FIRST")
    once = compact(msgs, 60, words, spy, keep_last=3)
    longer = once + [Message("assistant", "more " * 10), Message("user", "next " * 10)]
    spy2 = Spy("SECOND")
    twice = compact(longer, 40, words, spy2, keep_last=1)
    assert any("FIRST" in m.text for m in spy2.calls[0])
    assert twice[0].text.startswith("<conversation_summary>\nSECOND\n")
