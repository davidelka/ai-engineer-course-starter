"""Offline "models" for the multi-agent patterns (lesson 18). Deterministic and free.

They plug into agentkit.FakeLLM (same complete(req) interface as llmkit.LLM), so every
pattern runs unchanged with a real model. Tokens are ESTIMATED (characters / 4) and priced
like Haiku 5.5. Like lesson 15's AcmeHeuristic, they show the MECHANICS (who calls whom, how
context grows, what each agent pays, where a failure propagates), never a model's judgment.

  HRHeuristic           search_hr_policies -> read_document (newest version) -> quote sentences
  OncallHeuristic       get_oncall_for_service(<service in the task>) -> answer from the row
  SpecialistHeuristic   wraps one of the above (or AcmeHeuristic): handles ONLY its domain's
                        sentences of the task and says what it did not handle
  ComboHeuristic        the single agent: walks the domain segments of the task one by one
  RouterHeuristic       plan(): a RouteDecision from keyword scores (multi-domain -> 0.7)
  SupervisorHeuristic   delegate_to_<domain>(task=<that domain's sentences>), all at once or
                        one by one; verify=True cross-checks each answer with its evidence
  HandoffHeuristic      triage -> transfer_to_<first domain>; each specialist transfers to the
                        next domain with a summary; lossy=True writes a bad summary
  ResearchHeuristic     planner (split into sub-questions), worker (search -> read -> cite),
                        synthesizer (join, keep citations)
  WriterHeuristic / CriticHeuristic   the generator-critic loop
"""

from __future__ import annotations

import json
import re
from dataclasses import replace
from typing import Optional

from agentkit import AcmeHeuristic, FakeLLM
from agentkit.fake import Action, View

from .domains import DOMAINS, SERVICES, domains_of, split_by_domain, text_for

STOP = set("a an the of to in on for and or is are be can do does did what which who whom when how many much per "
           "under with by from at as it its this that their they them his her he she i me my we our you your "
           "also separately according any there was were has have had will would should could into about".split())
CONSTRAINT_RX = re.compile(r"[^.?!]*\b(do not|don't|only if|only after|without|not yet|never)\b[^.?!]*[.?!]?", re.I)


def keywords(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9][a-z0-9%$.-]*", text.lower())
    return [w.strip(".") for w in words if w.strip(".") not in STOP and len(w.strip(".")) > 1]


def _stem(w: str) -> str:
    return re.sub(r"(ing|ed|es|s)$", "", w) if len(w) > 4 else w


def best_sentences(text: str, query: str, n: int = 2) -> list[str]:
    """The n sentences (or bullet lines) of a document that share the most keywords with the query."""
    q = {_stem(w) for w in keywords(query)}
    parts = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("|"):  # a table row: keep its cells as one "sentence"
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) > 1 and not set("".join(cells)) <= set("-: "):
                parts.append(" | ".join(cells))
            continue
        line = line.lstrip("-*# ").strip()
        if not line or len(line) < 30:
            continue
        parts += [s.strip() for s in re.split(r"(?<=[.!?])\s+", line) if len(s.strip()) > 30]
    scored = []
    for i, s in enumerate(parts):
        words = {_stem(w) for w in keywords(s)}
        hit = len(q & words) + 0.5 * bool(re.search(r"\d", s))
        if hit:
            scored.append((hit, -i, s))
    scored.sort(reverse=True)
    return [s for _, _, s in scored[:n]]


def _family(doc_id: str) -> str:
    return re.sub(r"(-\d{4}(-\d{2})?)?(-he)?$", "", doc_id)


def pick_hit(hits: list[dict], naive: bool = False) -> Optional[dict]:
    """The top hit's document family, newest version (naive=True: just the top hit, the stale-doc trap)."""
    hits = [h for h in hits if not h["doc_id"].endswith("-he")] or hits
    if not hits:
        return None
    if naive:
        return hits[0]
    fam = _family(hits[0]["doc_id"])
    same = [h for h in hits if _family(h["doc_id"]) == fam]
    return max(same, key=lambda h: str(h.get("effective_date") or ""))


def _data(o) -> Optional[dict]:
    return o.data


