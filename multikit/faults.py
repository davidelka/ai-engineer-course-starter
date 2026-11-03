"""Worker faults for the failure exercise (lesson 18, exercise 7): a worker returns WRONG information.

The worker's tools and evidence stay correct; only its final answer is corrupted (a model
that misread its own tool result, or summarized it badly). The question is whether the agent
above it notices. Tool-level faults (errors, stale documents) come from agentkit.faults.

    corrupt_text("route needs_security", CORRUPTIONS["route"])  -> "route auto_approve"
"""

from __future__ import annotations

CORRUPTIONS: dict[str, list[tuple[str, str]]] = {
    # it_access: the strictest track silently becomes the easiest one
    "route": [("needs_security", "auto_approve"), ("needs_manager", "auto_approve")],
    # oncall: the wrong team lead and the wrong rotation
    "lead": [("Rina Sasson", "Omer Haddad"), ("Gil Avraham", "Maya Rosen"), ("Dana Levi", "Itai Barak"),
             ("Omer Haddad", "Rina Sasson")],
    "rotation": [("engine-oncall", "core-api-oncall"), ("billing-oncall", "frontend-oncall"),
                 ("integrations-oncall", "identity-oncall")],
    # hr: a number changes (5 carry-over days -> 10)
    "number": [("Up to 5 unused days", "Up to 10 unused days"), ("up to 2 days per week", "up to 4 days per week"),
               ("1.5 sick days", "2.5 sick days")],
}

WORKER_OF = {"route": "it_access", "lead": "oncall", "rotation": "oncall", "number": "hr"}


def corrupt_text(text: str, rules: list[tuple[str, str]]) -> str:
    """Apply each (old, new) replacement once per occurrence, simultaneously (a swap stays a swap)."""
    marks = {}
    for i, (old, _) in enumerate(rules):
        if old in text:
            tok = f"\x00{i}\x00"
            text = text.replace(old, tok)
            marks[tok] = rules[i][1]
    for tok, new in marks.items():
        text = text.replace(tok, new)
    return text
