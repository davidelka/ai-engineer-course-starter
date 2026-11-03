"""Exercise 3: the traceability matrix."""

from pathlib import Path

from mine import build_matrix, scan_req_markers
from spectools.spec import parse_spec

HERE = Path(__file__).resolve().parent
SAMPLE = HERE / "fixtures" / "sample_tests"

EXPECTED = {
    "REQ-1": ["test_plain.py::test_one", "test_plain.py::test_two"],
    "REQ-2": ["test_plain.py::test_two"],
    "REQ-3": ["test_plain.py::test_from_import"],
    "REQ-4": ["test_plain.py::TestGroup::test_a", "test_plain.py::TestGroup::test_b"],
    "REQ-5": ["test_plain.py::TestGroup::test_b"],
    "REQ-6": ["sub/test_module_mark.py::test_c", "sub/test_module_mark.py::test_d"],
    "REQ-99": ["sub/test_module_mark.py::test_d"],
}


def test_scan_directory():
    assert scan_req_markers([SAMPLE]) == EXPECTED


def test_scan_single_file_uses_its_name():
    got = scan_req_markers([SAMPLE / "sub" / "test_module_mark.py"])
    assert got == {"REQ-6": ["test_module_mark.py::test_c", "test_module_mark.py::test_d"],
                   "REQ-99": ["test_module_mark.py::test_d"]}


def test_scan_several_paths_merges_and_dedupes():
    got = scan_req_markers([SAMPLE, SAMPLE])
    assert got == EXPECTED


def test_scan_accepts_strings(tmp_path):
    (tmp_path / "test_s.py").write_text('import pytest\n\n@pytest.mark.req("REQ-1")\nasync def test_async():\n    pass\n')
    assert scan_req_markers([str(tmp_path)]) == {"REQ-1": ["test_s.py::test_async"]}


SPEC = parse_spec("""# T

## 3. Requirements

### REQ-1: One
**Statement:** THE SYSTEM SHALL do one.

### REQ-2: Two
**Statement:** THE SYSTEM SHALL do two.

### REQ-7: Seven
**Statement:** THE SYSTEM SHALL do seven.

## 4. Non-functional requirements

### NFR-1: Latency
**Statement:** THE SYSTEM SHALL answer in 50 ms.
""")


def test_build_matrix():
    m = build_matrix(SPEC, {"REQ-2": ["b.py::t2", "a.py::t1"], "REQ-1": ["a.py::t1"], "REQ-42": ["z.py::t", "y.py::t"],
                            "NFR-1": ["n.py::t"], "REQ-10": ["c.py::t"]})
    assert [(r.req_id, r.title, r.tests) for r in m.rows] == [
        ("REQ-1", "One", ["a.py::t1"]),
        ("REQ-2", "Two", ["a.py::t1", "b.py::t2"]),
        ("REQ-7", "Seven", []),
        ("NFR-1", "Latency", ["n.py::t"]),
    ]
    assert m.uncovered == ["REQ-7"]
    assert m.orphans == {"REQ-10": ["c.py::t"], "REQ-42": ["y.py::t", "z.py::t"]}
    assert list(m.orphans) == ["REQ-10", "REQ-42"]
    assert all(r.results == {} for r in m.rows)


def test_matrix_for_the_sample_against_a_small_spec():
    m = build_matrix(SPEC, scan_req_markers([SAMPLE]))
    assert m.uncovered == ["REQ-7", "NFR-1"]
    assert set(m.orphans) == {"REQ-3", "REQ-4", "REQ-5", "REQ-6", "REQ-99"}