# ---------------------------------------------------------------- domain specialists
class HRHeuristic:
    search_tool = "search_hr_policies"
    read_tool = "read_document"

    def __init__(self, naive: bool = False):
        self.naive = naive

    def plan(self, view: View) -> dict:  # pragma: no cover - specialists run in react mode
        return {"goal": view.task[:80], "steps": [], "done_when": "answered"}

    def act(self, view: View) -> Action:
        from .domains import domain_scores, sentences
        q = " ".join(x for x in sentences(view.task) if domain_scores(x)["hr"] > 0) or view.task
        if re.search(r"\buntil\b|\bwhen\b", q, re.I):
            q += " expire"
        search = [o for o in view.obs if o.name == self.search_tool]
        reads = [o for o in view.obs if o.name == self.read_tool and o.data and o.data.get("text")]
        if search and search[-1].is_error:
            return Action("", [("give_up", {"reason": search[-1].text[:200], "missing": "a matching HR document"})])
        if not search:
            return Action("I need the HR policy that covers this.", [(self.search_tool, {"query": " ".join(keywords(q)[:8]), "k": 4})])
        if not reads:
            hit = pick_hit((search[-1].data or {}).get("hits", []), self.naive)
            if hit is None:
                return Action("", [("give_up", {"reason": "no HR document matched", "missing": "the policy name"})])
            return Action(f"The newest matching policy is {hit['doc_id']}; I will read it.",
                          [(self.read_tool, {"doc_id": hit["doc_id"]})])
        doc = reads[-1].data
        sents = best_sentences(doc["text"], q, 3)
        if not sents:
            return Action(f"I read {doc['id']} but found no sentence that answers this.")
        return Action(f"According to {doc['id']} (effective {doc.get('effective_date')}): " + " ".join(sents))


class OncallHeuristic:
    def plan(self, view: View) -> dict:  # pragma: no cover
        return {"goal": view.task[:80], "steps": [], "done_when": "answered"}

    def act(self, view: View) -> Action:
        low = view.task.lower()
        svc = next((s for s in sorted(SERVICES, key=len, reverse=True) if re.search(r"\b" + re.escape(s) + r"\b", low)), None)
        got = [o for o in view.obs if o.name == "get_oncall_for_service"]
        if svc is None:
            return Action("", [("give_up", {"reason": "The request names no production service.",
                                            "missing": "which service (e.g. flow-api, billing-service)?"})])
        if not got:
            return Action(f"I need the catalog row for {svc}.", [("get_oncall_for_service", {"service": svc})])
        if got[-1].is_error:
            return Action("", [("give_up", {"reason": got[-1].text[:200], "missing": "the exact service name"})])
        d = got[-1].data or {}
        parts = [f"{d.get('service')}: owned by {d.get('owner_team')} (team lead {d.get('team_lead')}), tier {d.get('tier')}."]
        if d.get("rotation"):
            sched = f" ({d['schedule']})" if d.get("schedule") else ""
            parts.append(f"On-call rotation: {d['rotation']}{sched}.")
        if d.get("shared_with"):
            parts.append(f"The rotation is shared with {d['shared_with']}.")
        if d.get("secondary"):
            parts.append(f"Secondary rotation: {d['secondary']}.")
        if d.get("channel"):
            parts.append(f"Business hours only, channel {d['channel']}.")
        parts.append(f"PagerDuty service: {d.get('pagerduty_service') or 'none'}. Coverage {d.get('coverage')}"
                     + (f", acknowledge within {d['ack_minutes']} minutes." if d.get("ack_minutes") else "."))
        if d.get("runbook"):
            parts.append(f"Runbook: {d['runbook']}.")
        parts.append("(Source: get_oncall_for_service, eng-service-catalog.)")
        return Action(" ".join(parts))


def inner_for(domain: str, **kw):
    if domain == "hr":
        return HRHeuristic(naive=kw.get("naive_docs", False))
    if domain == "oncall":
        return OncallHeuristic()
    return AcmeHeuristic(naive_docs=kw.get("naive_docs", False))


def _as_text(a: Action) -> Optional[str]:
    """A finished sub-answer: plain text, or a give_up turned into text. None = still working."""
    if not a.calls:
        return a.text
    give = next((args for n, args in a.calls if n == "give_up"), None)
    if give is not None:
        miss = give.get("missing")
        return f"I could not complete this part: {give.get('reason')}" + (f" Missing: {miss}" if miss else "")
    return None


class SpecialistHeuristic:
    """A specialist that sees the whole request but works only on its own domain's sentences."""

    def __init__(self, domain: str, **kw):
        self.domain = domain
        self.inner = inner_for(domain, **kw)

    def plan(self, view: View) -> dict:  # pragma: no cover
        return self.inner.plan(view)

    def act(self, view: View) -> Action:
        mine = text_for(view.task, self.domain) or view.task
        others = [d for d in domains_of(view.task) if d != self.domain]
        a = self.inner.act(replace(view, task=mine))
        if a.calls:
            return a
        if others:
            return Action(a.text + f" (I did not handle the {' and '.join(others)} part: not my domain.)")
        return a


