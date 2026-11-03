"""ExtractiveAnswerer: a free, offline stand-in for the generation step.

It is NOT a language model. It reads the <source> blocks of a ragkit prompt, scores every
sentence by how many (analyzed) question terms it contains, and answers with the best one or
two sentences, each followed by its source number. If no sentence shares enough terms with
the question it answers "not in the documents".

So an offline run measures retrieval honestly (was the answer sentence in the prompt at all,
and in which source?), and exercises the citation plumbing. It cannot reason, combine two
sources, resolve a version conflict or translate: the live run with Haiku shows those.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html import unescape

from llmkit import ChatRequest, ChatResult, Usage

from .chunking.strategies import sentence_spans
from .rag import NOT_FOUND
from .retrieval.analyzer import analyze
from .tokens import get_tokenizer

SOURCE_RE = re.compile(r"<source id=\"(\d+)\"[^>]*>\n(.*?)\n</source>", re.S)
QUESTION_RE = re.compile(r"<question>(.*?)</question>", re.S)


@dataclass
class ExtractiveAnswerer:
    min_overlap: float = 0.34    # share of question terms a sentence must contain
    max_sentences: int = 2
    model: str = "fake-extractive"

    def complete(self, req: ChatRequest, **_) -> ChatResult:
        prompt = req.messages[-1].text
        m = QUESTION_RE.search(prompt)
        question = unescape(m.group(1)) if m else prompt
        q_terms = set(analyze(question))
        scored = []
        for sid, body in SOURCE_RE.findall(prompt):
            body = unescape(body)
            for a, b in sentence_spans(body):
                sent = body[a:b].strip().lstrip("#-| ").strip()
                if len(sent) < 12:
                    continue
                terms = set(analyze(sent))
                hit = len(q_terms & terms) / max(1, len(q_terms))
                scored.append((hit, -int(sid), sent, sid))
        scored.sort(reverse=True)
        best = [s for s in scored if s[0] >= self.min_overlap][: self.max_sentences]
        text = " ".join(f"{s[2]} [{s[3]}]" for s in best) if best else NOT_FOUND
        tok = get_tokenizer()
        usage = Usage(input_tokens=tok.count(req.system_text + prompt), output_tokens=tok.count(text))
        return ChatResult(text=text, stop_reason="end", usage=usage, provider="fake",
                          model=self.model, cost_usd=0.0)
