import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent.parent
ROOT = LAB.parents[1]
sys.path[:0] = [str(ROOT), str(LAB)]  # so tests can `import mine` and `import deploykit`