class ComboHeuristic:
    """The single agent with all ten tools: one domain after another, in the order of the task."""

    def __init__(self, **kw):
        self.inners = {d: inner_for(d, **kw) for d in DOMAINS}

    def plan(self, view: View) -> dict:  # pragma: no cover
        return self.inners["it_access"].plan(view)

    def act(self, view: View) -> Action:
        doms = domains_of(view.task)
        if not doms:
            return Action(CLARIFY)
        if len(doms) == 1:
            return self.inners[doms[0]].act(replace(view, task=text_for(view.task, doms[0])))
        done: list[str] = []
        for d in doms:
            a = self.inners[d].act(replace(view, task=text_for(view.task, d)))
            t = _as_text(a)
            if t is None:
                return a
            done.append(t)
        return Action(" ".join(done))


CLARIFY = ("I am not sure what you need. Which person is this about, and what do you need: an HR policy answer, "
           "access to a system (which one, at what level?), or on-call information for a service?")


# ---------------------------------------------------------------- router
class RouterHeuristic:
    """plan(view) answers the router's structured-output request (RouteDecision)."""

    def __init__(self, multi_confidence: float = 0.7):
        self.multi_confidence = multi_confidence

    def plan(self, view: View) -> dict:
        doms = domains_of(view.task)
        if not doms:
            return {"reason": "No HR, access or on-call keywords; the request is ambiguous.", "routes": [],
                    "confidence": 0.2, "clarifying_question": CLARIFY}
        if len(doms) == 1:
            return {"reason": f"Only {doms[0]} topics.", "routes": doms, "confidence": 0.9, "clarifying_question": None}
        return {"reason": f"Touches {', '.join(doms)}; {doms[0]} comes first.", "routes": doms,
                "confidence": self.multi_confidence, "clarifying_question": None}

    def act(self, view: View) -> Action:  # pragma: no cover
        return Action(json.dumps(self.plan(view)))


# ---------------------------------------------------------------- supervisor
class SupervisorHeuristic:
    def __init__(self, parallel: bool = True, verify: bool = False, max_redelegate: int = 1):
        self.parallel = parallel
        self.verify = verify
        self.max_redelegate = max_redelegate

    def plan(self, view: View) -> dict:  # pragma: no cover
        return {"goal": view.task[:80], "steps": [], "done_when": "answered"}

    def act(self, view: View) -> Action:
        from .supervisor import evidence_conflicts
        doms = [d for d in domains_of(view.task) if f"delegate_to_{d}" in view.tools]
        if not doms:
            return Action(CLARIFY)
        latest: dict[str, dict] = {}
        count: dict[str, int] = {}
        for o in view.obs:
            if o.name.startswith("delegate_to_") and o.data:
                d = o.name[len("delegate_to_"):]
                latest[d] = o.data
                count[d] = count.get(d, 0) + 1
        pending = [d for d in doms if d not in latest]
        if pending:
            pick = pending if self.parallel else pending[:1]
            return Action("I will delegate " + ", ".join(pick) + ".",
                          [(f"delegate_to_{d}", {"task": text_for(view.task, d), "context": None}) for d in pick])
        notes, redo = [], []
        for d in doms:
            r = latest[d]
            probs = list(r.get("warnings") or [])
            if self.verify:
                probs += evidence_conflicts(r.get("answer", ""), r.get("evidence") or [])
            probs = list(dict.fromkeys(probs))
            if probs and count.get(d, 0) <= self.max_redelegate:
                redo.append((f"delegate_to_{d}", {"task": text_for(view.task, d),
                                                  "context": "Your previous answer conflicts with your own tool "
                                                             "results: " + "; ".join(probs) + ". Re-check and answer again."}))
            elif probs:
                notes.append(f"Warning about the {d} answer: " + "; ".join(probs) + ".")
        if redo:
            return Action("An answer conflicts with its evidence; I will ask again.", redo)
        return Action(" ".join([latest[d].get("answer", "") for d in doms] + notes))


