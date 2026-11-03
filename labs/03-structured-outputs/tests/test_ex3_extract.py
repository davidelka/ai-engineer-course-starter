"""Exercise 3: find the JSON object in a model reply."""

import json

import pytest

from mine import extract_json


@pytest.mark.parametrize("text,expected", [
    ('{"a": 1}', {"a": 1}),
    ('```json\n{"a": 1}\n```', {"a": 1}),
    ('```\n{"a": 1}\n```', {"a": 1}),
    ('Sure! Here it is:\n{"a": 1}\nHope this helps.', {"a": 1}),
    ('{"a": {"b": {"c": 2}}, "d": [1, 2]}', {"a": {"b": {"c": 2}}, "d": [1, 2]}),
    ('{"a": "use {x} here"}', {"a": "use {x} here"}),
    ('{"a": "a quote \\" and a } brace"}', {"a": 'a quote " and a } brace'}),
    ('Result: {"a": 1} and also {"b": 2}', {"a": 1}),
    ('  \n{"name": "רוני"}  ', {"name": "רוני"}),
])
def test_finds_the_object(text, expected):
    assert json.loads(extract_json(text)) == expected


@pytest.mark.parametrize("text", ["no json here", "", "[1, 2, 3]"])
def test_no_object_raises(text):
    with pytest.raises(ValueError):
        extract_json(text)


def test_truncated_raises():
    with pytest.raises(ValueError):
        extract_json('{"a": 1, "b": {"c": ')
