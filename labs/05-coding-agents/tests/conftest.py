import os
import shutil
import sys
from pathlib import Path

import pytest

LAB = Path(__file__).resolve().parent.parent
REPO = LAB.parent.parent
sys.path.insert(0, str(REPO))  # repoguard
sys.path.insert(0, str(LAB))  # so tests can `import mine`


@pytest.fixture
def project(tmp_path):
    """A fresh copy of sample-service with a fake .env and a .claude/ folder."""
    proj = tmp_path / "project"
    shutil.copytree(LAB / "sample-service", proj, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    (proj / ".env").write_text("ACME_ADMIN_TOKEN=lab-fake-token-7f3a9c\n")
    (proj / ".claude" / "hooks").mkdir(parents=True)
    (proj / ".claude" / "settings.json").write_text("{}\n")
    return str(proj)


os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
