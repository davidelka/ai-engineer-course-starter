"""Traceability: requirement -> tests -> result. Reference for exercise 3 of lesson 6.

Tests point at requirements with a pytest marker:

    @pytest.mark.req("REQ-4")
    def test_admin_goes_to_security(client): ...

    @pytest.mark.req("REQ-8", "REQ-11")        # one test can cover several requirements
    class TestApprove:                          # a class marker applies to every test method
        def test_manager_approves(self, client): ...

    pytestmark = pytest.mark.req("NFR-2")       # a module marker applies to every test in the file

The scan is static (ast), so it needs no imports and no running app. The production
alternative is a small pytest plugin that reads item.iter_markers("req") during collection;
the static scan gives the same answer for these forms and is easier to test.
"""

from __future__ import annotations

import ast
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional, Union

from .spec import Spec


def _req_ids_from_marker(node: ast.AST) -> list[str]:
    """`pytest.mark.req("A", "B")` or `mark.req("A")` -> ["A", "B"]; anything else -> []."""
    if not isinstance(node, ast.Call):
        return []
    f = node.func
    if not (isinstance(f, ast.Attribute) and f.attr == "req"):
        return []
    owner = f.value
    is_mark = (isinstance(owner, ast.Attribute) and owner.attr == "mark") or (
        isinstance(owner, ast.Name) and owner.id == "mark")
    if not is_mark:
        return []
    return [a.value for a in node.args if isinstance(a, ast.Constant) and isinstance(a.value, str)]


def _module_ids(tree: ast.Module) -> list[str]:
    ids: list[str] = []
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "pytestmark" for t in stmt.targets):
            values = stmt.value.elts if isinstance(stmt.value, (ast.List, ast.Tuple)) else [stmt.value]
            for v in values:
                ids += _req_ids_from_marker(v)
    return ids


def _test_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    files = list(root.rglob("test_*.py")) + list(root.rglob("*_test.py"))
    return sorted(set(f for f in files if "__pycache__" not in f.parts))


def scan_req_markers(paths: Iterable[Union[str, Path]]) -> dict[str, list[str]]:
    out: dict[str, set[str]] = {}

    def add(ids: list[str], node_id: str) -> None:
        for i in ids:
            out.setdefault(i, set()).add(node_id)

    for p in paths:
        root = Path(p)
        for f in _test_files(root):
            rel = f.name if root.is_file() else f.relative_to(root).as_posix()
            tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
            mod = _module_ids(tree)
            for stmt in tree.body:
                if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and stmt.name.startswith("test"):
                    ids = mod + [i for d in stmt.decorator_list for i in _req_ids_from_marker(d)]
                    add(ids, f"{rel}::{stmt.name}")
                elif isinstance(stmt, ast.ClassDef) and stmt.name.startswith("Test"):
                    cls = [i for d in stmt.decorator_list for i in _req_ids_from_marker(d)]
                    for m in stmt.body:
                        if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and m.name.startswith("test"):
                            ids = mod + cls + [i for d in m.decorator_list for i in _req_ids_from_marker(d)]
                            add(ids, f"{rel}::{stmt.name}::{m.name}")
    return {k: sorted(v) for k, v in out.items()}


@dataclass
class Row:
    req_id: str
    title: str
    tests: list[str]
    results: dict[str, str] = field(default_factory=dict)  # test -> "passed" | "failed" | "skipped" | "not run"

    @property
    def status(self) -> str:
        """UNTESTED (no test), FAILING (a test failed), NOT RUN (no results), PASSING."""
        if not self.tests:
            return "UNTESTED"
        if not self.results:
            return "NOT RUN"
        vals = [self.results.get(t, "not run") for t in self.tests]
        if any(v == "failed" for v in vals):
            return "FAILING"
        if any(v == "passed" for v in vals):
            return "PASSING"
        return "NOT RUN"


@dataclass
class Matrix:
    rows: list[Row]
    uncovered: list[str]
    orphans: dict[str, list[str]]


def build_matrix(spec: Spec, markers: dict[str, list[str]]) -> Matrix:
    rows = []
    for rid in spec.ids():
        req = spec.get(rid)
        rows.append(Row(rid, req.title if req else "", sorted(markers.get(rid, []))))
    known = set(spec.ids())
    return Matrix(rows=rows, uncovered=[r.req_id for r in rows if not r.tests],
                  orphans={k: sorted(v) for k, v in sorted(markers.items()) if k not in known})


# ------------------------------------------------------------------ results from a pytest run
def junit_results(xml_path: Union[str, Path], prefix: str = "") -> dict[str, str]:
    """Map 'file.py::Class::test' -> outcome, from `pytest --junitxml`.

    pytest writes classname="acceptance.test_api.TestApprove" name="test_x[param]". We keep
    the last module part plus the class, so keys look like the ones scan_req_markers makes.
    Parametrized cases are folded: a test fails if any of its cases failed.
    """
    out: dict[str, str] = {}
    rank = {"failed": 3, "passed": 2, "skipped": 1}
    for tc in ET.parse(xml_path).getroot().iter("testcase"):
        parts = (tc.get("classname") or "").split(".")
        name = (tc.get("name") or "").split("[")[0]
        # find the module part (test_*.py) and anything after it is a class
        is_mod = [p.startswith("test_") or p.endswith("_test") for p in parts]
        idx = max((i for i, m in enumerate(is_mod) if m), default=len(parts) - 1)
        mod = "/".join(parts[: idx + 1])
        key = f"{prefix}{mod}.py" + "".join(f"::{c}" for c in parts[idx + 1:]) + f"::{name}"
        if tc.find("failure") is not None or tc.find("error") is not None:
            outcome = "failed"
        elif tc.find("skipped") is not None:
            outcome = "skipped"
        else:
            outcome = "passed"
        if rank[outcome] > rank.get(out.get(key, ""), 0):
            out[key] = outcome
    return out


def attach_results(matrix: Matrix, results: dict[str, str]) -> Matrix:
    """Match each row's tests to results by suffix (results may carry a longer path)."""
    for row in matrix.rows:
        for t in row.tests:
            hit = next((v for k, v in results.items() if k == t or k.endswith("/" + t)), None)
            row.results[t] = hit or "not run"
    return matrix


def render(matrix: Matrix, show_tests: bool = True) -> str:
    lines = []
    for row in matrix.rows:
        lines.append(f"{row.req_id:<7} {row.status:<9} {row.title}")
        if show_tests:
            for t in row.tests:
                r = row.results.get(t)
                lines.append(f"          {'' if r is None else f'[{r}] '}{t}")
    if matrix.uncovered:
        lines.append(f"\nUNTESTED requirements: {', '.join(matrix.uncovered)}")
    if matrix.orphans:
        lines.append("\nOrphan markers (a test points at a requirement that is not in the spec):")
        for k, v in matrix.orphans.items():
            lines.append(f"  {k}: {', '.join(v)}")
    return "\n".join(lines)


def summary(matrix: Matrix) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in matrix.rows:
        out[r.status] = out.get(r.status, 0) + 1
    return out


def find_test(matrix: Matrix, req_id: str) -> Optional[Row]:
    return next((r for r in matrix.rows if r.req_id == req_id), None)
