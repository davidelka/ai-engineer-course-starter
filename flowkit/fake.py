"""A fake LLM for offline runs and tests of the workflow (lesson 16).

It has the same surface as llmkit.LLM that the workflow uses (`provider.name`, `model`,
`complete(req)`), so llmkit.structured.complete_structured works with it unchanged.

  - Scripted replies first: FakeLLM(replies=['{"system": ...}', LLMError(...), callable]).
    A string is the reply text, an exception is raised, a callable gets the request.
  - Otherwise a request with a response_schema (the intake step) is answered by a small
    rule-based extractor that reads the text between <request> tags; any other request
    (the risk summary) gets a template built from the facts in the prompt.

The extractor is deliberately simple (keywords and aliases). It is NOT a model: it exists so
the graph, the checkpoints and the approval gates can be exercised without a key. Usage is
estimated (characters / 4) and the cost is 0.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, Callable, Optional, Union

from llmkit.types import ChatRequest, ChatResult, Usage, content_text

SYSTEMS = ["flow-api", "flow-engine", "flow-scheduler", "auth-service", "billing-service", "connectors-hub",
           "notifications", "web-app", "lighthouse", "conveyor", "kubernetes-prod", "aws-production", "datadog",
           "pagerduty", "jira", "confluence", "slack", "google-workspace", "zoom", "miro", "figma", "github",
           "1password", "salesforce", "zendesk", "netsuite", "hilan-payroll", "notion"]
ALIASES = {
    "aws": "aws-production", "amazon web services": "aws-production", "kubernetes": "kubernetes-prod",
    "k8s": "kubernetes-prod", "google drive": "google-workspace", "gmail": "google-workspace",
    "google workspace": "google-workspace", "g suite": "google-workspace", "payroll": "hilan-payroll",
    "hilan": "hilan-payroll", "crm": "salesforce", "git hub": "github",
}
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
NAME_FOR = re.compile(r"\b(?:add|for|give|grant)\s+([A-Z][a-z]+ [A-Z][a-z]+(?:-[A-Z][a-z]+)?)")


def _find_system(low: str) -> str:
    hits = []
    for name in SYSTEMS:
        m = re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", low)
        if m:
            hits.append((m.start(), name))
    for alias, name in ALIASES.items():
        m = re.search(rf"(?<![\w-]){re.escape(alias)}(?![\w-])", low)
        if m:
            hits.append((m.start(), name))
    if hits:
        return sorted(hits)[0][1]
    m = re.search(r"\b(?:access to|seat (?:in|on)|account (?:in|on)|to)\s+([a-z][\w-]+)", low)
    return m.group(1) if m else "unknown"


def _find_level(low: str) -> str:
    rules = [(r"\bowner\b", "owner"), (r"\b(admin|administrator|root)\b", "admin"),
             (r"\b(editor|edit|paid seat|full seat)\b", "editor"), (r"\b(write|push|commit)\b", "write"),
             (r"\b(viewer|view)\b", "viewer"), (r"\b(read|read-only|readonly)\b", "read")]
    for pat, level in rules:
        if re.search(pat, low):
            return level
    return "member"


def heuristic_extract(text: str, sender: Optional[str] = None) -> dict:
    """Free text -> a dict shaped like flowkit.state.IntakeRequest (keywords, not understanding)."""
    low = text.lower()
    employee = None
    emails = [e for e in EMAIL.findall(text) if e.lower() != (sender or "").lower()]
    if emails:
        employee = emails[0]
    else:
        m = NAME_FOR.search(text)
        if m and m.group(1).split()[0] not in {"Read", "Admin", "Write", "Access"}:
            employee = m.group(1)
    days = None
    m = re.search(r"(\d+)\s*(day|days|week|weeks|month|months)\b", low)
    if m:
        n = int(m.group(1))
        days = n * {"d": 1, "w": 7, "m": 30}[m.group(2)[0]]
        days = max(1, min(365, days))
    justification = None
    m = re.search(r"\b(?:because|so that|so i can|to)\s+(.+?)(?:[.!?]|$)", text, re.I)
    if m:
        justification = m.group(1).strip()[:160]
    external = bool(re.search(r"\b(external|outside|third[- ]party|oauth|agency|vendor|partner)\b", low))
    return {"employee": employee, "system": _find_system(low), "access_level": _find_level(low),
            "external_sharing": external, "duration_days": days, "justification": justification}


def _risk_template(prompt: str) -> str:
    def grab(key: str) -> str:
        m = re.search(rf"^{key}:\s*(.+)$", prompt, re.M)
        return m.group(1).strip() if m else "?"
    return (f"{grab('employee')} asks for {grab('access_level')} access to {grab('system')} "
            f"({grab('data_classification')} data, tier {grab('tier')}). Policy: {grab('reasons')}. "
            f"Existing access on this system: {grab('existing_grants')}. "
            f"Check that the justification fits the role ({grab('title')}) and prefer a time-limited grant.")


Reply = Union[str, Exception, Callable[[ChatRequest], str]]


@dataclass
class FakeLLM:
    replies: list[Reply] = field(default_factory=list)  # consumed in order, before the built-in behavior
    model: str = "fake-model"
    calls: list[ChatRequest] = field(default_factory=list)

    def __post_init__(self):
        self.provider = SimpleNamespace(name="anthropic")  # complete_structured builds an Anthropic-style schema
        self.replies = list(self.replies)

    def complete(self, req: Union[ChatRequest, str], **kw: Any) -> ChatResult:
        if isinstance(req, str):
            req = ChatRequest.from_prompt(req)
        self.calls.append(req)
        last_user = next((content_text(m.content) for m in reversed(req.messages) if m.role == "user"), "")
        if self.replies:
            r = self.replies.pop(0)
            if isinstance(r, Exception):
                raise r
            text = r(req) if callable(r) else r
        elif req.response_schema is not None:
            m = re.search(r"<request>(.*?)</request>", last_user, re.S)
            s = re.search(r"Sender:\s*(\S+)", last_user)
            text = json.dumps(heuristic_extract(m.group(1) if m else last_user, s.group(1) if s else None))
        else:
            text = _risk_template(last_user)
        prompt_chars = len(content_text(req.system) if req.system else "") + sum(
            len(content_text(m.content)) for m in req.messages)
        usage = Usage(input_tokens=prompt_chars // 4 + 1, output_tokens=len(text) // 4 + 1)
        return ChatResult(text=text, stop_reason="end_turn", usage=usage, provider="fake", model=self.model,
                          cost_usd=0.0)
