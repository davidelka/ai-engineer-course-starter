import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
ROOT = PROJECT.parents[1]
sys.path[:0] = [str(ROOT), str(PROJECT)]   # so tests can import cbrain (which adds the M1 project)

import cbrain  # noqa: E402,F401