# ---------------------------------------------------------------- handoffs
ORIG_RX = re.compile(r"<original_request>\s*(.*?)\s*</original_request>", re.S)
FACTS_RX = re.compile(r"<facts>\s*(.*?)\s*</facts>", re.S)
ACTIONS_RX = re.compile(r"<actions_taken>\s*(.*?)\s*</actions_taken>", re.S)
CONSTR_RX = re.compile(r"<constraints>\s*(.*?)\s*</constraints>", re.S)


def _bullets(rx, text: str) -> list[str]:
    m = rx.search(text)
    if not m:
        return []
    return [ln[2:].strip() for ln in m.group(1).splitlines() if ln.startswith("- ") and ln[2:].strip() != "(none)"]


class HandoffHeuristic:
    """role='triage' or a domain. lossy=True: the summary paraphrases the request and drops its
    constraints (what a careless summarizer does); after a transfer ERROR it writes a correct one."""

    def __init__(self, role: str, lossy: bool = False, **kw):
        self.role = role
        self.lossy = lossy
        self.inner = None if role == "triage" else inner_for(role, **kw)

    def plan(self, view: View) -> dict:  # pragma: no cover
        return {"goal": view.task[:80], "steps": [], "done_when": "answered"}

    def _summary(self, original: str, target: str, facts: list[dict], actions: list[str], fixed: bool) -> dict:
        constraints = [m.group(0).strip() for m in CONSTRAINT_RX.finditer(original)]
        req = original
        if self.lossy and not fixed:  # paraphrase: keep the first clause of each sentence, drop constraints
            req = " ".join(re.split(r",\s*but\b|;", s)[0].rstrip(".") + "." for s in re.split(r"(?<=[.?!])\s+", original))
            constraints = []
        return {"original_request": req, "goal": text_for(original, target) or original, "facts": facts,
                "actions_taken": actions, "constraints": constraints, "open_questions": []}

    def act(self, view: View) -> Action:
        m = ORIG_RX.search(view.task)
        original = m.group(1) if m else view.task
        doms = domains_of(original)
        transfer_errors = [o for o in view.obs if o.name.startswith("transfer_to_") and o.is_error]
        fixed = bool(transfer_errors)
        if self.role == "triage":
            if not doms:
                return Action(CLARIFY)
            target = doms[0]
            return Action(f"This starts with {target}; transferring.",
                          [(f"transfer_to_{target}", self._summary(original, target, [], [], fixed))])
        carried_facts = [{"claim": c.split(" (source:")[0], "source": (c.split("(source: ")[-1].rstrip(")") if "(source:" in c else "earlier agent")}
                         for c in _bullets(FACTS_RX, view.task)]
        carried_actions = _bullets(ACTIONS_RX, view.task)
        constraints = " ".join(_bullets(CONSTR_RX, view.task))
        # the receiving agent works from the request AS THE BRIEF STATES IT (+ its constraints)
        mine = text_for(original, self.role) or original
        a = self.inner.act(replace(view, task=(mine + " " + constraints).strip()))
        text = _as_text(a)
        if text is None:
            return a
        rest = doms[doms.index(self.role) + 1:] if self.role in doms else []
        if rest:
            created = [o.data for o in view.obs if o.name == "create_access_request" and o.data]
            actions = carried_actions + [f"Filed {c.get('id')} ({c.get('system')} {c.get('access_level')}, route "
                                         f"{c.get('route')})" for c in created]
            facts = carried_facts + [{"claim": text, "source": f"{self.role} agent"}]
            return Action(f"My part is done; {rest[0]} is next.",
                          [(f"transfer_to_{rest[0]}", self._summary(original, rest[0], facts, actions, fixed))])
        return Action(" ".join([f["claim"] for f in carried_facts] + [text]))


# ---------------------------------------------------------------- research fan-out
class ResearchHeuristic:
    """role: 'planner' (plan() -> SubQuestions), 'worker' (search -> read -> cite), 'synth' (join)."""

    def __init__(self, role: str, naive: bool = False):
        self.role = role
        self.naive = naive

    def plan(self, view: View) -> dict:
        qs = [s.strip() for s in re.split(r"(?<=\?)\s+", view.task) if s.strip()]
        return {"subquestions": [{"id": i + 1, "question": q, "why": "an independent part of the question"}
                                 for i, q in enumerate(qs)]}

    def act(self, view: View) -> Action:
        if self.role == "synth":
            answers = re.findall(r"<answer id=\"\d+\">\s*(.*?)\s*</answer>", view.prompt, re.S)
            return Action(" ".join(a for a in answers if a) or "The workers found nothing.")
        q = view.task
        search = [o for o in view.obs if o.name == "search_docs"]
        reads = [o for o in view.obs if o.name == "read_corpus_doc" and o.data]
        if not search:
            return Action("Searching.", [("search_docs", {"query": " ".join(keywords(q)[:8]), "k": 5})])
        if search[-1].is_error:
            return Action("", [("give_up", {"reason": search[-1].text[:160], "missing": None})])
        if not reads:
            hit = pick_hit((search[-1].data or {}).get("hits", []), self.naive)
            return Action(f"Reading {hit['doc_id']}.", [("read_corpus_doc", {"doc_id": hit["doc_id"]})])
        doc = reads[-1].data
        sents = best_sentences(doc["text"], q, 1)
        return Action((" ".join(sents) if sents else "No sentence answers this.") + f" [{doc['id']}]")


