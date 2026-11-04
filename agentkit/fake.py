"""Offline models for agents: deterministic, free, and honest about being fake.

FakeLLM(policy) has the same complete(req) -> ChatResult interface as llmkit.LLM, so
the Agent cannot tell the difference. Tokens are ESTIMATED (characters / 4, plus a fixed
286-token stand-in for the tool prompt Anthropic adds; the real size depends on the model
and tool_choice, so read it from a live run's usage) and priced like Claude Haiku 5.5; results say
estimated_cost=True. Two policies:

  ScriptPolicy(turns)    replays a fixed list of turns: for unit tests.
  AcmeHeuristic(...)     a small rule-based "model" for Acme access tasks. It reads the
                         task with regexes, reads the tool results it can still SEE
                         (cleared results are gone, notes survive), and picks the next
                         call. In plan mode (a <plan> in the system prompt) it batches
                         independent reads into one turn, like a model following a plan.
                         Knobs reproduce real failure modes:
                           loop="repeat"      the same call forever (-> repetition)
                           loop="paraphrase"  the same lookup with different arguments
                                              (-> no_progress; repetition misses it)
                           stubborn=True      keeps retrying a failing tool (-> tool_errors)
                           naive_docs=True    believes a document over check_policy

It is a stand-in for the mechanics, not for a model's judgment: numbers it produces show
how the loop, the limits and the metrics behave, never how good Claude is. Measure that
live (lesson 15, exercise 5).
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from functools import lru_cache
from types import SimpleNamespace
from typing import Any, Optional

from llmkit.pricing import cost_usd
from llmkit.types import ChatRequest, ChatResult, ToolCall, Usage, content_text

TOOL_PROMPT_TOKENS = 286


# ---------------------------------------------------------------- reading a request
@dataclass
class Obs:
    name: str
    args: dict
    is_error: bool
    text: str
    turn: int  # index of the tool turn (1-based)

    @property
    def cleared(self) -> bool:
        return self.text.startswith("[cleared:")

    @property
    def data(self) -> Optional[dict]:
        if self.is_error or self.cleared:
            return None
        try:
            v = json.loads(self.text)
            return v if isinstance(v, dict) else None
        except (json.JSONDecodeError, TypeError):
            return None


@dataclass
class View:
    task: str
    system: str
    tools: list[str]
    tool_choice: Optional[str]
    obs: list[Obs]
    turns: int  # assistant tool turns so far
    is_plan_request: bool
    prompt: str  # the last user text (the planner prompt in plan requests)

    @classmethod
    def of(cls, req: ChatRequest) -> "View":
        task = ""
        for m in req.messages:
            if m.role == "user" and isinstance(m.content, str):
                task = m.content
                break
        calls: dict[str, tuple[str, dict, int]] = {}
        obs: list[Obs] = []
        turns = 0
        for m in req.messages:
            if m.role == "assistant" and m.tool_calls:
                turns += 1
                for c in m.tool_calls:
                    calls[c.id] = (c.name, c.arguments, turns)
            for r in m.tool_results:
                name, args, t = calls.get(r.call_id, (r.name, {}, turns))
                obs.append(Obs(name, args, r.is_error, r.text, t))
        last_user = next((m.text for m in reversed(req.messages) if m.role == "user" and m.text), "")
        if req.response_schema is not None:
            mt = re.search(r"<task>\s*(.*?)\s*</task>", last_user, re.S)
            task = mt.group(1) if mt else last_user
        return cls(task, req.system_text, [t.name for t in req.tools], req.tool_choice, obs, turns,
                   req.response_schema is not None, last_user)

    def notes(self) -> list[str]:
        m = re.search(r"<notes>\n(.*?)\n</notes>", self.system, re.S)
        return [ln[2:] for ln in m.group(1).splitlines()] if m else []

    @property
    def in_plan_mode(self) -> bool:
        return "<plan>" in self.system

    def last_turn(self) -> list[Obs]:
        return [o for o in self.obs if o.turn == self.turns] if self.turns else []


@dataclass
class Action:
    text: str = ""
    calls: list[tuple[str, dict]] = field(default_factory=list)


# ---------------------------------------------------------------- the fake model
class FakeLLM:
    """llmkit.LLM look-alike driven by a policy object with act(view) and plan(view)."""

    estimated = True

    def __init__(self, policy, model: str = "fake-haiku", price_as: str = "claude-haiku-5-5"):
        self.policy = policy
        self.model = model
        self.price_as = price_as
        self.provider = SimpleNamespace(name="fake")
        self.requests: list[ChatRequest] = []
        self._n = 0

    def complete(self, req: ChatRequest, **_) -> ChatResult:
        self._n += 1
        self.requests.append(req)
        view = View.of(req)
        if view.is_plan_request:
            act = Action(text=json.dumps(self.policy.plan(view), ensure_ascii=False))
        else:
            act = self.policy.act(view)
            if req.tool_choice == "none":
                act = Action(text=act.text or "Stopped; see the trajectory for what was found.")
        calls = [ToolCall(f"fake_{self._n}_{i}", name, dict(args), json.dumps(args, ensure_ascii=False))
                 for i, (name, args) in enumerate(act.calls)]
        usage = Usage(input_tokens=estimate_input(req), output_tokens=estimate_output(act))
        return ChatResult(text=act.text, stop_reason="tool_use" if calls else "end", usage=usage,
                          provider="fake", model=self.model, cost_usd=cost_usd(self.price_as, usage),
                          tool_calls=calls, raw_stop_reason="tool_use" if calls else "end_turn")


def estimate_input(req: ChatRequest) -> int:
    chars = len(req.system_text)
    chars += len(json.dumps([{"n": t.name, "d": t.description, "s": t.input_schema} for t in req.tools]))
    for m in req.messages:
        chars += len(content_text(m.content)) if isinstance(m.content, str) else 0
        for c in m.tool_calls:
            chars += len(c.name) + len(json.dumps(c.arguments))
        for r in m.tool_results:
            chars += len(r.text)
        if not isinstance(m.content, str):
            chars += len(m.text)
    return max(1, chars // 4) + (TOOL_PROMPT_TOKENS if req.tools else 0)


def estimate_output(act: Action) -> int:
    return 8 + len(act.text) // 4 + sum(len(n) + len(json.dumps(a)) for n, a in act.calls) // 4


# ---------------------------------------------------------------- scripted policy (tests)
class ScriptPolicy:
    """turns: a list of {"text": "...", "calls": [{"name", "arguments"}]}. Turn k is used
    when the conversation has k earlier tool turns. Past the end: a final text."""

    def __init__(self, turns: list[dict], plan: Optional[dict] = None, final: str = "Done."):
        self.turns = turns
        self._plan = plan
        self.final = final

    def act(self, view: View) -> Action:
        if view.turns >= len(self.turns):
            return Action(self.final)
        t = self.turns[view.turns]
        return Action(t.get("text", ""), [(c["name"], c.get("arguments", {})) for c in t.get("calls", [])])

    def plan(self, view: View) -> dict:
        return self._plan or {"goal": view.task[:80], "steps": [{"id": 1, "action": "Answer", "tool": None,
                                                                "depends_on": []}], "done_when": "answered"}


# ---------------------------------------------------------------- the Acme heuristic
ROUTES = ("auto_approve", "needs_manager", "needs_security")


@lru_cache(maxsize=1)
def _acme_names() -> tuple[list[str], list[str], list[str]]:
    from toolkit.acme import ACME_DB, DOCS
    con = sqlite3.connect(f"file:{ACME_DB}?mode=ro", uri=True)
    try:
        people = [r[0] for r in con.execute("SELECT name FROM employees")]
        systems = [r[0] for r in con.execute("SELECT name FROM systems")]
    finally:
        con.close()
    docs = sorted(p.stem for p in DOCS.glob("*.md"))
    return people, systems, docs


ALIASES = {"aws production": "aws-production", "aws prod": "aws-production", "kubernetes production": "kubernetes-prod",
           "k8s prod": "kubernetes-prod", "google workspace": "google-workspace", "payroll": "hilan-payroll",
           "hilan": "hilan-payroll"}
LEVEL_WORDS = [("admin", "admin"), ("owner", "owner"), ("root", "admin"), ("editor", "editor"), ("paid seat", "editor"),
               ("write", "write"), ("read", "read"), ("viewer", "viewer"), ("member", "member")]
TRANSIENT = re.compile(r"unavailable|timed out|internal error|try again|temporar", re.I)


@dataclass
class TaskSpec:
    employee: Optional[str] = None
    systems: list[str] = field(default_factory=list)
    level: str = "member"
    level_given: bool = False
    duration: Optional[int] = None
    wants_request: bool = False
    only_if_auto: bool = False
    check_grants: bool = False
    list_access: bool = False
    ask_route: bool = False
    ask_manager: bool = False
    wants_doc: bool = False
    doc_id: str = ""
    external: bool = False
    compare: bool = False

    @property
    def system(self) -> Optional[str]:
        return self.systems[0] if self.systems else None


def parse_task(task: str) -> TaskSpec:
    people, systems, docs = _acme_names()
    t = task
    low = t.lower()
    s = TaskSpec()
    m = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", t)
    if m:
        s.employee = m.group(0).rstrip(".")
    elif re.search(r"\bE\d{3}\b", t):
        s.employee = re.search(r"\bE\d{3}\b", t).group(0)
    else:
        full = [p for p in people if p in t]
        if full:
            s.employee = max(full, key=len)
        else:
            firsts = {p.split()[0] for p in people}
            for w in re.findall(r"\b[A-Z][a-z']+\b", t):
                if w in firsts:
                    s.employee = w
                    break
    found: list[tuple[int, str]] = []
    for alias, name in ALIASES.items():
        for mm in re.finditer(re.escape(alias), low):
            found.append((mm.start(), name))
    for name in systems:
        for pat in {name, name.replace("-", " ")}:
            for mm in re.finditer(r"\b" + re.escape(pat) + r"\b", low):
                found.append((mm.start(), name))
    for _, name in sorted(found):
        if name not in s.systems:
            s.systems.append(name)
    for word, level in LEVEL_WORDS:
        if re.search(r"\b" + word + r"\b", low):
            s.level, s.level_given = level, True
            break
    d = re.search(r"(\d+)\s*days?", low)
    s.duration = int(d.group(1)) if d else (7 if "a week" in low else None)
    no_file = re.search(r"(do not|don't|dont|without) (file|filing|submit)|not file anything|nothing filed", low)
    s.wants_request = bool(re.search(r"\b(open|file|submit|create|raise)\b[^.?]{0,40}\brequest\b|\bfile it\b", low)) \
        and not no_file
    s.only_if_auto = bool(re.search(r"only (file|open|submit)[^.]{0,60}auto|only if[^.]{0,40}auto", low))
    s.check_grants = bool(re.search(r"already (has|have)|whether (s?he|they|he|she) (already )?(has|have)|"
                                    r"does [^.?]{0,40} already", low))
    s.list_access = bool(re.search(r"what access does|which systems does|list the systems|have right now", low))
    s.ask_route = bool(re.search(r"route|track|who reviews|policy|approve", low))
    s.ask_manager = bool(re.search(r"manager|who approves|who will approve|approver", low))
    s.external = bool(re.search(r"oauth|external|third-party|share [^.]{0,30} with", low))
    s.compare = "compare" in low
    s.wants_doc = bool(re.search(r"document|according to", low))
    if s.wants_doc:
        doc = next((d for d in docs if d in low), None)
        s.doc_id = doc or "it-saas-access-v2-2"
    return s


@dataclass
class Facts:
    employee: Optional[dict] = None
    policy: Optional[dict] = None
    grants: Optional[dict] = None
    doc: Optional[dict] = None
    systems: dict[str, dict] = field(default_factory=dict)
    created: Optional[dict] = None


NOTE_KEYS = {"lookup_employee": ("id", "name", "email", "manager"),
             "check_policy": ("system", "access_level", "route", "review_target", "default_expiry_days"),
             "list_access_grants": ("employee", "count", "grants"),
             "get_system_info": ("name", "owner_team", "tier", "sensitive", "approved_tool"),
             "create_access_request": ("id", "route", "status", "approver", "expires_at")}


def _note_for(o: Obs) -> Optional[str]:
    d = o.data
    if d is None or o.name not in NOTE_KEYS:
        return None
    keep = {k: d[k] for k in NOTE_KEYS[o.name] if k in d}
    if o.name == "list_access_grants":
        keep["grants"] = [{k: g[k] for k in ("system", "level")} for g in d.get("grants", [])]
    return f"{o.name}: {json.dumps(keep, ensure_ascii=False, separators=(',', ':'))}"


def gather(view: View) -> Facts:
    f = Facts()
    sources: list[tuple[str, dict]] = []
    for n in view.notes():
        name, _, js = n.partition(": ")
        try:
            sources.append((name, json.loads(js)))
        except json.JSONDecodeError:
            continue
    for o in view.obs:
        if o.data is not None:
            sources.append((o.name, o.data))
    for name, d in sources:
        if name == "lookup_employee":
            f.employee = d
        elif name == "check_policy":
            f.policy = d
        elif name == "list_access_grants":
            f.grants = d
            if f.employee is None and d.get("employee"):
                f.employee = dict(d["employee"])
        elif name == "read_document":
            f.doc = d
        elif name == "get_system_info":
            f.systems[d.get("name", "?")] = d
        elif name == "create_access_request":
            f.created = d
    return f


class AcmeHeuristic:
    def __init__(self, *, loop: str = "", stubborn: bool = False, naive_docs: bool = False, max_retries: int = 1):
        self.loop = loop
        self.stubborn = stubborn
        self.naive_docs = naive_docs
        self.max_retries = max_retries

    # ---- planning (structured output)
    def plan(self, view: View) -> dict:
        s = parse_task(view.task)
        if re.search(r"employees are named|No employee matches", view.prompt):
            return {"goal": "Resolve who the request is for", "done_when": "the user was asked",
                    "steps": [{"id": 1, "action": "Explain the problem and ask the user which person they mean",
                               "tool": None, "depends_on": []}]}
        steps = []
        for call in self._reads(s, Facts(), batch=True):
            steps.append({"id": len(steps) + 1, "action": f"Call {call[0]} to get the facts", "tool": call[0],
                          "depends_on": []})
        if s.wants_request:
            steps.append({"id": len(steps) + 1, "action": "File the request if the checks allow it",
                          "tool": "create_access_request", "depends_on": [x["id"] for x in steps]})
        steps.append({"id": len(steps) + 1, "action": "Answer the user with the facts found", "tool": None,
                      "depends_on": [x["id"] for x in steps]})
        return {"goal": view.task[:120], "steps": steps, "done_when": "the user has the answer"}

    # ---- acting
    def _reads(self, s: TaskSpec, f: Facts, batch: bool) -> list[tuple[str, dict]]:
        """The read-only calls still needed, in the order a careful agent would make them."""
        out: list[tuple[str, dict]] = []
        if s.compare:
            out += [("get_system_info", {"system": x}) for x in s.systems if x not in f.systems]
            return out
        if (s.check_grants or s.list_access) and f.grants is None and s.employee:
            out.append(("list_access_grants", {"employee": s.employee,
                                               "system": s.system if s.check_grants else None,
                                               "include_expired": False}))
            if not batch:
                return out
        need_emp = (s.wants_request or s.ask_manager) and s.employee and (
            f.employee is None or (s.ask_manager and not f.employee.get("manager")))
        if need_emp and not (batch and out and not s.ask_manager):
            out.append(("lookup_employee", {"employee": s.employee}))
        if s.system and (s.wants_request or s.ask_route) and f.policy is None and not s.list_access:
            out.append(("check_policy", {"system": s.system, "access_level": s.level, "external_sharing": s.external,
                                         "holds_customer_or_financial_data": None}))
        if s.wants_doc and f.doc is None:
            out.append(("read_document", {"doc_id": s.doc_id}))
        return out

    def _has_already(self, s: TaskSpec, f: Facts) -> Optional[dict]:
        if f.grants is None:
            return None
        for g in f.grants.get("grants", []):
            if g.get("system") == s.system and (not s.level_given or g.get("level") == s.level):
                return g
        return None

    def act(self, view: View) -> Action:
        s = parse_task(view.task)
        f = gather(view)
        last = view.last_turn()

        # loops on purpose (failure demos)
        if self.loop and f.employee and s.employee:
            if self.loop == "repeat":
                return Action("Let me check the employee again.", [("lookup_employee", {"employee": s.employee})])
            keys = [s.employee, f.employee.get("email"), f.employee.get("id"), f.employee.get("name")]
            keys = [k for k in dict.fromkeys(keys) if k]
            return Action("Let me double-check that record.", [("lookup_employee", {"employee": keys[view.turns % len(keys)]})])

        # errors in the last turn
        for e in [o for o in last if o.is_error]:
            if "employees are named" in e.text:
                names = re.findall(r"([A-Z][\w'-]+(?: [A-Z][\w'-]+)+) <", e.text)
                return Action(f"I found several people named {s.employee}: {', '.join(names)}. Which one do you mean? "
                              "I have not filed anything.")
            if "No employee matches" in e.text:
                return Action("", [("give_up", {"reason": f"No Acme employee matches {e.args.get('employee')!r}.",
                                                "missing": "the person's correct work email"})])
            if "DECLINED" in e.text or "NOT executed" in e.text:
                return Action(self._final(s, f, declined=True))
            if "Unknown system" in e.text:
                return Action("", [("give_up", {"reason": e.text[:200], "missing": "the exact system name"})])
            if TRANSIENT.search(e.text):
                fails = sum(1 for o in view.obs if o.name == e.name and o.is_error)
                if self.stubborn or fails <= self.max_retries:
                    return Action(f"{e.name} failed ({e.text[:60]}). Retrying once.", [(e.name, e.args)])
                return Action("", [("give_up", {"reason": f"The {e.name} tool keeps failing: {e.text[:120]}",
                                                "missing": "try again later"})])

        notes = self._notes(view) if "note" in view.tools else []
        if f.created is not None:  # the side effect happened: report, never redo
            return Action(self._final(s, f), [])
        if s.check_grants and self._has_already(s, f) is not None and not s.ask_route:
            return Action(self._final(s, f), [])
        reads = self._reads(s, f, batch=view.in_plan_mode)
        if reads:
            calls = reads if view.in_plan_mode else reads[:1]
            why = {"lookup_employee": "I need the employee record and manager",
                   "check_policy": "I need the approval route from the policy",
                   "list_access_grants": "I need the current grants", "read_document": "I need the document text",
                   "get_system_info": "I need the system facts"}
            return Action("; ".join(dict.fromkeys(why[c[0]] for c in calls)) + ".", notes + calls)
        if s.wants_request and f.created is None and f.employee and f.policy:
            if s.only_if_auto and f.policy.get("route") != "auto_approve":
                return Action(self._final(s, f))
            if s.check_grants and self._has_already(s, f) is not None:
                return Action(self._final(s, f))
            email = f.employee.get("email") or s.employee
            args = {"employee": email, "system": s.system, "access_level": s.level,
                    "justification": view.task.split(".")[0][:160], "duration_days": s.duration,
                    "idempotency_key": f"{email}:{s.system}:{s.level}"}
            return Action("The policy check is done, so I will file the request (a human must confirm).",
                          notes + [("create_access_request", args)])
        return Action(self._final(s, f), [])

    def _notes(self, view: View) -> list[tuple[str, dict]]:
        have = set(view.notes())
        out = []
        for o in view.last_turn():
            n = _note_for(o)
            if n and n not in have:
                out.append(("note", {"text": n}))
        return out

    # ---- the answer
    def _final(self, s: TaskSpec, f: Facts, declined: bool = False) -> str:
        parts: list[str] = []
        if s.compare:
            for name in s.systems:
                d = f.systems.get(name)
                if d:
                    parts.append(f"{name}: owner team {d.get('owner_team')}, tier {d.get('tier')}, "
                                 f"{'sensitive' if d.get('sensitive') else 'not sensitive'}.")
            return " ".join(parts) or "I could not get the system facts."
        e = f.employee
        if e and e.get("name"):
            line = f"{e['name']} ({e.get('id', '?')})"
            if e.get("manager"):
                line += f" reports to {e['manager'].get('name')} ({e['manager'].get('id')})"
            parts.append(line + ".")
        if s.list_access and f.grants is not None:
            gl = ", ".join(f"{g['system']} ({g['level']})" for g in f.grants.get("grants", []))
            parts.append(f"Current access: {gl or 'none'}.")
        elif s.check_grants and f.grants is not None:
            g = self._has_already(s, f)
            if g:
                parts.append(f"They already have {g['system']} {g['level']} access ({g.get('id', 'existing grant')}), "
                             "so nothing new was filed.")
            else:
                parts.append(f"They have no current {s.system} grant at that level.")
        if f.policy:
            p = f.policy
            route = p.get("route")
            doc_route = self._doc_route(f) if s.wants_doc else None
            if doc_route and doc_route != route and self.naive_docs:
                parts.append(f"According to the document, {p.get('access_level')} on {p.get('system')} is {doc_route}.")
            else:
                parts.append(f"check_policy: {p.get('access_level')} on {p.get('system')} routes to {route} "
                             f"({p.get('review_target')}).")
                if doc_route and doc_route != route:
                    parts.append(f"Note: the document says {doc_route}, but check_policy (the authority) says {route}.")
        if s.wants_doc and f.doc and not f.policy:  # a document question: quote the relevant sentences
            text = f.doc.get("text", "")
            keep = [x.strip() for x in re.split(r"(?<=[.])\s+", text)
                    if re.search(r"business days|expire", x, re.I) and len(x) < 300][:3]
            parts.append(f"From {f.doc.get('id')}: " + " ".join(keep) if keep else f"I read {f.doc.get('id')}.")
        if f.created:
            c = f.created
            parts.append(f"Filed {c.get('id')}: route {c.get('route')}, status {c.get('status')}, approver "
                         f"{c.get('approver')}, expires {c.get('expires_at') or 'never'}.")
        elif declined:
            parts.append("The request was NOT submitted: no human approved it.")
        elif s.wants_request and s.only_if_auto and f.policy and f.policy.get("route") != "auto_approve":
            parts.append("I did not file it, because it cannot be auto-approved.")
        return " ".join(parts) or "I could not find an answer with the available tools."

    @staticmethod
    def _doc_route(f: Facts) -> Optional[str]:
        if not f.doc or not f.policy:
            return None
        system = str(f.policy.get("system", ""))
        for sent in re.split(r"(?<=[.])\s+", f.doc.get("text", "")):
            low = sent.lower()
            if system.split("-")[0] in low:
                for r in ROUTES:
                    if r in low:
                        return r
        return None
