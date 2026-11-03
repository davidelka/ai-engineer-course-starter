"""A small parser for Mermaid sequence diagrams, and the design checks for the
access-request flow (exercise 7). It understands the subset the exercise needs:
participant/actor lines, messages (->> -->> -> --> -x --x -) --)), and the
blocks alt/else, opt, loop, par/and, critical/option, break, rect ... end.
It is a checker of the DESIGN rules, not a full Mermaid validator: render the
file (mermaid.live, GitHub, or mmdc) to see that Mermaid itself accepts it.
"""

from __future__ import annotations

import base64
import json
import re
import zlib
from dataclasses import dataclass, field

ARROW = r"(-->>|->>|-->|->|--x|-x|--\)|-\))"
MSG = re.compile(rf"^([A-Za-z_][\w]*)\s*{ARROW}\s*[+-]?\s*([A-Za-z_][\w]*)\s*:\s*(.*)$")
PART = re.compile(r"^(participant|actor)\s+([A-Za-z_][\w]*)(?:\s+as\s+(.+))?$")
OPEN = ("alt", "opt", "loop", "par", "critical", "break", "rect", "box")
MIDDLE = ("else", "and", "option")


@dataclass
class Message:
    src: str
    arrow: str
    dst: str
    text: str
    line: int
    blocks: list[tuple[str, str]] = field(default_factory=list)  # (kind, branch label), outermost first

    @property
    def is_reply(self) -> bool:
        return self.arrow.startswith("--")


@dataclass
class Diagram:
    participants: dict[str, str]
    messages: list[Message]
    blocks: list[tuple[str, list[str]]]  # (kind, [label of each branch]) for alt/opt/... in order
    errors: list[str]


def parse(text: str) -> Diagram:
    parts: dict[str, str] = {}
    msgs: list[Message] = []
    blocks: list[tuple[str, list[str]]] = []
    stack: list[list] = []  # [kind, current label, index in blocks]
    errors: list[str] = []
    seen_header = False
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("%%"):
            continue
        if line == "sequenceDiagram":
            seen_header = True
            continue
        word = line.split()[0]
        if word in ("autonumber", "activate", "deactivate", "title") or word.startswith("Note") or word == "note":
            continue
        m = PART.match(line)
        if m:
            parts[m[2]] = (m[3] or m[2]).strip()
            continue
        if word in OPEN:
            label = line[len(word):].strip()
            blocks.append((word, [label]))
            stack.append([word, label, len(blocks) - 1])
            continue
        if word in MIDDLE:
            if not stack:
                errors.append(f"line {n}: '{word}' outside a block")
                continue
            label = line[len(word):].strip()
            stack[-1][1] = label
            blocks[stack[-1][2]][1].append(label)
            continue
        if line == "end":
            if not stack:
                errors.append(f"line {n}: 'end' without an open block")
            else:
                stack.pop()
            continue
        m = MSG.match(line)
        if m:
            src, arrow, dst, txt = m[1], m[2], m[3], m[4].strip()
            for p in (src, dst):
                parts.setdefault(p, p)  # Mermaid allows implicit participants
            msgs.append(Message(src, arrow, dst, txt, n, [(s[0], s[1]) for s in stack]))
            continue
        errors.append(f"line {n}: not understood: {line[:60]}")
    if not seen_header:
        errors.insert(0, "the file must start with 'sequenceDiagram'")
    if stack:
        errors.append(f"{len(stack)} block(s) never closed with 'end'")
    return Diagram(parts, msgs, blocks, errors)


# ---------------------------------------------------------------- the design rules
REQUIRED = {"Emp": "Employee", "API": "AccessAPI", "Svc": "AccessService", "LLM": "Classifier",
            "Pol": "PolicyEngine", "Store": "RequestStore", "Appr": "Approver", "IdP": "IdentityProvider"}
ERRWORDS = re.compile(r"timeout|unavailable|error|fail|down", re.I)


