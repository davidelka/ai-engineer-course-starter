"""Reference tamper guard. Exercise 4 in lesson 7 asks you to write your own in mine.py.

A loop that verifies with tests the generator can edit has a weak oracle: the cheapest
way to make "the tests pass" is often to change the tests. This guard compares the
pristine tests with the candidate's tests (and looks at the solution for hard-coded
test inputs) and reports what it finds as short strings "kind:location".
"""

from __future__ import annotations

import ast
from pathlib import PurePosixPath
from typing import Optional

SKIP_NAMES = {"skip", "skipif", "xfail"}


def is_test_path(path: str) -> bool:
    name = PurePosixPath(path).name
    return name.endswith(".py") and (name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py")


def _dotted(node: ast.AST) -> str:
    """'pytest.mark.skip' for an Attribute chain, '' for anything else."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return ""


def _is_skip_expr(node: ast.AST) -> bool:
    """True for pytest.mark.skip / skipif / xfail (called or not), and pytest.skip(...) / pytest.xfail(...)."""
    target = node.func if isinstance(node, ast.Call) else node
    name = _dotted(target)
    if not name:
        return False
    last = name.split(".")[-1]
    return last in SKIP_NAMES and ("mark" in name.split(".") or name.startswith("pytest."))


def _is_trivial_assert(node: ast.Assert) -> bool:
    t = node.test
    if isinstance(t, ast.Constant):
        return bool(t.value)
    if isinstance(t, ast.Compare) and len(t.ops) == 1 and isinstance(t.ops[0], (ast.Eq, ast.Is)):
        return ast.dump(t.left) == ast.dump(t.comparators[0])
    return False


def _test_functions(tree: ast.Module) -> dict[str, ast.FunctionDef]:
    out: dict[str, ast.FunctionDef] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
            out[node.name] = node
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) and sub.name.startswith("test"):
                    out[f"{node.name}::{sub.name}"] = sub
    return out


def _checks(fn: ast.FunctionDef) -> int:
    """Non-trivial assert statements plus `with pytest.raises(...)` blocks."""
    n = 0
    for node in ast.walk(fn):
        if isinstance(node, ast.Assert) and not _is_trivial_assert(node):
            n += 1
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                ce = item.context_expr
                if isinstance(ce, ast.Call) and _dotted(ce.func).endswith("raises"):
                    n += 1
    return n


def _skips_in(fn: ast.FunctionDef) -> bool:
    if any(_is_skip_expr(d) for d in fn.decorator_list):
        return True
    return any(isinstance(n, ast.Call) and _is_skip_expr(n) and _dotted(n.func).startswith("pytest.")
               and "mark" not in _dotted(n.func) for n in ast.walk(fn))


def _module_skip(tree: ast.Module) -> bool:
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "pytestmark" for t in node.targets):
            if any(_is_skip_expr(n) for n in ast.walk(node.value)):
                return True
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and _is_skip_expr(node.value):
            return True
    return False


def literal_test_inputs(original: dict[str, str]) -> set[str]:
    """String literals (3+ chars) inside the arguments of calls in the original test functions,
    including parametrize lists: these are the inputs a cheating solution would hard-code."""
    found: set[str] = set()
    for path, text in original.items():
        if not is_test_path(path):
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        for fn in _test_functions(tree).values():
            for node in ast.walk(fn):
                if isinstance(node, ast.Call):
                    for arg in list(node.args) + [k.value for k in node.keywords]:
                        for sub in ast.walk(arg):
                            if isinstance(sub, ast.Constant) and isinstance(sub.value, str) and len(sub.value.strip()) >= 3:
                                found.add(sub.value)
    return found


def special_cases(source: str, inputs: set[str]) -> list[str]:
    """Test inputs that the solution compares against (==, !=, in) or uses as dict keys."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    hits: set[str] = set()

    def lit(n: ast.AST) -> Optional[str]:
        return n.value if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value in inputs else None

    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            for side in [node.left, *node.comparators]:
                if (v := lit(side)) is not None:
                    hits.add(v)
                if isinstance(side, (ast.Tuple, ast.List, ast.Set)):
                    hits.update(v for e in side.elts if (v := lit(e)) is not None)
        elif isinstance(node, ast.Dict):
            hits.update(v for k in node.keys if k is not None and (v := lit(k)) is not None)
    return sorted(hits)


def find_tampering(original: dict[str, str], candidate: dict[str, str], source: Optional[str] = None,
                   spec: str = "") -> list[str]:
    """Compare pristine test files with the candidate's files. Returns sorted unique findings:

        deleted_file:<path>            a pristine test file is gone
        new_conftest:<path>            a conftest.py appeared (it can patch anything)
        unparsable_test:<path>         a test file no longer parses
        removed_test:<path>::<name>    a pristine test function is gone
        skip_marker:<path>::<name>     a skip/skipif/xfail marker or pytest.skip() call was added
        skip_marker:<path>::*          module-level pytestmark skip, or pytest.skip at module level
        modified_test:<path>::<name>   the test's code changed in any way (decorators included)
        trivial_assert:<path>::<name>  `assert True`, `assert 1`, `assert x == x` in a test
        weakened_test:<path>::<name>   fewer real checks (asserts + pytest.raises) than before
        special_case:<literal>         the solution compares against a literal test input
                                       (literals that also appear in the spec are allowed)
    A test can get several findings: `assert True` in place of a real assert is
    trivial_assert + weakened_test + modified_test.
    """
    findings: set[str] = set()
    for path in original:
        if is_test_path(path) and path not in candidate:
            findings.add(f"deleted_file:{path}")
    for path, text in candidate.items():
        if not is_test_path(path):
            continue
        if PurePosixPath(path).name == "conftest.py" and path not in original:
            findings.add(f"new_conftest:{path}")
        try:
            new_tree = ast.parse(text)
        except SyntaxError:
            findings.add(f"unparsable_test:{path}")
            continue
        old_tree = None
        if path in original:
            try:
                old_tree = ast.parse(original[path])
            except SyntaxError:
                old_tree = None
        old_fns = _test_functions(old_tree) if old_tree else {}
        new_fns = _test_functions(new_tree)
        if _module_skip(new_tree) and not (old_tree and _module_skip(old_tree)):
            findings.add(f"skip_marker:{path}::*")
        for name in old_fns:
            if name not in new_fns:
                findings.add(f"removed_test:{path}::{name}")
        for name, fn in new_fns.items():
            old = old_fns.get(name)
            if _skips_in(fn) and not (old and _skips_in(old)):
                findings.add(f"skip_marker:{path}::{name}")
            if any(isinstance(n, ast.Assert) and _is_trivial_assert(n) for n in ast.walk(fn)):
                findings.add(f"trivial_assert:{path}::{name}")
            if old is not None and _checks(fn) < _checks(old):
                findings.add(f"weakened_test:{path}::{name}")
            if old is not None and ast.dump(fn) != ast.dump(old):
                findings.add(f"modified_test:{path}::{name}")
    if source:
        allowed = spec.lower()
        findings.update(f"special_case:{v}" for v in special_cases(source, literal_test_inputs(original))
                        if v.lower() not in allowed)
    return sorted(findings)
