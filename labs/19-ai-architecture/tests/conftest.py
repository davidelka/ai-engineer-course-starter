import sys
from pathlib import Path

import pytest

LAB = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(LAB))  # so tests can `import mine`

from archkit import load_spec  # noqa: E402


@pytest.fixture(scope="session")
def company_brain():
    return load_spec(LAB / "specs" / "company_brain.arch.yaml")


def mini_spec(components, flows, boundaries=None):
    """A small spec for unit tests. Boundaries: user (untrusted), vpc (trusted),
    prov_a and prov_b (third_party)."""
    return load_spec({
        "system": "mini",
        "boundaries": boundaries or [
            {"id": "user", "name": "User", "trust": "untrusted"},
            {"id": "vpc", "name": "VPC", "trust": "trusted"},
            {"id": "prov_a", "name": "Provider A", "trust": "third_party"},
            {"id": "prov_b", "name": "Provider B", "trust": "third_party"},
        ],
        "components": components,
        "flows": flows,
    })
