"""Which Acme domain does a piece of text belong to? (lesson 18)

Three specialist domains:
  hr         people policies: vacation, sick leave, remote work, parental leave, expenses ...
  it_access  SaaS / system access requests under the access policy (the lesson 15 tasks)
  oncall     engineering on-call: rotations, handovers, PagerDuty, runbooks, team leads

This keyword classifier is NOT what a real router uses (the router asks a model with
structured output, see router.py). It exists for two reasons:
  1. the offline fake models in fake.py use it to decide what a "model" would do, and
  2. it is the cheap baseline every LLM router should beat (exercise 1 compares them).

split_by_domain() cuts a task into sentences, labels each, and glues sentences without
any keyword to the segment before them ("Do not file anything." belongs to the request
before it). The fakes give every specialist only ITS segments, the way a supervisor writes
a focused brief, and a single agent walks the segments one by one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

DOMAINS = ("hr", "it_access", "oncall")

DOMAIN_INFO = {
    "hr": "HR policies: vacation and carry-over, sick leave, remote work, parental leave, reserve duty, expenses, "
          "relocation, onboarding, health insurance, performance reviews",
    "it_access": "Access to SaaS tools and systems: who has access, which approval track a request takes "
                 "(auto_approve / needs_manager / needs_security), filing access requests, system facts",
    "oncall": "Engineering on-call for production services: which rotation covers a service, handover times, "
              "acknowledge targets, PagerDuty services, runbooks, owning team and team lead",
}

SERVICES = ("flow-api", "flow-engine", "flow-scheduler", "auth-service", "billing-service", "connectors-hub",
            "notifications", "web-app", "lighthouse")

_WORDS = {
    "hr": [r"vacation", r"carr(y|ied)[ -]over", r"sick", r"medical certificate", r"remote(ly)?\b", r"work from home",
           r"parental", r"maternity", r"paternity", r"reserve duty", r"expenses?", r"reimburse", r"relocation",
           r"onboarding", r"health insurance", r"performance review", r"days off", r"leave\b", r"accrue",
           r"per diem", r"office days?"],
    "it_access": [r"access\b", r"\brequest\b", r"\bseat\b", r"account\b", r"\badmin\b", r"\beditor\b", r"\bowner access",
                  r"\bgrants?\b", r"\btrack\b", r"approves?\b", r"approval", r"who reviews", r"permission",
                  r"\bfile (it|the request|a request)", r"oauth", r"security review", r"\bwrite\b",
                  r"compare [a-z0-9-]+ and"],
    "oncall": [r"on[- ]?call", r"rotation", r"handover", r"pagerduty", r"runbook", r"acknowledge", r"\bpaged?\b",
               r"\bshift\b", r"escalat"],
}
_RX = {d: [re.compile(w, re.I) for w in ws] for d, ws in _WORDS.items()}
_SENT = re.compile(r"(?<=[.?!])\s+(?=[A-Z0-9\"'(])")


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT.split(text.strip()) if s.strip()]


def domain_scores(text: str) -> dict[str, float]:
    """Keyword hits per domain. A production-service name counts half a point for oncall:
    services are also systems you can request access to (flow-api is in the systems table)."""
    low = text.lower()
    out = {d: float(sum(1 for rx in _RX[d] if rx.search(low))) for d in DOMAINS}
    if any(re.search(r"\b" + re.escape(s) + r"\b", low) for s in SERVICES):
        out["oncall"] += 0.5
    return out


def top_domain(text: str) -> str | None:
    sc = domain_scores(text)
    best = max(DOMAINS, key=lambda d: sc[d])
    if sc[best] <= 0.5:  # a lone service name is not enough to call it on-call work
        return None
    return best


@dataclass
class Segment:
    domain: str
    text: str


def split_by_domain(task: str) -> list[Segment]:
    """Consecutive sentences of the same domain form one segment; unlabeled sentences join the
    segment before them (or the first labeled one). Segments keep the order of the task."""
    labeled = [(top_domain(s), s) for s in sentences(task)]
    segs: list[Segment] = []
    pending: list[str] = []  # unlabeled sentences before the first labeled one
    for dom, s in labeled:
        if dom is None:
            if segs:
                segs[-1].text += " " + s
            else:
                pending.append(s)
            continue
        if segs and segs[-1].domain == dom:
            segs[-1].text += " " + s
        else:
            segs.append(Segment(dom, s))
        if pending:
            segs[-1].text = " ".join(pending + [segs[-1].text])
            pending = []
    return segs


def domains_of(task: str) -> list[str]:
    """The domains a task touches, in order of first appearance."""
    return list(dict.fromkeys(s.domain for s in split_by_domain(task)))


def text_for(task: str, domain: str) -> str:
    """Only the sentences of one domain (what a focused brief for that specialist would say)."""
    return " ".join(s.text for s in split_by_domain(task) if s.domain == domain)
