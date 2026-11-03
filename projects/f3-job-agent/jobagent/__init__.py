"""jobagent: the owner's job-alert agent, production edition (final project F3).

    sources -> dedup -> safety screen -> structured extraction -> validation -> matching
            -> digest -> delivery + Gmail drafts, with a SQLite state store, schedules,
            tracing, an eval harness, an admin API and deployment files.

Run `python -m jobagent --help` from projects/f3-job-agent/.
"""

import sys
from pathlib import Path

# The course packages (llmkit, obskit, guardkit, evalkit, deploykit) live at the repo root.
_ROOT = Path(__file__).resolve().parents[3]
if (_ROOT / "llmkit").is_dir() and str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

__version__ = "1.0.0"
