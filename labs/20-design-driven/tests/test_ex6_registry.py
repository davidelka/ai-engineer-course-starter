"""Exercise 6: prompt/schema registry with version pins and a compatibility check.
The prompt history used here is in prompts_catalog.py (read its docstring)."""

import pytest

import mine
import prompts_catalog as pc
from designkit.types import PromptVersion


def schema(model):
    return model.model_json_schema()


# ---------------------------------------------------------------- check_compatible
def test_identical_and_additive_changes_are_compatible():
    assert mine.check_compatible(schema(pc.OutV1), schema(pc.OutV1)) == []
    assert mine.check_compatible(schema(pc.OutV1), schema(pc.OutV1_1)) == []  # new optional field
    assert mine.check_compatible(None, schema(pc.OutV1)) == []


def test_new_enum_value_is_breaking():
    out = mine.check_compatible(schema(pc.OutV1_1), schema(pc.OutPartial))
    assert len(out) == 1 and out[0].startswith("breaking:") and "'status'" in out[0] and "partial" in out[0]


def test_fewer_enum_values_is_fine():
    assert mine.check_compatible(schema(pc.OutPartial), schema(pc.OutV1_1)) == []


def test_removed_required_field_is_breaking():
    out = mine.check_compatible(schema(pc.OutPartial), schema(pc.OutRenamed))
    assert any("'citations'" in m for m in out)
    assert not any("'sources'" in m for m in out), "a NEW field is not breaking"


def test_removed_optional_field_is_fine():
    assert mine.check_compatible(schema(pc.OutV1_1), schema(pc.OutV1)) == []


def test_now_nullable_is_breaking():
    out = mine.check_compatible(schema(pc.OutV1), schema(pc.OutNullableText))
    assert len(out) == 1 and "'text'" in out[0] and "null" in out[0]


def test_required_to_optional_and_enum_to_free_text():
    old = {"properties": {"route": {"type": "string", "enum": ["a", "b"]}}, "required": ["route"]}
    new = {"properties": {"route": {"type": "string"}}, "required": []}
    out = mine.check_compatible(old, new)
    assert len(out) == 2 and all("'route'" in m for m in out)


def test_type_widening_via_list_and_anyof():
    old = {"properties": {"n": {"type": "integer"}}, "required": ["n"]}
    assert mine.check_compatible(old, {"properties": {"n": {"type": ["integer", "string"]}}, "required": ["n"]})
    assert mine.check_compatible(old, {"properties": {"n": {"anyOf": [{"type": "integer"}, {"type": "number"}]}},
                                       "required": ["n"]})
    narrower = {"properties": {"n": {"anyOf": [{"type": "integer"}, {"type": "null"}]}}, "required": ["n"]}
    assert mine.check_compatible(narrower, old) == []


def test_schema_removed():
    out = mine.check_compatible(schema(pc.OutV1), None)
    assert out and out[0].startswith("breaking:")


# ---------------------------------------------------------------- registry
def registry_with_history():
    r = mine.PromptRegistry()
    for p in (pc.V1_0_0, pc.V1_0_1, pc.V1_1_0, pc.V2_0_0):
        r.register(p)
    return r


def test_pins():
    r = registry_with_history()
    assert r.get("answer", "1").version == "1.1.0"
    assert r.get("answer", "1.0").version == "1.0.1"
    assert r.get("answer", "1.0.0").version == "1.0.0"
    assert r.get("answer", "latest").version == "2.0.0"
    assert r.get("answer").version == "2.0.0"
    assert r.versions("answer") == ["1.0.0", "1.0.1", "1.1.0", "2.0.0"]


def test_versions_compare_as_numbers():
    r = mine.PromptRegistry()
    for v in ("1.9.0", "1.10.0", "1.2.0"):
        r.register(PromptVersion(name="p", version=v, template=v))
    assert r.get("p", "1").version == "1.10.0"
    assert r.versions("p") == ["1.2.0", "1.9.0", "1.10.0"]


def test_missing_raises_key_error():
    r = registry_with_history()
    with pytest.raises(KeyError):
        r.get("answer", "3")
    with pytest.raises(KeyError):
        r.get("nope")


def test_breaking_change_needs_a_new_major():
    r = registry_with_history()
    r2 = mine.PromptRegistry()
    for p in (pc.V1_0_0, pc.V1_1_0):
        r2.register(p)
    with pytest.raises(mine.IncompatibleVersion) as e:
        r2.register(pc.V1_2_0_BAD)
    assert "status" in str(e.value)
    with pytest.raises(mine.IncompatibleVersion):
        r.register(pc.V2_1_0_BAD)
    assert r.get("answer", "2").version == "2.0.0", "a refused version must not be registered"


def test_versions_are_immutable_but_registration_is_idempotent():
    r = registry_with_history()
    r.register(pc.V1_0_1)  # the identical object again: fine
    changed = PromptVersion(name="answer", version="1.0.1", template="something else",
                            output_schema=pc.V1_0_1.output_schema)
    with pytest.raises(ValueError):
        r.register(changed)


def test_bad_version_string():
    with pytest.raises(ValueError):
        mine.PromptRegistry().register(PromptVersion(name="p", version="v2", template="t"))
