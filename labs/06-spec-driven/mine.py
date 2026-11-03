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

    spec.requirements is a list of Requirement(id, title, kind, statement, criteria, line),
    in file order; criteria is a list of Criterion(id, text, line). See spectools/spec.py.

    Rules (Finding(rule, req_id, message, severity)); req_id is the requirement's id or None:
      missing-id          the heading has no REQ-<n>/NFR-<n> id (req_id=None)
      duplicate-id        the id was already used by an earlier requirement (report the later one)
      missing-statement   statement is empty
      not-ears            statement does not contain the word SHALL (any case), OR does not start
                          with one of: THE, WHEN, WHILE, IF, WHERE (any case, followed by a space)
      weak-modal          one Finding per word from WEAK_MODALS found in the statement,
                          severity "warning"; the message names the word, e.g. '"should" in statement'
      vague-word          one Finding per word from VAGUE_WORDS found in the statement, and one per
                          word per criterion; the message names the word and where, e.g.
                          '"quickly" in statement' or '"some" in AC-5.1'
      nfr-not-measurable  kind == "non-functional" and the statement has no digit
      no-criteria         no acceptance criteria
      criterion-not-gwt   a criterion without the words GIVEN, WHEN, THEN in that order (any case)

    Word matching is case-insensitive and on word boundaries: "fast" matches "Fast." but not
    "breakfast"; "user-friendly" and "as needed" are single entries. Only check the statement
    of a requirement that has one. All severities are "error" except weak-modal.
    """
    # TODO(ex2)
    raise NotImplementedError("exercise 2: implement lint_spec")


# ------------------------------------------------------------------ exercise 3
def scan_req_markers(paths: Iterable[Union[str, Path]]) -> dict[str, list[str]]:
    """Find which tests point at which requirement, by reading test files (no imports).

    paths: files or directories. In a directory, scan test_*.py and *_test.py recursively.
    Return {"REQ-4": ["test_routing.py::test_admin", "sub/test_x.py::TestA::test_b"], ...}
    with each list sorted and without duplicates.

    Node ids: "<file>::<function>" or "<file>::<Class>::<method>", where <file> is the path
    relative to the directory that was passed (posix slashes), or just the file name when a
    file was passed directly.

    Recognize (use the ast module):
      @pytest.mark.req("REQ-1")                  on a module-level function named test*
      @pytest.mark.req("REQ-1", "REQ-2")         several ids in one marker
      @mark.req("REQ-1")                         after `from pytest import mark`
      @pytest.mark.req(...) on a class Test*     applies to every test* method in it
      pytestmark = pytest.mark.req("REQ-9")      module level, applies to every test in the file
      pytestmark = [pytest.mark.req("REQ-9"), pytest.mark.slow]   (a list or tuple)
    Ignore other markers (parametrize, skip...), functions not named test*, and classes not
    named Test*. Stacked decorators combine.
    """
    # TODO(ex3)
    raise NotImplementedError("exercise 3: implement scan_req_markers")


def build_matrix(spec: Spec, markers: dict[str, list[str]]) -> Matrix:
    """Requirement -> tests, plus the two kinds of gap.

    rows:      one Row(req_id, title, tests) per id in spec.ids() (spec order, first occurrence),
               tests sorted; results stays empty
    uncovered: ids from the spec with no test, in spec order
    orphans:   {id: sorted tests} for ids that tests mention but the spec does not contain,
               keys sorted
    """
    # TODO(ex3)
    raise NotImplementedError("exercise 3: implement build_matrix")


# ------------------------------------------------------------------ exercise 5
def find_drift(contract: dict, implemented: dict) -> list[Drift]:
    """Compare two OpenAPI 3.1 documents: the contract file and what the code says about itself.

    Return Drift(kind, where, detail) items:
      missing-operation       (method, path) in the contract, not in the code. where="POST /a/{}"
      undocumented-operation  in the code, not in the contract
      For every operation in both, with where = "<METHOD> <normalized path>":
      missing-status          a response code in the contract, not in the code. detail="404"
      undocumented-status     a response code in the code, not in the contract ("default" ignored)
      For the application/json request body, and for every 2xx response code in both:
        where = "<METHOD> <path> request body"  or  "<METHOD> <path> <code> response"
      missing-property        a property in the contract's object schema, not in the code's
      undocumented-property   the other way round
      enum-mismatch           a property in both whose enum sets differ;
                              detail starts with the property path, e.g. "status: ..."
      Recurse into properties that exist on both sides: into objects, and into arrays of
      objects with "[]" in the path: "items[].status". Stop after depth 5.

    Helpers you can use (spectools/contract.py):
      operations(doc)          {("POST", "/access-requests/{}"): op}; path params normalized
      json_body_schema(doc, x) the resolved application/json schema of a requestBody/response
      unwrap(doc, schema)      resolves $ref and drops a nullable anyOf/oneOf wrapper
      enum_values(doc, schema) set of allowed values (enum or const), or None
    Each document resolves its own $refs: contract refs against `contract`, code refs against
    `implemented`.
    """
    # TODO(ex5)
    raise NotImplementedError("exercise 5: implement find_drift")
