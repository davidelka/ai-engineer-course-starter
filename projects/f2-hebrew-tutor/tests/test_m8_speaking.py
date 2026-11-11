"""M8: word_feedback (mine.py): intelligibility via ASR, word by word."""

from hebtutor.hooks import load_mine

mine = load_mine()


def st(fb):
    return [(w.word, w.status) for w in fb.words]


def test_perfect():
    fb = mine.word_feedback("כמה עולה כרטיס?", "כמה עולה כרטיס")
    assert st(fb) == [("כמה", "ok"), ("עולה", "ok"), ("כרטיס", "ok")] and fb.score == 1.0 and fb.missed == []


def test_p_said_as_b_is_close_with_a_hint():
    fb = mine.word_feedback("כמה פעמים ביום לקחת?", "כמה בעמים ביום לקחת")
    w = fb.words[1]
    assert (w.word, w.status, w.heard, w.cer, w.hint) == ("פעמים", "close", "בעמים", 0.2, "p_b")
    assert fb.score == 0.875


def test_homophone_spelling_is_the_recognizers():
    fb = mine.word_feedback("כואב לי הבטן", "כואב לי הבתן")
    assert fb.words[2].status == "homophone" and fb.score == 1.0


def test_missing_wrong_and_extra():
    fb = mine.word_feedback("אני צריך אישור יציאה", "אני רוצה אישור יציאה עכשיו")
    assert st(fb) == [("אני", "ok"), ("צריך", "wrong"), ("אישור", "ok"), ("יציאה", "ok")]
    assert fb.extra == ["עכשיו"] and fb.missed == ["צריך"]
    fb = mine.word_feedback("מתי הרופא מגיע", "מתי מגיע")
    assert [w.status for w in fb.words].count("missing") == 1 and fb.words[1].cer == 1.0


def test_v_said_as_f_and_final_letters_kept():
    fb = mine.word_feedback("אני רוצה לנסוע לתל אביב", "אני רוצה לנסוע לתל אפיב")
    assert fb.words[-1].hint == "v_f" and fb.words[-1].word == "אביב"
    assert mine.word_feedback("שלום", "שלום").words[0].word == "שלום"
