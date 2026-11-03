"""hebtutor: the AI backend of a spoken-Hebrew practice app for Bedouin high-school students
(AI Engineer course, final project F2). See projects/f2-hebrew-tutor/README.md.

    content.py   scenarios, phrases, vocabulary (CEFR-tagged), retrieval (ragkit BM25), teacher submissions
    prompts.py   the tutor prompt (static rules first, for caching) and the request builder
    tutor.py     one turn: screen -> redact -> retrieve -> llmkit.structured Assessment -> validate; streaming
    safety.py    input/output screens for minors, LLM second opinion, redaction, kind replies
    rules.py     the offline rule-based baseline detector;  fakes.py: offline LLM stand-ins, record/replay
    validate.py  learner.py  speaking.py   references of the mine.py milestones
    voice.py     audio -> STT -> tutor (streamed sentences) -> TTS, with a timeline
    store.py     SQLite (minimal data, redacted text, retention purge);  service.py: the app layer
    api.py       FastAPI + SSE + the demo page;  evaluate.py: the eval;  config.py: settings and factories
"""

import sys
from pathlib import Path

# The course packages (llmkit, voicekit, ragkit, guardkit, obskit, evalkit, servekit) live at the repo root.
_ROOT = Path(__file__).resolve().parents[3]
if (_ROOT / "llmkit").is_dir() and str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

__version__ = "1.0.0"
