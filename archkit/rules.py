"""Architecture rules (lesson 19): checks that run on a Spec, like a linter.

Each rule is a function Spec -> list[Finding]. The first three are the ones the
lab asks you to write (mine.py); the reference versions live here.

  external_input_guarded  every path from an untrusted component to an LLM or a
                          tool passes through a guardrail
  llm_resilience          every LLM call has a timeout, retries and a fallback
  pii_classified          PII never reaches a third party without a classification step
  write_tools_approved    every path from an LLM to a write tool passes a human,
                          or the last hop states why it is exempt (a written policy)
  observability           tracing and eval exist as components; every LLM is traced
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from .spec import FALLBACK_MODES, Spec


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: str   # "error" | "warning"
    where: str      # component id, or "src->dst" for a flow
    message: str

    def __str__(self) -> str:
        return f"[{self.severity}] {self.rule} @ {self.where}: {self.message}"


# ---------------------------------------------------------------- rule 1
def rule_external_input_guarded(spec: Spec) -> list[Finding]:
    out: list[Finding] = []
    for src in spec.components:
        if spec.trust_of(src.id) != "untrusted":
            continue
        seen = {src.id}
        stack = [(src.id, [src.id])]
        reported: set[str] = set()
        while stack:
            node, path = stack.pop()
            for f in spec.outgoing(node):
                nxt = spec.component(f.dst)
                if nxt.kind == "guardrail":
                    continue  # this branch is checked
                if spec.trust_of(nxt.id) == "untrusted":
                    continue  # another untrusted component: it is checked as a source of its own
                if nxt.kind in ("llm", "tool"):
                    if nxt.id not in reported:
                        reported.add(nxt.id)
                        out.append(Finding("external_input_guarded", "error", nxt.id,
                                           f"untrusted input from {src.id} reaches {nxt.kind} {nxt.id} "
                                           f"without a guardrail: {' -> '.join(path + [nxt.id])}"))
                    continue
                if nxt.id not in seen:
                    seen.add(nxt.id)
                    stack.append((nxt.id, path + [nxt.id]))
    return out


# ---------------------------------------------------------------- rule 2
def rule_llm_resilience(spec: Spec) -> list[Finding]:
    out: list[Finding] = []
    R = "llm_resilience"
    for c in spec.by_kind("llm"):
        if not c.timeout_s or c.timeout_s <= 0:
            out.append(Finding(R, "error", c.id, f"{c.id} has no timeout_s: a hung call blocks the request forever"))
        if c.retry is None or c.retry.max_attempts < 2:
            out.append(Finding(R, "error", c.id, f"{c.id} has no retry (retry.max_attempts must be >= 2)"))
        if not c.fallback:
            out.append(Finding(R, "error", c.id, f"{c.id} has no fallback: what happens when the provider is down?"))
            continue
        if c.fallback == c.id:
            out.append(Finding(R, "error", c.id, f"{c.id} uses itself as its fallback"))
        elif c.fallback in FALLBACK_MODES:
            pass
        elif not spec.has_component(c.fallback):
            out.append(Finding(R, "error", c.id,
                               f"fallback {c.fallback!r} of {c.id} is not a component or one of {', '.join(FALLBACK_MODES)}"))
        else:
            fb = spec.component(c.fallback)
            if fb.kind == "llm" and fb.boundary == c.boundary:
                out.append(Finding(R, "warning", c.id,
                                   f"fallback {fb.id} runs in the same boundary ({c.boundary}) as {c.id}: "
                                   f"it will not help when that provider is down"))
    return out


# ---------------------------------------------------------------- rule 3
def rule_pii_classified(spec: Spec) -> list[Finding]:
    out: list[Finding] = []
    R = "pii_classified"
    for f in spec.flows:
        dst = spec.component(f.dst)
        if spec.trust_of(dst.id) != "third_party" or dst.pii_allowed:
            continue
        if f.classification == "pii":
            out.append(Finding(R, "error", f.key,
                               f"pii ({f.data}) is sent to third-party {dst.id}, which is not approved for PII"))
            continue
        # walk upstream from f.src; a classifier stops the walk on its branch
        seen = {f.src}
        stack = [f.src]
        hit = None
        while stack and hit is None:
            node = stack.pop()
            if spec.component(node).kind == "classifier":
                continue
            for g in spec.incoming(node):
                if g.classification == "pii":
                    hit = g
                    break
                if g.src not in seen:
                    seen.add(g.src)
                    stack.append(g.src)
        if hit is not None:
            out.append(Finding(R, "error", f.key,
                               f"pii from {hit.src} ({hit.data}) can reach third-party {dst.id} through "
                               f"{f.src} without a classifier on the way"))
    return out


# ---------------------------------------------------------------- rule 4
def rule_write_tools_approved(spec: Spec) -> list[Finding]:
    out: list[Finding] = []
    R = "write_tools_approved"
    reported: set[str] = set()
    for llm in spec.by_kind("llm"):
        seen = {llm.id}
        stack = [llm.id]
        while stack:
            node = stack.pop()
            for f in spec.outgoing(node):
                nxt = spec.component(f.dst)
                if nxt.kind == "human_approval":
                    continue
                if nxt.kind == "tool" and nxt.side_effects == "write":
                    if not f.approval_exempt and f.key not in reported:
                        reported.add(f.key)
                        out.append(Finding(R, "error", f.key,
                                           f"{llm.id} can trigger write tool {nxt.id} via {f.src} with no human "
                                           f"approval and no approval_exempt reason"))
                    continue
                if nxt.id not in seen:
                    seen.add(nxt.id)
                    stack.append(nxt.id)
    return out


# ---------------------------------------------------------------- rule 5
def rule_observability(spec: Spec) -> list[Finding]:
    out: list[Finding] = []
    R = "observability"
    if not spec.by_kind("observability"):
        out.append(Finding(R, "error", spec.system, "no observability component (tracing/logs/metrics)"))
    if not spec.by_kind("eval"):
        out.append(Finding(R, "error", spec.system, "no eval component: how will you know a change made it worse?"))
    for c in spec.by_kind("llm"):
        if not c.traced:
            out.append(Finding(R, "warning", c.id, f"{c.id} is not traced (traced: true)"))
    return out


RULES: dict[str, Callable[[Spec], list[Finding]]] = {
    "external_input_guarded": rule_external_input_guarded,
    "llm_resilience": rule_llm_resilience,
    "pii_classified": rule_pii_classified,
    "write_tools_approved": rule_write_tools_approved,
    "observability": rule_observability,
}


def check(spec: Spec, rules: Iterable[Callable[[Spec], list[Finding]]] = None) -> list[Finding]:
    out: list[Finding] = []
    for r in (rules or RULES.values()):
        out.extend(r(spec))
    return out
