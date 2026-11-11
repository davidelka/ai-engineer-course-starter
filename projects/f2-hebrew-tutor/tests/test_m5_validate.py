"""M5: validate_assessment (mine.py). Code checks what the model returned."""

import pytest

from hebtutor.hooks import load_mine
from hebtutor.models import Assessment, Correction, VocabItem

mine = load_mine()
STUDENT = "אני מחפש את הבית ספר החדש."


def A(**kw):
    kw.setdefault("reply_he", "אה, את בית הספר החדש. איפה הוא?")
    return Assessment(**kw)


def C(original="הבית ספר", corrected="בית הספר", explanation_ar="في الإضافة نقول: בית הספר.", error_type="definiteness"):
    return Correction(original=original, corrected=corrected, explanation_ar=explanation_ar, error_type=error_type)


def codes(f):
    return {(x.code, x.severity) for x in f}


def test_good_assessment_passes_unchanged():
    a = A(correction=C(), new_vocabulary=[VocabItem(he="בית ספר", ar="مدرسة", transliteration="بيت سيفر")])
    out, f = mine.validate_assessment(a, STUDENT, level="A1")
    assert f == [] and out == a and out is not a


def test_does_not_modify_input():
    a = A(correction=C(original="ספר בית"))
    mine.validate_assessment(a, STUDENT)
    assert a.correction is not None and a.correction.original == "ספר בית"


def test_correction_not_grounded():
    out, f = mine.validate_assessment(A(correction=C(original="הבית הספר")), STUDENT)
    assert out.correction is None and ("correction_not_grounded", "block") in codes(f)


def test_grounding_ignores_niqqud_and_punctuation():
    out, f = mine.validate_assessment(A(correction=C(original="הַבֵּית סֵפֶר")), STUDENT)
    assert out.correction is not None and f == []


def test_noop_and_spelling_in_voice():
    out, f = mine.validate_assessment(A(correction=C(corrected="הבית ספר")), STUDENT)
    assert out.correction is None and ("correction_noop", "warn") in codes(f)
    s = "כואב לי הבתן"
    sp = C(original="הבתן", corrected="הבטן", error_type="spelling", explanation_ar="الكتابة الصحيحة הבטן.")
    out, f = mine.validate_assessment(A(correction=sp), s, mode="voice")
    assert out.correction is None and ("spelling_in_voice", "info") in codes(f)
    out, f = mine.validate_assessment(A(correction=sp), s, mode="text")
    assert out.correction is not None


def test_explanation_must_be_arabic_and_short():
    out, f = mine.validate_assessment(A(correction=C(explanation_ar="In a construct state the article goes on the second noun.")), STUDENT)
    assert ("explanation_not_arabic", "warn") in codes(f)
    assert "בית הספר" in out.correction.explanation_ar and "الإضافة" in out.correction.explanation_ar
    long = "هذه جملة طويلة جدا " * 15
    out, f = mine.validate_assessment(A(correction=C(explanation_ar=long)), STUDENT)
    assert ("explanation_too_long", "warn") in codes(f) and len(out.correction.explanation_ar) <= 161


def test_reply_not_hebrew_gets_fallback():
    out, f = mine.validate_assessment(A(reply_he="Great job! Where is the school?"), STUDENT, level="A2")
    assert ("reply_not_hebrew", "block") in codes(f)
    assert out.reply_he.startswith("סליחה") and "{" not in out.reply_he


def test_reply_too_long_is_cut_by_level():
    r = "מצוין. זה טוב. איפה הבית? מתי השיעור? מי המורה?"
    out, f = mine.validate_assessment(A(reply_he=r), STUDENT, level="A1")
    assert ("reply_too_long", "warn") in codes(f) and out.reply_he == "מצוין. זה טוב. איפה הבית?"
    out, f = mine.validate_assessment(A(reply_he=r), STUDENT, level="B1")
    assert f == []


def test_help_checks():
    out, f = mine.validate_assessment(A(help_ar="Say: שלום"), STUDENT)
    assert out.help_ar is None and ("help_not_arabic", "warn") in codes(f)
    out, f = mine.validate_assessment(A(help_ar="قل: " + "مرحبا بك " * 40), STUDENT)
    assert ("help_too_long", "warn") in codes(f) and len(out.help_ar) <= 221


def test_vocabulary_cleanup():
    v = [VocabItem(he="תור", ar="موعد", transliteration="تور"), VocabItem(he="תּוֹר", ar="دور", transliteration="تور"),
         VocabItem(he="doctor", ar="طبيب", transliteration=""), VocabItem(he="רופא", ar="doctor", transliteration=""),
         VocabItem(he="חום", ar="حرارة", transliteration="حوم"), VocabItem(he="כאב", ar="ألم", transliteration=""),
         VocabItem(he="ראש", ar="رأس", transliteration="")]
    out, f = mine.validate_assessment(A(new_vocabulary=v), STUDENT)
    assert [x.he for x in out.new_vocabulary] == ["תור", "חום", "כאב"]
    assert sum(1 for x in f if x.code == "vocab_dropped" and x.severity == "info") == 4


@pytest.mark.parametrize("screen,model,expected", [("distress", "none", "distress"), ("personal_info", "off_topic", "personal_info"),
                                                   ("off_topic", "unsafe", "unsafe"), ("none", "injection", "injection")])
def test_model_never_lowers_the_screen_flag(screen, model, expected):
    out, f = mine.validate_assessment(A(safety_flag=model), STUDENT, input_flag=screen)
    assert out.safety_flag == expected
    assert (("safety_downgrade", "block") in codes(f)) == (expected != model)
