import os
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
ROOT = PROJECT.parents[1]
sys.path[:0] = [str(ROOT), str(PROJECT)]  # so tests can `import mine`, `import pss`, `import ragkit`
os.environ.setdefault("PSS_HOME", tempfile.mkdtemp(prefix="pss-home-"))
