"""ADR lint (lesson 19): structural checks for an Architecture Decision Record.

The template (labs/19-ai-architecture/adr/TEMPLATE.md) follows Michael Nygard's
original format (context, decision, status, consequences) with additions from
MADR (decision drivers, considered options, confirmation) and one section that
AI systems need: cost and latency, with numbers.

The lint checks STRUCTURE only: that the sections exist and carry the minimum
content. Whether the reasoning is good is what the rubric and the critique
(archkit.critique) are for.
"""

from __future__ import annotations

import re

from .rules import Finding

REQUIRED = [
    "context and problem statement",
    "decision drivers",
    "considered options",
    "decision outcome",
    "consequences",
    "cost and latency",
    "confirmation",
]
STATUSES = ("proposed", "accepted", "rejected", "deprecated", "superseded")


def sections(text: str) -> dict[str, str]:
    """'## Heading' -> body (up to the next '## '). Keys are lowercased."""
    out: dict[str, str] = {}
    cur = None
    buf: list[str] = []
    for line in text.splitlines():
        m = re.match(r"^##\s+(?!#)(.+?)\s*$", line)
        if m:
            if cur is not None:
                out[cur] = "\n".join(buf).strip()
            cur, buf = m.group(1).strip().lower(), []
        elif cur is not None:
            buf.append(line)
    if cur is not None:
        out[cur] = "\n".join(buf).strip()
    return out


def subsections(body: str) -> dict[str, str]:
    out: dict[str, str] = {}
    cur = None
    buf: list[str] = []
    for line in body.splitlines():
        m = re.match(r"^###\s+(.+?)\s*$", line)
        if m:
            if cur is not None:
                out[cur] = "\n".join(buf).strip()
            cur, buf = m.group(1).strip(), []
        elif cur is not None:
            buf.append(line)
    if cur is not None:
        out[cur] = "\n".join(buf).strip()
    return out


def bullets(body: str) -> list[str]:
    return [ln.strip()[2:].strip() for ln in body.splitlines() if re.match(r"^\s*[-*]\s+\S", ln)]


def _real(body: str) -> str:
    """Drop HTML comments (template guidance) before checking content."""
    return re.sub(r"<!--.*?-->", "", body, flags=re.S).strip()


def lint_adr(text: str) -> list[Finding]:
    out: list[Finding] = []
    R = "adr"

    def err(where, msg):
        out.append(Finding(R, "error", where, msg))

    def warn(where, msg):
        out.append(Finding(R, "warning", where, msg))

    first = next((ln for ln in text.splitlines() if ln.strip()), "")
    if not re.match(r"^#\s+ADR-\d{4}:\s+\S", first):
        err("title", 'first line must look like "# ADR-0001: Short decision title"')
    m = re.search(r"^\s*[-*]?\s*Status:\s*(\w+)", text, flags=re.M | re.I)
    if not m or m.group(1).lower() not in STATUSES:
        err("status", f"a 'Status:' line with one of: {', '.join(STATUSES)}")

    secs = {k: _real(v) for k, v in sections(text).items()}
    for name in REQUIRED:
        if name not in secs:
            err(name, f"missing section '## {name.capitalize()}'")
        elif not secs[name]:
            err(name, "section is empty")

    ctx = secs.get("context and problem statement", "")
    if ctx and len(ctx) < 300:
        warn("context and problem statement", "context is very short: state the problem, the users, the scale and the constraints")

    drivers = bullets(secs.get("decision drivers", ""))
    if "decision drivers" in secs and len(drivers) < 3:
        err("decision drivers", f"at least 3 drivers as bullets (found {len(drivers)})")

    opts = subsections(secs.get("considered options", ""))
    if "considered options" in secs and len(opts) < 2:
        err("considered options", f"at least 2 options as '### Option ...' headings (found {len(opts)})")
    for name, body in opts.items():
        b = _real(body)
        if not re.search(r"(?im)^\s*[-*]\s*(good|pro)\b", b) or not re.search(r"(?im)^\s*[-*]\s*(bad|con)\b", b):
            warn("considered options", f"option '{name}': list both 'Good, because' and 'Bad, because' bullets")

    outcome = secs.get("decision outcome", "")
    if outcome:
        mm = re.search(r'Chosen option:\s*"?([^",\n]+)"?', outcome, flags=re.I)
        if not mm or "because" not in outcome.lower():
            err("decision outcome", 'write: Chosen option: "<name>", because <reason linked to the drivers>')
        elif opts and not any(mm.group(1).strip().lower() in o.lower() or o.lower() in mm.group(1).strip().lower()
                              for o in opts):
            warn("decision outcome", f"chosen option '{mm.group(1).strip()}' does not match any option heading")

    cons = subsections(secs.get("consequences", ""))
    low = {k.lower(): v for k, v in cons.items()}
    for side in ("positive", "negative"):
        if "consequences" in secs and not bullets(_real(low.get(side, ""))):
            why = " (an ADR with no negative consequences is not honest)" if side == "negative" else ""
            err("consequences", f"'### {side.capitalize()}' with at least one bullet{why}")

    cl = secs.get("cost and latency", "")
    if cl:
        if not re.search(r"(\$\s?\d|\d\s?\$|\d\s?USD\b)", cl):
            err("cost and latency", "no dollar figure: estimate cost per request and per month")
        if not re.search(r"\d\s?(ms|s|sec|seconds)\b", cl):
            err("cost and latency", "no latency figure (ms or s), e.g. p95 per path")

    conf = secs.get("confirmation", "")
    if conf and not re.search(r"\d", conf):
        err("confirmation", "no measurable threshold: say what you will measure and what number confirms the decision")
    return out
