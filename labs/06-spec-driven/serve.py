"""Run an implementation on http://127.0.0.1:8000 so you can try it with curl.

    python labs/06-spec-driven/serve.py --app reference
    python labs/06-spec-driven/serve.py --app impl

    curl -s -X POST localhost:8000/access-requests -H 'X-Actor: dana@acme.example' -H 'X-Role: employee' \\
         -H 'content-type: application/json' -d '{"tool":"Jira","access_level":"read","justification":"sprint board please"}'
    curl -s localhost:8000/access-requests -H 'X-Actor: dana@acme.example' -H 'X-Role: employee'
    open http://127.0.0.1:8000/docs     # FastAPI's own docs: the app's view of itself, not the contract
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
sys.path[:0] = [str(LAB.parents[1]), str(LAB)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", default="reference")
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args()
    import uvicorn  # in labs/06-spec-driven/requirements.txt
    from grade import load_app
    uvicorn.run(load_app(a.app), host="127.0.0.1", port=a.port)


if __name__ == "__main__":
    main()
