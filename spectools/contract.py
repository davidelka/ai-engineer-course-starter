"""Interface contracts (OpenAPI 3.1): loading, diffing for drift, and validating live traffic.

- `find_drift(contract, implemented)` compares the contract file with the OpenAPI document
  the implementation generates about itself (FastAPI's app.openapi()). Reference for
  exercise 5. It catches what a contract TEST cannot: operations the code added without a
  spec, and enum values renamed in code.
- `ContractClient` wraps Starlette's TestClient and validates every request and response
  against the contract with openapi-core, so every example-based test is also a contract test.
- `contract_schema(path, app)` loads the contract with Schemathesis and binds it to an ASGI
  app, so generated requests run in-process against the CONTRACT (not against the app's own
  generated schema, which would always agree with the app).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Union

import yaml

METHODS = ("get", "put", "post", "delete", "patch", "head", "options")


def load_contract(path: Union[str, Path]) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def normalize_path(path: str) -> str:
    """'/a/{request_id}/b' -> '/a/{}/b': parameter names are not part of the interface."""
    return re.sub(r"\{[^}]*\}", "{}", path)


def operations(doc: dict) -> dict[tuple[str, str], dict]:
    """{("POST", "/access-requests/{}/approve"): <operation object>, ...}"""
    out = {}
    for path, item in (doc.get("paths") or {}).items():
        for method, op in item.items():
            if method.lower() in METHODS and isinstance(op, dict):
                out[(method.upper(), normalize_path(path))] = op
    return out


def resolve(doc: dict, node: Any, _depth: int = 0) -> Any:
    """Follow local $ref pointers ('#/components/schemas/X') until a non-ref node."""
    while isinstance(node, dict) and "$ref" in node and _depth < 50:
        ref = node["$ref"]
        if not ref.startswith("#/"):
            raise ValueError(f"only local $ref is supported, got {ref}")
        target: Any = doc
        for part in ref[2:].split("/"):
            target = target[part.replace("~1", "/").replace("~0", "~")]
        node, _depth = target, _depth + 1
    return node


def unwrap(doc: dict, schema: Any) -> dict:
    """Resolve $ref and drop a nullable wrapper: anyOf/oneOf [X, {type: null}] -> X."""
    schema = resolve(doc, schema) or {}
    for key in ("anyOf", "oneOf"):
        if key in schema:
            options = [resolve(doc, o) for o in schema[key]]
            non_null = [o for o in options if o.get("type") != "null"]
            if len(non_null) == 1:
                return unwrap(doc, non_null[0])
    return schema


def enum_values(doc: dict, schema: Any) -> Optional[set]:
    """The allowed values of an enum-like schema, or None if it is not one.
    Handles enum, const (pydantic writes a one-value Literal as const), $ref and nullable wrappers.
    null is not counted as a value."""
    s = unwrap(doc, schema)
    if "enum" in s:
        return {v for v in s["enum"] if v is not None}
    if "const" in s:
        return {s["const"]}
    return None


def json_body_schema(doc: dict, holder: Optional[dict]) -> Optional[dict]:
    """The application/json schema of a requestBody or response object, resolved, or None."""
    holder = resolve(doc, holder) if holder else None
    if not holder:
        return None
    content = holder.get("content") or {}
    media = content.get("application/json")
    return resolve(doc, media["schema"]) if media and "schema" in media else None


@dataclass(frozen=True)
class Drift:
    kind: str  # missing-operation | undocumented-operation | missing-status | undocumented-status
    #            missing-property | undocumented-property | enum-mismatch
    where: str  # "POST /access-requests/{}" or "POST /access-requests 201 response" or "... request body"
    detail: str = ""  # status code, property path, or the enum difference

    def __str__(self) -> str:
        return f"{self.kind:<22} {self.where}" + (f"  [{self.detail}]" if self.detail else "")


def _object_props(doc: dict, schema: Any) -> Optional[dict]:
    s = unwrap(doc, schema)
    return s.get("properties") if isinstance(s.get("properties"), dict) else None


def _compare_schemas(doc_c: dict, sc: Any, doc_i: dict, si: Any, where: str, prefix: str, depth: int) -> list[Drift]:
    out: list[Drift] = []
    if depth > 5:
        return out
    pc, pi = _object_props(doc_c, sc), _object_props(doc_i, si)
    if pc is None or pi is None:
        return out
    for name in pc:
        if name not in pi:
            out.append(Drift("missing-property", where, prefix + name))
    for name in pi:
        if name not in pc:
            out.append(Drift("undocumented-property", where, prefix + name))
    for name in pc:
        if name not in pi:
            continue
        ec, ei = enum_values(doc_c, pc[name]), enum_values(doc_i, pi[name])
        if ec is not None and ei is not None and ec != ei:
            out.append(Drift("enum-mismatch", where, f"{prefix}{name}: contract {sorted(map(str, ec))} "
                                                     f"vs code {sorted(map(str, ei))}"))
        uc, ui = unwrap(doc_c, pc[name]), unwrap(doc_i, pi[name])
        if uc.get("type") == "array" and ui.get("type") == "array":
            out += _compare_schemas(doc_c, uc.get("items", {}), doc_i, ui.get("items", {}), where,
                                    f"{prefix}{name}[].", depth + 1)
        else:
            out += _compare_schemas(doc_c, uc, doc_i, ui, where, f"{prefix}{name}.", depth + 1)
    return out


def find_drift(contract: dict, implemented: dict) -> list[Drift]:
    out: list[Drift] = []
    oc, oi = operations(contract), operations(implemented)
    for key in oc:
        if key not in oi:
            out.append(Drift("missing-operation", f"{key[0]} {key[1]}"))
    for key in oi:
        if key not in oc:
            out.append(Drift("undocumented-operation", f"{key[0]} {key[1]}"))
    for key in oc:
        if key not in oi:
            continue
        where = f"{key[0]} {key[1]}"
        rc = {str(k) for k in (oc[key].get("responses") or {}) if str(k) != "default"}
        ri = {str(k) for k in (oi[key].get("responses") or {}) if str(k) != "default"}
        out += [Drift("missing-status", where, s) for s in sorted(rc - ri)]
        out += [Drift("undocumented-status", where, s) for s in sorted(ri - rc)]
        bc = json_body_schema(contract, oc[key].get("requestBody"))
        bi = json_body_schema(implemented, oi[key].get("requestBody"))
        if bc is not None and bi is not None:
            out += _compare_schemas(contract, bc, implemented, bi, f"{where} request body", "", 0)
        for status in sorted(rc & ri):
            if not status.startswith("2"):
                continue
            sc = json_body_schema(contract, oc[key]["responses"][_key(oc[key]["responses"], status)])
            si = json_body_schema(implemented, oi[key]["responses"][_key(oi[key]["responses"], status)])
            if sc is not None and si is not None:
                out += _compare_schemas(contract, sc, implemented, si, f"{where} {status} response", "", 0)
    return out


def _key(responses: dict, status: str):
    return next(k for k in responses if str(k) == status)


# ------------------------------------------------------------------ openapi-core: validate traffic
class ContractViolation(AssertionError):
    pass


class ContractClient:
    """A TestClient-like wrapper: every call is validated against the contract.

        client = ContractClient(app, "spec/openapi.yaml")
        r = client.post("/access-requests", json=body, headers=H)   # raises ContractViolation on drift

    Request validation runs only for requests the test MEANT to be valid (expect_valid_request);
    tests that send bad input on purpose still get their response validated.
    """

    def __init__(self, app, contract_path: Union[str, Path]):
        from fastapi.testclient import TestClient
        from openapi_core import OpenAPI

        self.http = TestClient(app, raise_server_exceptions=False)
        self.openapi = OpenAPI.from_file_path(str(contract_path))
        self.checked = 0

    def request(self, method: str, url: str, *, expect_valid_request: bool = False, **kw):
        from openapi_core.testing import MockRequest, MockResponse

        resp = self.http.request(method, url, **kw)
        req = resp.request
        body = req.content or None
        mreq = MockRequest("http://testserver", method.lower(), req.url.path,
                           args=dict(req.url.params), headers=dict(req.headers),
                           data=body, content_type=req.headers.get("content-type", "application/json"))
        if expect_valid_request:
            try:
                self.openapi.validate_request(mreq)
            except Exception as exc:  # noqa: BLE001
                raise ContractViolation(f"request does not match the contract: {exc}") from None
        mresp = MockResponse(resp.content, status_code=resp.status_code, headers=dict(resp.headers),
                             content_type=resp.headers.get("content-type", "application/json").split(";")[0])
        try:
            self.openapi.validate_response(mreq, mresp)
        except Exception as exc:  # noqa: BLE001
            detail = getattr(exc, "__cause__", None) or exc
            raise ContractViolation(
                f"{method.upper()} {req.url.path} -> {resp.status_code} breaks the contract: {detail}\n"
                f"body: {resp.text[:300]}") from None
        self.checked += 1
        return resp

    def get(self, url: str, **kw):
        return self.request("GET", url, **kw)

    def post(self, url: str, **kw):
        return self.request("POST", url, **kw)


# ------------------------------------------------------------------ schemathesis
def contract_schema(contract_path: Union[str, Path], app):
    """Schemathesis schema loaded from the contract FILE and bound to an in-process ASGI app.

    schemathesis.openapi.from_asgi() would load the app's own /openapi.json, so it can only
    find bugs the app admits to. Loading the file and setting .app (which is what from_asgi
    does internally in Schemathesis 4.x) tests the app against the spec instead.
    """
    import schemathesis

    schema = schemathesis.openapi.from_path(str(contract_path))
    schema.app = app
    return schema


def dump(doc: dict) -> str:
    return json.dumps(doc, indent=2, ensure_ascii=False)
