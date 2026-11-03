"""Milestone 3: rule_intent, the first stage of the intent router (mine.rule_intent)."""
import pytest

from _impl import mine


@pytest.mark.parametrize("text,intent", [
    ("I need a Figma editor seat for the new dashboards.", "access_request"),
    ("Please give me read access to Salesforce.", "access_request"),
    ("Grant me write access to the billing-service repo.", "access_request"),
    ("Can I get a Notion member account?", "access_request"),
    ("צריכה גישת עריכה ל-Figma בשביל העיצובים", "access_request"),
    ("אפשר לקבל הרשאת קריאה ל-Jira?", "access_request"),
    ("Who approves a Figma editor seat?", "knowledge"),
    ("How long does a security review take for admin access?", "knowledge"),
    ("What's the process to get access to aws-production?", "knowledge"),
    ("Do I need my manager's approval for a Notion account?", "knowledge"),
    ("מי מאשר הרשאת admin ב-GitHub?", "knowledge"),
    ("When is billing-service frozen for deploys?", "knowledge"),
    ("How many vacation days carry over to next year?", "knowledge"),
    ("What is Blue Room?", "knowledge"),
    ("How many open P1 tickets do we have right now?", "data"),
    ("How many people are on the Engine team?", "data"),
    ("Who currently has admin on aws-production?", "data"),
])
def test_clear_cases(text, intent):
    r = mine.rule_intent(text)
    assert r["intent"] == intent, (text, r)


def test_shape_and_confidences():
    r = mine.rule_intent("I need admin on GitHub")
    assert set(r) == {"intent", "confidence", "matched"}
    assert r == {"intent": "access_request", "confidence": 0.9, "matched": ["request"]}
    assert mine.rule_intent("Who approves Figma editor seats?") == {"intent": "knowledge", "confidence": 0.85,
                                                                  "matched": ["policy_question"]}
    assert mine.rule_intent("What is Blue Room?") == {"intent": "knowledge", "confidence": 0.6, "matched": ["default"]}


def test_unsure_cases_return_none():
    for text, label in [("figma editor for dana.levi@acme.example please", "access_word"),
                        ("Hi, Jira read access for the sprint reviews would be great", "access_word")]:
        r = mine.rule_intent(text)
        assert r["intent"] is None and r["confidence"] == 0.4 and r["matched"] == [label], (text, r)


def test_mixed_message_is_for_the_model():
    r = mine.rule_intent("What is the policy for Zendesk, and I need read access to it too")
    assert r["intent"] is None and r["confidence"] == 0.5
    assert r["matched"] == ["request", "policy_question"]


def test_empty_and_data_labels():
    assert mine.rule_intent("   ") == {"intent": None, "confidence": 0.0, "matched": []}
    r = mine.rule_intent("How many open P1 tickets do we have right now?")
    assert r["confidence"] == 0.8 and r["matched"] and all(m.startswith("data:") for m in r["matched"])
    assert mine.rule_intent("Who currently has admin on aws-production?")["matched"] == ["data_rule"]


def test_request_beats_data_words():
    # "how many" appears, but the employee asks for access: rule 3 comes before rule 6
    assert mine.rule_intent("I need read access to Zendesk to see how many tickets my customers have")["intent"] \
        == "access_request"
