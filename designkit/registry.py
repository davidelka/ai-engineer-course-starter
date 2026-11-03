"""Reference prompt/schema registry (exercise 6).

Prompts and output schemas are versioned like a library: MAJOR.MINOR.PATCH.
Callers pin a version ("1" = newest 1.x.y), so a new prompt never reaches them
by surprise, and a change that would break the code reading the output must
come as a new MAJOR. The compatibility check is from the CONSUMER's side: the
model produces the JSON, our code reads it.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from .types import PromptVersion

SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


class IncompatibleVersion(ValueError):
    """A breaking schema change was registered without a new MAJOR version."""


def parse_version(v: str) -> tuple[int, int, int]:
    m = SEMVER.match(v)
    if not m:
        raise ValueError(f"version must be MAJOR.MINOR.PATCH, got {v!r}")
    return int(m[1]), int(m[2]), int(m[3])


# ---------------------------------------------------------------- compatibility
def _types(prop: dict[str, Any]) -> set[str]:
    if "anyOf" in prop:
        return set().union(*(_types(p) for p in prop["anyOf"]))
    if "$ref" in prop:
        return {"object"}
    t = prop.get("type")
    if isinstance(t, list):
        return set(t)
    if t:
        return {t}
    if "enum" in prop:
        return {type(v).__name__.replace("str", "string").replace("NoneType", "null") for v in prop["enum"]}
    return {"any"}


def _enum(prop: dict[str, Any]) -> Optional[set]:
    if "enum" in prop:
        return set(prop["enum"])
    if "const" in prop:
        return {prop["const"]}
    if "anyOf" in prop:
        vals = [_enum(p) for p in prop["anyOf"] if _types(p) != {"null"}]
        if vals and all(v is not None for v in vals):
            return set().union(*vals)
    return None


def check_compatible(old: Optional[dict], new: Optional[dict]) -> list[str]:
    """Breaking changes for code that reads output written against `old`.

    Breaking: a required field removed; a required field no longer required; a field
    that can now hold a new type (e.g. null); a new enum value; an enum that
    became free text; the whole schema removed. NOT breaking: new fields,
    removing an optional field, narrower types, fewer enum values. Each message starts with "breaking:".
    """
    if old is None:
        return []
    if new is None:
        return ["breaking: the output schema was removed"]
    out: list[str] = []
    old_props, new_props = old.get("properties", {}), new.get("properties", {})
    old_req, new_req = set(old.get("required", [])), set(new.get("required", []))
    for name, op in old_props.items():
        if name not in new_props:
            if name in old_req:  # an optional field could always be missing: readers already cope
                out.append(f"breaking: removed field '{name}'")
            continue
        np_ = new_props[name]
        if name in old_req and name not in new_req:
            out.append(f"breaking: field '{name}' is no longer required (it may be missing)")
        added = _types(np_) - _types(op)
        if added and "any" not in _types(op):
            out.append(f"breaking: field '{name}' can now be {', '.join(sorted(added))}")
        oe, ne = _enum(op), _enum(np_)
        if oe is not None and ne is None and not added:
            out.append(f"breaking: field '{name}' is no longer restricted to {sorted(map(str, oe))}")
        elif oe is not None and ne is not None and ne - oe:
            out.append(f"breaking: field '{name}' has new values {sorted(map(str, ne - oe))}")
    return out


# ---------------------------------------------------------------- registry
class PromptRegistry:
    def __init__(self):
        self._items: dict[str, dict[str, PromptVersion]] = {}

    def versions(self, name: str) -> list[str]:
        return sorted(self._items.get(name, {}), key=parse_version)

    def register(self, pv: PromptVersion) -> None:
        key = parse_version(pv.version)
        same = self._items.setdefault(pv.name, {})
        if pv.version in same:
            if same[pv.version].fingerprint != pv.fingerprint:
                raise ValueError(f"{pv.ref} already exists with different content: versions are immutable, "
                                 "publish a new version instead")
            return  # registering the identical thing again is a no-op (idempotent)
        older = [v for v in same.values() if parse_version(v.version)[0] == key[0] and parse_version(v.version) < key]
        if older:
            prev = max(older, key=lambda v: parse_version(v.version))
            problems = check_compatible(prev.output_schema, pv.output_schema)
            if problems:
                raise IncompatibleVersion(f"{pv.ref} breaks {prev.ref}; publish it as {key[0] + 1}.0.0. "
                                          + "; ".join(problems))
        same[pv.version] = pv

    def get(self, name: str, pin: str = "latest") -> PromptVersion:
        """pin: "latest", "1" (newest 1.x.y), "1.2" (newest 1.2.x) or "1.2.3" (exact)."""
        items = self._items.get(name)
        if not items:
            raise KeyError(f"no prompt named {name!r}")
        if pin == "latest":
            cands = list(items.values())
        else:
            if not re.fullmatch(r"\d+(\.\d+){0,2}", pin):
                raise ValueError(f"bad pin {pin!r}: use latest, 1, 1.2 or 1.2.3")
            want = tuple(int(x) for x in pin.split("."))
            cands = [v for v in items.values() if parse_version(v.version)[: len(want)] == want]
        if not cands:
            raise KeyError(f"no version of {name!r} matches pin {pin!r}; have {self.versions(name)}")
        return max(cands, key=lambda v: parse_version(v.version))