# ---------------------------------------------------------------- generator-critic
class WriterHeuristic:
    """Writes the employee-facing reply from the facts. The first draft has two planted flaws
    (it promises access, and omits what happens next); each later draft fixes the criteria the
    critic failed, read from the <feedback> block."""

    def plan(self, view: View) -> dict:  # pragma: no cover
        return {}

    def act(self, view: View) -> Action:
        m = re.search(r"<facts>\s*(\{.*?\})\s*</facts>", view.prompt, re.S)
        f = json.loads(m.group(1)) if m else {}
        fb = re.search(r"<feedback>(.*?)</feedback>", view.prompt, re.S)
        failed = set(re.findall(r"\b([a-z_]+): FAIL", fb.group(1))) if fb else set()
        prev = re.search(r"<previous_draft>(.*?)</previous_draft>", view.prompt, re.S)
        fixed = set(re.findall(r"<!--fixed:([a-z_,]*)-->", prev.group(1))[0].split(",")) if prev and "<!--fixed:" in prev.group(1) else set()
        fixed = {x for x in fixed if x} | failed
        name = f.get("employee_name", "there").split()[0]
        lines = [f"Hi {name}, your request {f.get('request_id')} for {f.get('access_level')} on {f.get('system')} "
                 f"is filed."]
        if "no_promise" in fixed:
            lines.append(f"It is not active yet: it needs approval from {f.get('approver')} first.")
        else:
            lines.append("Good news: you now have access, enjoy!")
        if "facts" in fixed and "no_promise" not in fixed:
            lines.append(f"Approver: {f.get('approver')}.")
        if "plain_language" in fixed:
            lines.append("Because this is admin access to production, it goes through a security review.")
        else:
            lines.append(f"Route: {f.get('route')}.")
        if "next_step" in fixed:
            lines.append(f"{f.get('approver')} reviews it within {f.get('review_days')} business days, and the "
                         f"access expires on {f.get('expires_at')}.")
        return Action(" ".join(lines) + f"<!--fixed:{','.join(sorted(fixed))}-->")


class CriticHeuristic:
    """plan(view) -> Review. Checks the 'llm' criteria with fake-only regexes from the rubric.
    mode: 'strict' (honest), 'lenient' (passes everything: a rubber stamp),
    'nitpick' (always fails plain_language: the loop never converges)."""

    FAKE_CHECKS = {
        "no_promise": (r"you now have access|access is (now )?(active|granted)|enjoy", False),
        "next_step": (r"business days", True),
        "plain_language": (r"security review", True),
    }

    def __init__(self, mode: str = "strict"):
        self.mode = mode

    def plan(self, view: View) -> dict:
        m = re.search(r"<draft>\s*(.*?)\s*</draft>", view.prompt, re.S)
        draft = re.sub(r"<!--.*?-->", "", m.group(1) if m else "")
        ids = re.findall(r"^- ([a-z_]+): ", view.prompt, re.M)
        out = []
        for cid in ids:
            rx, want = self.FAKE_CHECKS.get(cid, (None, True))
            ok = True if rx is None else (bool(re.search(rx, draft, re.I)) == want)
            if self.mode == "lenient":
                ok = True
            if self.mode == "nitpick" and cid == "plain_language":
                ok = False
            out.append({"id": cid, "passed": ok, "note": "ok" if ok else f"fails {cid}"})
        return {"criteria": out, "passed": all(c["passed"] for c in out), "summary": "fake critic"}

    def act(self, view: View) -> Action:  # pragma: no cover
        return Action(json.dumps(self.plan(view)))


def fake(policy, model: str = "fake-haiku") -> FakeLLM:
    return FakeLLM(policy, model=model)
