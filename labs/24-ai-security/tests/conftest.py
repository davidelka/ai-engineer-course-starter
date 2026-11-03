import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent.parent
REPO = LAB.parents[1]
sys.path.insert(0, str(LAB))  # so tests can `import mine`
if str(REPO) not in sys.path:
    sys.path.insert(1, str(REPO))  # guardkit, llmkit
