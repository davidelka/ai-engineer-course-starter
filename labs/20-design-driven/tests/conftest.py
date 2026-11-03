import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent.parent
ROOT = LAB.parents[1]
sys.path[:0] = [str(LAB), str(ROOT)]  # so tests can `import mine`, `import prompts_catalog`, `import designkit`
