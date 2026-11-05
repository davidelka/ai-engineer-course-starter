"""Your code for lesson 6. Each part is checked by tests in ./tests.

spectools/ (lint.py, trace.py, contract.py) has reference versions.
Try not to peek before your tests pass.

    python -m pytest -q labs/06-spec-driven/tests
"""

from __future__ import annotations

import ast  # noqa: F401  (exercise 3)
import re  # noqa: F401
from pathlib import Path  # noqa: F401
from typing import Iterable, Union

from spectools.contract import (  # noqa: F401  (helpers for exercise 5)
    Drift, enum_values, json_body_schema, normalize_path, operations, resolve, unwrap,
)
from spectools.lint import VAGUE_WORDS, WEAK_MODALS, Finding  # noqa: F401
from spectools.spec import Spec
from spectools.trace import Matrix, Row  # noqa: F401


# ------------------------------------------------------------------ exercise 2
def lint_spec(spec: Spec) -> list[Finding]:
    """Check every requirement in a parsed spec. Return one Finding per problem.

    spec.requirements: Requirement(id, title, kind, statement, criteria, line) in file order;
    criteria: Criterion(id, text, line). See spectools/spec.py.
    Finding(rule, req_id, message, severity): req_id is the requirement's id (None if it has
    none); severity is "error" for every rule except weak-modal ("warning"). Rules:
      missing-id          the heading has no REQ-<n>/NFR-<n> id
      duplicate-id        the id was used by an earlier requirement (report the later one)
      missing-statement   empty statement (then no other statement rule applies)
      not-ears            no SHALL, or not starting with THE/WHEN/WHILE/IF/WHERE + space
      weak-modal          one per WEAK_MODALS word in the statement; message '"should" in statement'
      vague-word          one per VAGUE_WORDS word in the statement and in each criterion;
                          message '"quickly" in statement' or '"some" in AC-5.1'
      nfr-not-measurable  a non-functional requirement whose statement has no digit
      no-criteria         no acceptance criteria
      criterion-not-gwt   a criterion without GIVEN, WHEN, THEN in that order
    All matching ignores case. Words match whole words only: "fast" matches "Fast." but not
    "breakfast"; multi-word entries such as "as needed" count as one word.

    Stuck? HINTS.md -> lint_spec
    """
    # TODO(ex2)
    raise NotImplementedError("exercise 2: implement lint_spec")


# ------------------------------------------------------------------ exercise 3
def scan_req_markers(paths: Iterable[Union[str, Path]]) -> dict[str, list[str]]:
    """Find which tests point at which requirement, by reading test files (no imports).

    paths: files or directories; in a directory, test_*.py and *_test.py, recursively.
    Returns {"REQ-4": ["test_routing.py::test_admin", "sub/test_x.py::TestA::test_b"], ...},
    each list sorted and without duplicates. Node ids are "<file>::<function>" or
    "<file>::<Class>::<method>"; <file> is relative to the directory passed (posix slashes),
    or just the file name for a file passed directly.
    Markers that count (several ids allowed in one marker, stacked markers combine):
      @pytest.mark.req("REQ-1", ...) or @mark.req(...) on a module-level test* function;
      the same on a class Test*, applying to each of its test* methods;
      a module-level pytestmark = pytest.mark.req(...) or a list/tuple containing one,
      applying to every test in the file.
    Other markers, non-test functions and non-Test classes are ignored.

    Stuck? HINTS.md -> scan_req_markers
    """
    # TODO(ex3)
    raise NotImplementedError("exercise 3: implement scan_req_markers")


def build_matrix(spec: Spec, markers: dict[str, list[str]]) -> Matrix:
    """Requirement -> tests, plus the two kinds of gap.

    Returns a Matrix with:
      rows:      one Row(req_id, title, tests) per id in spec.ids() (spec order, first
                 occurrence), tests sorted, results left empty;
      uncovered: spec ids with no test, in spec order;
      orphans:   {id: sorted tests} for ids that tests mention but the spec lacks, keys sorted.

    Stuck? HINTS.md -> build_matrix
    """
    # TODO(ex3)
    raise NotImplementedError("exercise 3: implement build_matrix")


# ------------------------------------------------------------------ exercise 5
def find_drift(contract: dict, implemented: dict) -> list[Drift]:
    """Compare two OpenAPI 3.1 documents: the contract file and what the code says about itself.

    Returns Drift(kind, where, detail) items. Paths are compared with their parameters
    normalized ("/a/{}"); each document resolves its own $refs.
      missing-operation       in the contract, not in the code; where="POST /a/{}"
      undocumented-operation  in the code, not in the contract
    For each operation in both, where = "<METHOD> <normalized path>":
      missing-status          a response code in the contract, not in the code; detail="404"
      undocumented-status     a response code in the code, not in the contract ("default" ignored)
    For the application/json request body and each 2xx response code in both,
    where = "<METHOD> <path> request body" or "<METHOD> <path> <code> response":
      missing-property        in the contract's object schema, not in the code's
      undocumented-property   the other way round
      enum-mismatch           a property in both with different enum sets; detail starts
                              with the property path, e.g. "status: ..."
      Nested properties present on both sides are compared too, objects and arrays of
      objects ("items[].status"), down to depth 5.
    spectools/contract.py (imported above) has helpers for the OpenAPI plumbing.

    Stuck? HINTS.md -> find_drift
    """
    # TODO(ex5)
    raise NotImplementedError("exercise 5: implement find_drift")
