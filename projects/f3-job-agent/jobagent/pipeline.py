"""One run of the agent for one schedule slot.

    claim slot -> fetch (per source, Airtable only in the morning) -> new posts only
      -> per post: repost check -> injection screen -> extract (cached) -> validate
         -> per job: fingerprint -> exact / near duplicate -> score
      -> digest of undelivered jobs -> deliver -> mark delivered -> drafts -> report

Every step is a span (obskit, OpenTelemetry). One trace per run, one child span per post,
LLM calls as GenAI spans with tokens and cost. Post text is redacted before it reaches any
span attribute.

The functions that milestones replace (validate, fingerprint, near-duplicate, scorer) are
injected, so the same pipeline runs with your mine.py versions or with the references.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Optional, Sequence

from . import dedup, match, safety
from .delivery import ConsoleDelivery, DeliveryPort, DraftPort, Receipt, draft_for
from .digest import Digest, build_digest
from .extract import PROMPT_VERSION, ExtractResult, Extractor, text_hash
from .models import Finding, Job, PostExtraction, RawPost
from .prefs import Preferences
from .schedule import TZ, is_morning
from .store import Store


def _lazy(name: str) -> Callable:
    from .hooks import _lazy as lazy
    return lazy(name)


@dataclass
class Hooks:
    """The replaceable pieces: your mine.py functions (see jobagent/hooks.py)."""

    validate_job: Callable = field(default_factory=lambda: _lazy("validate_job"))
    fingerprint: Callable = field(default_factory=lambda: _lazy("job_fingerprint"))
    near_duplicate: Callable = field(default_factory=lambda: _lazy("near_duplicate"))
    score_job: Callable = field(default_factory=lambda: _lazy("score_job"))


@dataclass
class PostOutcome:
    post: RawPost
    repost_of: Optional[str] = None
    flagged: bool = False
    flag_reasons: list[str] = field(default_factory=list)
    extraction: Optional[PostExtraction] = None
    result: Optional[ExtractResult] = None
    jobs: list[Job] = field(default_factory=list)


@dataclass
class RunResult:
    run_id: str
    skipped: bool = False
    reason: str = ""
    posts_in: int = 0
    posts: list[PostOutcome] = field(default_factory=list)
    new_jobs: list[Job] = field(default_factory=list)
    digest: Optional[Digest] = None
    receipt: Optional[Receipt] = None
    drafts: list[Receipt] = field(default_factory=list)
    cost_usd: float = 0.0
    llm_calls: int = 0
    spans: list[dict] = field(default_factory=list)
    report_path: Optional[str] = None
    error: Optional[str] = None

    @property
    def posts_new(self) -> int:
        return len(self.posts)

    @property
    def all_jobs(self) -> list[Job]:
        return [j for o in self.posts for j in o.jobs]


class Pipeline:
    def __init__(self, *, sources: Sequence, extractor: Extractor, prefs: Preferences, store: Store,
                 delivery: Optional[DeliveryPort] = None, drafts: Optional[DraftPort] = None,
                 hooks: Optional[Hooks] = None, results_dir: Optional[Path] = None, trace: bool = True,
                 send_empty: bool = False, first_run_lookback: timedelta = timedelta(hours=24)):
        self.sources = list(sources)
        self.extractor = extractor
        self.prefs = prefs
        self.store = store
        self.delivery = delivery or ConsoleDelivery()
        self.drafts = drafts
        self.hooks = hooks or Hooks()
        self.results_dir = Path(results_dir) if results_dir else None
        self.trace = trace
        self.send_empty = send_empty
        self.first_run_lookback = first_run_lookback

    # ------------------------------------------------------------ helpers
    def _window(self, slot_dt: datetime, source_name: str) -> datetime:
        """Posts newer than this go into the run. Morning-only sources look back a full day."""
        if source_name in self.prefs.morning_only_sources:
            return slot_dt - timedelta(days=1)
        last = self.store.last_done()
        if last and last < slot_dt.strftime("%Y-%m-%dT%H:%M"):
            return datetime.fromisoformat(last).replace(tzinfo=TZ)  # everything since the last finished run
        return slot_dt - self.first_run_lookback  # first run ever: one day back, not the whole history

    def _extract(self, post: RawPost) -> ExtractResult:
        h = text_hash(post.text)
        cached = self.store.cached_extraction(h, PROMPT_VERSION, self.extractor.name)
        if cached is not None:
            return ExtractResult(PostExtraction.model_validate(cached), cached=True, extractor=self.extractor.name)
        r = self.extractor.extract(post)
        if r.error is None:
            self.store.cache_extraction(h, PROMPT_VERSION, self.extractor.name, r.extraction.model_dump(), r.cost_usd)
        return r

    # ------------------------------------------------------------ the run
    def run(self, slot: str, *, force: bool = False) -> RunResult:
        from obskit import agent_span, setup_tracing, span

        tracing = setup_tracing("job-agent", memory=True, redact=safety.redact_for_span,
                                jsonl=str(self.results_dir / "traces.jsonl") if (self.results_dir and self.trace) else None)
        res = RunResult(run_id=slot)
        if not self.store.claim_run(slot, force=force):
            res.skipped, res.reason = True, "slot already done (or running)"
            tracing.shutdown()
            return res
        slot_dt = datetime.fromisoformat(slot).replace(tzinfo=TZ)
        todo = None
        try:
            with agent_span("job_agent_run", workflow=True, attributes={"job_agent.slot": slot,
                                                                         "job_agent.extractor": self.extractor.name}) as root:
                posts = self._fetch(slot, slot_dt, span)
                res.posts_in = len(posts)
                run_texts: list[tuple[str, str]] = []
                recent = self.store.recent_texts()
                run_jobs: list[Job] = []
                for post in posts:
                    res.posts.append(self._process(post, slot, run_texts, recent, run_jobs, span))
                res.new_jobs = run_jobs
                res.cost_usd = sum(o.result.cost_usd for o in res.posts if o.result and not o.result.cached)
                res.llm_calls = sum(o.result.attempts for o in res.posts if o.result and not o.result.cached)
                self._deliver(res, slot, span)
                root.set_attribute("job_agent.posts_new", res.posts_new)
                root.set_attribute("job_agent.jobs_new", len(res.new_jobs))
                root.set_attribute("job_agent.cost_usd", round(res.cost_usd, 6))
            status = "done"
        except Exception as exc:  # the slot stays retryable; the error is visible in /runs
            res.error = f"{type(exc).__name__}: {exc}"
            status = "failed"
            if type(exc).__name__ == "MilestoneTodo":   # a function of mine.py not written yet: stop loudly
                todo = exc
        tracing.flush()
        res.spans = list(tracing.memory.spans) if tracing.memory else []
        tracing.shutdown()
        if self.results_dir:
            from .report import write_report

            res.report_path = str(write_report(res, self.results_dir))
        self.store.finish_run(slot, status=status, posts_in=res.posts_in, posts_new=res.posts_new,
                              jobs_new=len(res.new_jobs), matches=len(res.digest.matches) if res.digest else 0,
                              cost_usd=res.cost_usd, extractor=self.extractor.name,
                              digest=res.digest.text if res.digest else None, error=res.error,
                              report_path=res.report_path)
        if todo is not None:
            raise todo
        return res

    def _fetch(self, slot: str, slot_dt: datetime, span) -> list[RawPost]:
        out: list[RawPost] = []
        for src in self.sources:
            if src.name in self.prefs.morning_only_sources and not is_morning(slot):
                continue
            since = self._window(slot_dt, src.name)
            with span(f"fetch {src.name}", type="retrieval", attributes={"job_agent.source": src.name}) as sp:
                got = [p for p in src.fetch(since) if p.ts is None or p.ts <= slot_dt]
                new = [p for p in got if not self.store.seen_post(p.key)]
                sp.set_attribute("job_agent.fetched", len(got))
                sp.set_attribute("job_agent.new", len(new))
            out += new
        out.sort(key=lambda p: (p.ts or slot_dt, p.key))
        return out

    def _process(self, post: RawPost, slot: str, run_texts, recent, run_jobs: list[Job], span) -> PostOutcome:
        o = PostOutcome(post=post)
        red = safety.redact(post.text)
        with span("process_post", attributes={"job_agent.post_key": post.key, "job_agent.source": post.source,
                                              "job_agent.channel": post.channel, "job_agent.chars": len(post.text)}) as sp:
            o.repost_of = dedup.find_repost(red, run_texts + recent)
            self.store.add_post(post.key, text_hash(post.text), post.source, post.channel,
                                post.ts.isoformat() if post.ts else None, slot, o.repost_of, red)
            if o.repost_of:
                sp.set_attribute("job_agent.repost_of", o.repost_of)
                return o
            run_texts.append((post.key, red))
            with span("screen", type="guard") as g:
                v = safety.screen_post(post.text)
                o.flagged, o.flag_reasons = v.flagged, v.reasons
                g.set_attribute("guard.flagged", v.flagged)
                g.set_attribute("guard.reasons", ",".join(v.reasons))
            o.result = self._extract(post)
            ex, per_job = safety.validate_extraction(o.result.extraction, post.text, self.hooks.validate_job)
            o.extraction = ex
            sp.set_attribute("job_agent.jobs", len(ex.jobs))
            sp.set_attribute("job_agent.extraction_cached", o.result.cached)
            if o.result.error:
                sp.set_attribute("job_agent.extract_error", o.result.error)
            known = self.store.all_postings()
            for i, (posting, findings) in enumerate(zip(ex.jobs, per_job)):
                job = Job(posting=posting, post_key=post.key, job_index=i, source=post.source, channel=post.channel,
                          findings=findings, posted_at=post.ts)
                job.posting.posted_at = post.ts.isoformat() if post.ts else None
                job.suspicious = (o.flagged or ex.injection_suspected
                                  or any(f.severity == "block" for f in findings))
                if o.flagged or ex.injection_suspected:
                    job.findings.append(Finding(code="injection_suspected", detail=",".join(o.flag_reasons),
                                                severity="block"))
                job.fingerprint = self.hooks.fingerprint(posting)
                if self.store.known_job(job.fingerprint) or any(j.fingerprint == job.fingerprint for j in run_jobs):
                    job.duplicate_of = job.fingerprint
                else:
                    for fp, other in known:
                        from .models import JobPosting
                        if self.hooks.near_duplicate(posting, JobPosting.model_validate(other)):
                            job.duplicate_of = fp
                            break
                    else:
                        for other in run_jobs:
                            if self.hooks.near_duplicate(posting, other.posting):
                                job.duplicate_of = other.fingerprint
                                break
                match.apply_score(job, self.prefs, self.hooks.score_job)
                o.jobs.append(job)
                if job.duplicate_of is None:
                    run_jobs.append(job)
                    self.store.add_job(job, slot)
        return o

    def _deliver(self, res: RunResult, slot: str, span) -> None:
        pending = self.store.undelivered()  # this run's new jobs + any from a failed delivery before
        drafted: set[str] = set()
        if self.drafts:
            for j in pending:
                if j.tier != "match":
                    continue
                d = draft_for(j, self.prefs.owner)
                if d is None:
                    continue
                with span("create_draft", type="tool", attributes={"job_agent.adapter": self.drafts.name}):
                    r = self.drafts.create_draft(d)
                res.drafts.append(r)
                if r.ok:
                    drafted.add(j.fingerprint)
        res.digest = build_digest(slot, pending, category_order=list(self.prefs.targets), posts_seen=res.posts_new,
                                  drafted=drafted, show_others=self.prefs.show_other_jobs)
        if res.digest.empty and not self.send_empty:
            return
        with span("deliver", type="tool", attributes={"job_agent.adapter": self.delivery.name,
                                                      "job_agent.digest_jobs": res.digest.job_count}):
            res.receipt = self.delivery.send(res.digest)
        if res.receipt.ok:
            self.store.mark_delivered([j.fingerprint for j in pending], slot)
