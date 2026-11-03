import sys
from pathlib import Path

import pytest

LAB = Path(__file__).resolve().parent.parent
ROOT = LAB.parents[1]
sys.path[:0] = [str(ROOT), str(LAB)]  # so tests can `import mine` and `import datakit`

from datakit import connect_ro, load_layer, policy_from_layer  # noqa: E402


@pytest.fixture(scope="session")
def layer():
    return load_layer()  # the reference semantic layer: datakit/data/acme_semantic.yaml


@pytest.fixture(scope="session")
def policy(layer):
    return policy_from_layer(layer)


@pytest.fixture
def con():
    c = connect_ro()  # data/acme/corpus/structured/acme.db, read-only
    yield c
    c.close()
