"""cbrain: Company Brain, the course's final project F1.

One service that answers questions over Acme's knowledge (phase 2, the M1 package `acmeqa`,
imported, not copied), runs the access-request approval workflow (phase 3, `flowkit` on
LangGraph with human approval gates), and is secured, observed, evaluated and deployable
(phase 4: guardkit, obskit, evalkit, gatewaykit, archkit, deploykit).

    from cbrain.brain import Brain
    brain = Brain.from_env()                       # offline by default: free, no key
    brain.ask("How many vacation days carry over?", user="dana")
    rid = brain.requests.start(brain.users["dana"], "I need a Figma editor seat").thread_id
    brain.requests.decide(rid, brain.users["michal"], "approve", "ok")

Modules
    config.py      BrainSettings from the environment (MODE, LLM_PATH, STATE_DIR, ...)
    auth.py        users, roles (employee, manager, security, admin) and API keys
    models.py      the model factories: offline fakes, mockllm, live Haiku, the obedient simulation
    gateway.py     gatewaykit in front of every model call ("production" config) + GatewayLLM
    guards.py      guardkit layers around the knowledge path, and the data classification
    router.py      the intent router: knowledge / data / access_request (rules + structured output)
    knowledge.py   GuardedKnowledge: acmeqa.Assistant with the guard layers composed around it
    workflow.py    AccessRequests: flowkit's graph, SQLite checkpoints, approvals inbox, audit
    brain.py       Brain: the facade the API, the MCP server and the evaluation all call
    obs.py         tracing setup, SLO report and cost per request type (obskit)
    mcp_server.py  Company Brain as an MCP server (mcpkit tools + brain tools, same users)
    service.py     the FastAPI app and the single-page Hebrew UI (ui/index.html)
    evaluate.py    the unified evaluation: knowledge, routing, workflow, security, cost
    hooks.py       your mine.py functions (loaded as module "f1_mine"), or the references
    seed.py        demo data for a fresh deployment

Importing cbrain puts the repo root and the M1 project on sys.path, so `acmeqa`, `flowkit`,
`guardkit` and the rest import the same way here, in the tests and in the container.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
ROOT = PROJECT.parents[1] if (PROJECT.parents[1] / "llmkit").is_dir() else PROJECT.parent
M1 = ROOT / "projects" / "m1-knowledge-assistant"

for _p in (ROOT, M1):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.append(str(_p))

__version__ = "1.0.0"
