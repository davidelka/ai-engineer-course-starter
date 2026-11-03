"""Reference AnswerService (exercise 3): the same behavior as legacy/tangled.py,
written against ports, with every dependency injected in the constructor.

The service owns the ORDER of things and the decisions; adapters own the I/O.
"""

from __future__ import annotations

import logging

from .domain import ANSWER_PROMPT_V1, NO_CONTEXT_TEXT, build_prompt, degraded_text, parse_citations, policy_check
from .ports import AnswerStore, ChatModel, Clock, Retriever
from .types import Answer, AnswerRequest, ModelUnavailable, PromptVersion, RetrieverUnavailable

log = logging.getLogger("brain.service")


class AnswerService:
    def __init__(self, model: ChatModel, retriever: Retriever, store: AnswerStore, clock: Clock,
                 *, prompt: PromptVersion = ANSWER_PROMPT_V1, k: int = 4, min_score: float = 0.2,
                 max_tokens: int = 512):
        self.model = model
        self.retriever = retriever
        self.store = store
        self.clock = clock
        self.prompt = prompt
        self.k = k
        self.min_score = min_score
        self.max_tokens = max_tokens

    def _make(self, req: AnswerRequest, status: str, text: str, **kw) -> Answer:
        return Answer(request_id=req.request_id, status=status, text=text, created_at=self.clock.now(), **kw)

    def _keep(self, answer: Answer) -> Answer:
        """Store and return. If another call stored this request_id first, return theirs."""
        if self.store.put(answer):
            return answer
        return self.store.get(answer.request_id) or answer

    def answer(self, req: AnswerRequest) -> Answer:
        # 1. Idempotency: a retry of a finished request returns the same answer, at no cost.
        existing = self.store.get(req.request_id)
        if existing is not None:
            log.info("replay request_id=%s status=%s", req.request_id, existing.status)
            return existing

        # 2. Policy BEFORE anything leaves the building (search, model call, logs with content).
        decision = policy_check(req.question, req.user_email)
        if not decision.allowed:
            log.info("refused request_id=%s rule=%s", req.request_id, decision.rule)
            return self._keep(self._make(req, "refused", decision.reason))

        # 3. Retrieval. A transient search failure degrades; it is not stored, so a retry can succeed.
        try:
            passages = [p for p in self.retriever.search(req.question, self.k) if p.score >= self.min_score]
        except RetrieverUnavailable as exc:
            log.warning("retriever unavailable request_id=%s: %s", req.request_id, exc)
            return self._make(req, "degraded", degraded_text([]))
        if not passages:
            return self._keep(self._make(req, "no_context", NO_CONTEXT_TEXT))

        # 4. Model. Transient -> degrade (not stored). Permanent (ModelRejected) -> propagate: it is a bug.
        try:
            completion = self.model.complete(self.prompt.template, build_prompt(req.question, passages),
                                             max_tokens=self.max_tokens)
        except ModelUnavailable as exc:
            log.warning("model unavailable request_id=%s: %s", req.request_id, exc)
            return self._make(req, "degraded", degraded_text(passages), citations=[p.doc_id for p in passages])

        # 5. Keep only citations to passages we actually sent.
        cites = parse_citations(completion.text, {p.doc_id for p in passages})
        answer = self._make(req, "answered", completion.text, citations=cites, prompt_version=self.prompt.ref,
                            model=completion.model, cost_usd=completion.cost_usd)
        log.info("answered request_id=%s citations=%d cost=%.6f", req.request_id, len(cites), completion.cost_usd)
        return self._keep(answer)
