"""Exercise 5: contract drift between spec/openapi.yaml and the code's own OpenAPI."""

import copy
from pathlib import Path

import pytest

from mine import find_drift
from spectools.contract import load_contract

LAB = Path(__file__).resolve().parent.parent
CONTRACT = load_contract(LAB / "spec" / "openapi.yaml")


def kinds(drifts):
    return sorted((d.kind, d.where, d.detail.split(":")[0]) for d in drifts)


def doc(paths, schemas=None):
    return {"openapi": "3.1.0", "info": {"title": "t", "version": "1"}, "paths": paths,
            "components": {"schemas": schemas or {}}}


def op(responses=("200",), body=None, resp_schema=None):
    o = {"responses": {}}
    for code in responses:
        o["responses"][code] = {"description": "x"}
        if resp_schema is not None and code.startswith("2"):
            o["responses"][code]["content"] = {"application/json": {"schema": resp_schema}}
    if body is not None:
        o["requestBody"] = {"content": {"application/json": {"schema": body}}}
    return o


def test_identical_documents_have_no_drift():
    assert find_drift(CONTRACT, copy.deepcopy(CONTRACT)) == []


def test_operations_and_path_param_names():
    a = doc({"/items": {"get": op()}, "/items/{item_id}": {"get": op()}})
    b = doc({"/items/{id}": {"get": op()}, "/items/{id}/archive": {"post": op()}})
    assert kinds(find_drift(a, b)) == [
        ("missing-operation", "GET /items", ""),
        ("undocumented-operation", "POST /items/{}/archive", ""),
    ]


def test_status_codes_ignore_default():
    a = doc({"/x": {"get": op(("200", "404"))}})
    b = doc({"/x": {"get": op(("200", "422", "default"))}})
    assert kinds(find_drift(a, b)) == [("missing-status", "GET /x", "404"), ("undocumented-status", "GET /x", "422")]


def test_request_body_properties():
    a = doc({"/x": {"post": op(body={"type": "object", "properties": {"tool": {"type": "string"}, "note": {}}})}})
    b = doc({"/x": {"post": op(body={"type": "object", "properties": {"tool": {"type": "string"}, "extra": {}}})}})
    assert kinds(find_drift(a, b)) == [
        ("missing-property", "POST /x request body", "note"),
        ("undocumented-property", "POST /x request body", "extra"),
    ]


def test_enum_through_ref_nullable_and_const():
    contract = doc({"/x": {"get": op(resp_schema={"$ref": "#/components/schemas/Out"})}},
                   {"Out": {"type": "object", "properties": {
                       "status": {"$ref": "#/components/schemas/Status"},
                       "kind": {"type": "string", "enum": ["a"]}}},
                    "Status": {"type": "string", "enum": ["pending", "approved"]}})
    code = doc({"/x": {"get": op(resp_schema={"$ref": "#/components/schemas/AnyName"})}},
               {"AnyName": {"type": "object", "properties": {
                   "status": {"anyOf": [{"type": "string", "enum": ["pending", "granted"]}, {"type": "null"}]},
                   "kind": {"const": "a"}}}})
    d = find_drift(contract, code)
    assert kinds(d) == [("enum-mismatch", "GET /x 200 response", "status")]


def test_recurses_into_arrays_of_objects():
    item_c = {"type": "object", "properties": {"status": {"enum": ["pending", "approved"]}, "id": {}}}
    item_i = {"type": "object", "properties": {"status": {"enum": ["pending", "granted"]}}}
    a = doc({"/x": {"get": op(resp_schema={"type": "object", "properties": {"items": {"type": "array", "items": item_c}}})}})
    b = doc({"/x": {"get": op(resp_schema={"type": "object", "properties": {"items": {"type": "array", "items": item_i}}})}})
    assert kinds(find_drift(a, b)) == [
        ("enum-mismatch", "GET /x 200 response", "items[].status"),
        ("missing-property", "GET /x 200 response", "items[].id"),
    ]


def test_only_2xx_response_bodies_are_compared():
    a = doc({"/x": {"get": op(("200", "404"), resp_schema={"type": "object", "properties": {"a": {}}})}})
    b = copy.deepcopy(a)
    b["paths"]["/x"]["get"]["responses"]["404"]["content"] = {
        "application/json": {"schema": {"type": "object", "properties": {"detail": {}}}}}
    assert find_drift(a, b) == []


def test_reference_app_matches_the_contract():
    from reference.app import create_app
    assert find_drift(CONTRACT, create_app().openapi()) == []


@pytest.mark.parametrize("scenario,expected", [
    ("reject_route", {"undocumented-operation", "enum-mismatch"}),
    ("renamed_status", {"enum-mismatch"}),
    ("default_limit", set()),   # behavior drift: the contract diff cannot see it
    ("dropped_rule", set()),    # neither can it see this one
])
def test_drift_scenarios(scenario, expected):
    from drift.scenarios import build_app
    got = {d.kind for d in find_drift(CONTRACT, build_app(scenario).openapi())}
    assert got == expected
