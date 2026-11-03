"""M6: redact_for_log (mine.py). Students are minors: PII never reaches the model or the store."""

import pytest

from hebtutor.hooks import load_mine

mine = load_mine()


@pytest.mark.parametrize("text,expected,kinds", [
    ("הטלפון שלי 050-7654321", "הטלפון שלי [טלפון]", ["phone"]),
    ("תתקשרי 0507654321 או 08-6234567", "תתקשרי [טלפון] או [טלפון]", ["phone"]),
    ("my number +972-50-1234567", "my number [טלפון]", ["phone"]),
    ("כתבו לי ל-salem.k@gmail.com", "כתבו לי ל-[מייל]", ["email"]),
    ("תיכנס ל https://evil.example/x?y=1 עכשיו", "תיכנס ל [קישור] עכשיו", ["url"]),
    ("ת\"ז 123456782", "ת\"ז [ת״ז]", ["id_number"]),
    ("המספר 123456789 לא תעודת זהות", "המספר 123456789 לא תעודת זהות", []),
    ("אני גרה ברחוב הנרקיס 12 בבאר שבע", "אני גרה [כתובת] בבאר שבע", ["address"]),
    ("انا ساكن في شارع الجامع 7", "انا ساكن في [כתובת]", ["address"]),
])
def test_patterns(text, expected, kinds):
    assert mine.redact_for_log(text) == (expected, kinds)


def test_full_name_but_not_first_name():
    out, k = mine.redact_for_log("קוראים לי מרים אבו סעיד ואני בכיתה י")
    assert out == "קוראים לי [שם] ואני בכיתה י" and k == ["full_name"]
    out, k = mine.redact_for_log("اسمي احمد الهزيل")
    assert out == "اسمي [שם]" and k == ["full_name"]
    assert mine.redact_for_log("קוראים לי סאלם ואני בן 16") == ("קוראים לי סאלם ואני בן 16", [])
    assert mine.redact_for_log("שמי נור") == ("שמי נור", [])


def test_several_kinds_sorted_and_plain_text_untouched():
    out, k = mine.redact_for_log("קוראים לי מרים אבו סעיד, הטלפון 050-7654321")
    assert k == ["full_name", "phone"] and "050" not in out and "סעיד" not in out
    assert mine.redact_for_log("כואב לי הראש כבר שלושה ימים") == ("כואב לי הראש כבר שלושה ימים", [])