def _first(d: Diagram, pred) -> int:
    return next((i for i, m in enumerate(d.messages) if pred(m)), -1)


def check(text: str) -> list[tuple[str, bool, str]]:
    """Returns (rule, passed, explanation) for each design rule."""
    d = parse(text)
    res: list[tuple[str, bool, str]] = []

    def add(rule, ok, why):
        res.append((rule, bool(ok), why))

    add("parses", not d.errors, "; ".join(d.errors) or "the diagram parses")
    used = {m.src for m in d.messages} | {m.dst for m in d.messages}
    missing = [p for p in REQUIRED if p not in used]
    add("all participants used", not missing,
        f"never used: {', '.join(missing)}" if missing else "all 8 participants take part")

    first_req = _first(d, lambda m: m.src == "Emp" and m.dst == "API")
    ok = first_req >= 0 and re.search(r"request_id|idempotency", d.messages[first_req].text, re.I)
    add("idempotency key on the request", ok,
        "the first Emp->>API message must carry request_id (or an Idempotency-Key)")

    llm_call = _first(d, lambda m: m.dst == "LLM" and not m.is_reply)
    store_first = _first(d, lambda m: m.dst == "Store" and not m.is_reply)
    add("check the store before the model", 0 <= store_first < llm_call,
        "Svc must look up request_id in Store BEFORE calling the LLM (a retry must not pay twice)")

    reply = _first(d, lambda m: m.src == "LLM" and m.is_reply)
    add("model call and its reply", llm_call >= 0 and reply > llm_call,
        "Svc->>LLM, then a dashed reply LLM-->>Svc")

    err_branch = [m for m in d.messages if any(ERRWORDS.search(lbl or "") for _, lbl in m.blocks)]
    ok = any(re.search(r"needs_manager|needs_security|human|Appr", m.text + m.dst, re.I) for m in err_branch)
    add("an error path for the model", ok,
        "a block (alt/else/break/opt) whose label says timeout/unavailable/error, that sends the request "
        "to a human route instead of failing or auto-approving")

    pol = _first(d, lambda m: m.dst == "Pol" and not m.is_reply)
    add("rules after the model", pol > llm_call >= 0,
        "PolicyEngine is called AFTER the classifier: the model proposes a route, the rules decide")

    labels = " ".join(lbl for kind, branches in d.blocks if kind == "alt" for lbl in branches)
    need = [r for r in ("auto_approve", "needs_manager", "needs_security") if r not in labels]
    add("three routes in an alt", not need,
        f"alt/else branches missing for: {', '.join(need)}" if need else "alt covers all three routes")

    def grant_ok(i: int, m: Message) -> bool:
        in_auto = any("auto_approve" in (lbl or "") for _, lbl in m.blocks)
        approved_before = any(x.src == "Appr" for x in d.messages[:i])
        return in_auto or approved_before

    grants = [(i, m) for i, m in enumerate(d.messages) if m.dst == "IdP" and not m.is_reply]
    add("no grant without a decision", grants and all(grant_ok(i, m) for i, m in grants),
        "every call to IdP must be inside the auto_approve branch, or come after a message from Appr")

    saved = any(m.dst == "Store" and re.search(r"save|store|record|audit|write|insert|put", m.text, re.I)
                for m in d.messages)
    add("decision persisted", saved, "a message to Store that saves/records the decision (audit trail)")

    add("employee gets an answer", any(m.dst == "Emp" for m in d.messages), "some message goes back to Emp")
    return res


def mermaid_live_url(code: str) -> str:
    """Link that opens the diagram in the mermaid.live editor (pako = zlib + urlsafe base64)."""
    state = json.dumps({"code": code, "mermaid": json.dumps({"theme": "default"}), "autoSync": True})
    data = base64.urlsafe_b64encode(zlib.compress(state.encode(), 9)).decode().rstrip("=")
    return "https://mermaid.live/edit#pako:" + data
