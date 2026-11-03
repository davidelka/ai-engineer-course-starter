import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(LAB), str(LAB.parents[1])]  # so tests can `import mine` and `import loopkit`

FIXTURES = Path(__file__).resolve().parent / "fixtures"
TASKS = LAB / "tasks"
