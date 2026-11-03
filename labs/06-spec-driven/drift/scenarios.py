"""Spec drift on purpose: the code changes, the spec does not (exercise 5).

Each scenario is a small textual patch to reference/app.py or reference/routing.py, the kind
of change a developer (or an agent) makes in a hurry without touching the spec. The patched
module is built in memory; the files on disk never change.

    from drift.scenarios import SCENARIOS, build_app
    app = build_app("renamed_status")

Each scenario is also a factory for ACCESS_APP, so the acceptance tests can run against it:

    ACCESS_APP=drift.scenarios:renamed_status python -m pytest -q labs/06-spec-driven/acceptance
"""

from __future__ import annotations

import difflib
import importlib
import sys
import types
from dataclasses import dataclass, field
from pathlib import Path

LAB = Path(__file__).resolve().parent.parent
REF = LAB / "reference"


@dataclass
class Scenario:
    name: str
    story: str  # what the developer did, in one sentence
    app_patches: list[tuple[str, str]] = field(default_factory=list)
    routing_patches: list[tuple[str, str]] = field(default_factory=list)
    extra_tests: str = ""  # a test file the developer added with the change (or "")


SCENARIOS: dict[str, Scenario] = {s.name: s for s in [
    Scenario(
        "reject_route",
        "A developer added a reject endpoint and a 'rejected' status, plus a test for it, "
        "but did not touch the spec or the contract.",
        app_patches=[
            ('Status = Literal["pending", "approved"]', 'Status = Literal["pending", "approved", "rejected"]'),
            ("    return app\n",
             '    @app.post("/access-requests/{request_id}/reject", response_model=AccessRequest)\n'
             '    def reject(request_id: str, who: Caller = Depends(caller)):\n'
             '        item = store.get(request_id)\n'
             '        if item is None:\n'
             '            raise ApiError(404, "not_found", f"no access request {request_id}")\n'
             '        updated = store.update(request_id, status="rejected", decided_by=who.actor, decided_at=now())\n'
             '        log_change(request_id, who.actor, item["status"], "rejected")\n'
             '        return updated\n'
             "\n    return app\n"),
        ],
        extra_tests=(
            'import pytest\n\n\n'
            '@pytest.mark.req("REQ-12")\n'
            'def test_manager_rejects_request(client):\n'
            '    ...\n'),
    ),
    Scenario(
        "renamed_status",
        "A developer renamed the status 'approved' to 'granted' in the code, because the "
        "product team says 'granted' in the UI.",
        app_patches=[
            ('Status = Literal["pending", "approved"]', 'Status = Literal["pending", "granted"]'),
            ('"status": "approved" if auto else "pending"', '"status": "granted" if auto else "pending"'),
            ('status="approved", decided_by=who.actor', 'status="granted", decided_by=who.actor'),
            ('log_change(request_id, who.actor, "pending", "approved")',
             'log_change(request_id, who.actor, "pending", "granted")'),
        ],
    ),
    Scenario(
        "default_limit",
        "A developer raised the default page size from 20 to 50 because the UI wanted fewer pages.",
        app_patches=[("limit: int = Query(20, ge=1, le=100)", "limit: int = Query(50, ge=1, le=100)")],
    ),
    Scenario(
        "dropped_rule",
        "A developer removed Kubernetes from the sensitive-tools list while 'cleaning up' routing.py.",
        routing_patches=[('SENSITIVE_TOOLS = {"aws", "gcp", "kubernetes", "netsuite", "payroll"}',
                          'SENSITIVE_TOOLS = {"aws", "gcp", "netsuite", "payroll"}')],
    ),
]}


def _patched(path: Path, patches: list[tuple[str, str]]) -> str:
    src = path.read_text(encoding="utf-8")
    for old, new in patches:
        if src.count(old) != 1:
            raise RuntimeError(f"drift patch does not apply cleanly to {path.name}: {old[:60]!r}")
        src = src.replace(old, new)
    return src


def diff(name: str) -> str:
    """The scenario as a unified diff, like a code review would show it."""
    s = SCENARIOS[name]
    out = []
    for path, patches in ((REF / "app.py", s.app_patches), (REF / "routing.py", s.routing_patches)):
        if not patches:
            continue
        before = path.read_text(encoding="utf-8").splitlines(keepends=True)
        after = _patched(path, patches).splitlines(keepends=True)
        out += difflib.unified_diff(before, after, f"a/reference/{path.name}", f"b/reference/{path.name}", n=1)
    return "".join(out)


def _module(name: str, src: str, filename: str) -> types.ModuleType:
    importlib.import_module("reference")  # the package must exist for relative imports
    mod = types.ModuleType(name)
    mod.__package__ = "reference"
    mod.__file__ = filename
    sys.modules[name] = mod  # pydantic resolves the string annotations through sys.modules
    exec(compile(src, filename, "exec"), mod.__dict__)  # noqa: S102  (our own reviewed patch)
    return mod


def build_app(name: str):
    s = SCENARIOS[name]
    app_mod = _module(f"reference._drift_{name}", _patched(REF / "app.py", s.app_patches),
                      f"<drift {name}: reference/app.py>")
    if s.routing_patches:
        routing = _module(f"reference._drift_{name}_routing", _patched(REF / "routing.py", s.routing_patches),
                          f"<drift {name}: reference/routing.py>")
        app_mod.route_for = routing.route_for  # create() looks route_for up in the module at call time
    return app_mod.create_app()


def _factory(name: str):
    def factory():
        return build_app(name)
    factory.__name__ = name
    return factory


for _n in SCENARIOS:
    globals()[_n] = _factory(_n)
