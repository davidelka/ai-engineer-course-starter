"""Real adapters for the answer service ports.

LlmkitChatModel is the interesting one: llmkit (lesson 2) is itself an adapter
layer over three providers, and here it sits behind OUR port. Its job is
translation: our types in, provider call, our types and our errors out.
"""

from __future__ import annotations

import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from llmkit import LLM, LLMError, classify_error

from .domain import rank
from .types import Answer, Completion, ModelRejected, ModelUnavailable, Passage

ROOT = Path(__file__).resolve().parents[1]
ACME_FILES = [ROOT / "data" / "acme" / "hr_policies.md", ROOT / "data" / "acme" / "saas_access_policy.md"]


# ---------------------------------------------------------------- ChatModel
class LlmkitChatModel:
    """ChatModel port -> llmkit.LLM. Retries for transient errors already happen
    inside llm.complete (RetryPolicy); whatever still fails is translated here."""

    def __init__(self, llm: LLM):
        self.llm = llm
        self.name = f"{llm.provider.name}:{llm.model}"

    def complete(self, system: str, prompt: str, *, max_tokens: int = 512) -> Completion:
        try:
            r = self.llm.complete(prompt, system=system, max_tokens=max_tokens)
        except LLMError as exc:
            if classify_error(exc).retry:  # 429, 5xx, 529, timeout, network: still failing after retries
                raise ModelUnavailable(str(exc)) from exc
            raise ModelRejected(str(exc)) from exc  # 400, 401, 404...: the same request fails again
        if r.stop_reason == "refusal":
            raise ModelRejected("the model refused")
        if not r.text.strip():
            raise ModelUnavailable(f"empty reply (stop_reason={r.stop_reason})")
        return Completion(text=r.text, model=self.name, input_tokens=r.usage.input_tokens,
                          output_tokens=r.usage.output_tokens, cost_usd=r.cost_usd or 0.0)


# ---------------------------------------------------------------- Retriever
def load_passages(paths: Iterable[Path]) -> list[Passage]:
    """Split Acme markdown files into passages:
    <document source="x.md"> blocks -> one passage each (doc_id = x.md);
    otherwise "## " sections -> doc_id = file.md#section; otherwise the whole file."""
    out: list[Passage] = []
    for path in paths:
        text = Path(path).read_text(encoding="utf-8")
        docs = re.findall(r'<document source="([^"]+)">\s*(.*?)</document>', text, re.S)
        if docs:
            for source, body in docs:
                title, rest = _title(body)
                out.append(Passage(doc_id=source, title=title, text=rest))
            continue
        parts = re.split(r"^## +", text, flags=re.M)
        if len(parts) > 1:
            doc_title, _ = _title(parts[0])
            for part in parts[1:]:
                head, _, body = part.partition("\n")
                out.append(Passage(doc_id=f"{Path(path).name}#{head.strip()}", title=f"{doc_title}: {head.strip()}",
                                   text=" ".join(body.split())))
            continue
        title, rest = _title(text)
        out.append(Passage(doc_id=Path(path).name, title=title, text=rest))
    return out


def _title(block: str) -> tuple[str, str]:
    m = re.search(r"^# +(.+)$", block, re.M)
    title = re.sub(r"\s*\(.*?\)\s*$", "", m.group(1)).strip() if m else "Untitled"
    body = block[m.end():] if m else block
    return title, " ".join(body.split())


class KeywordRetriever:
    """Keyword search over passages loaded ONCE, at construction (the tangled
    version re-read every file on every question)."""

    def __init__(self, passages: list[Passage]):
        self.passages = list(passages)

    @classmethod
    def from_files(cls, paths: Iterable[Path] = ACME_FILES) -> "KeywordRetriever":
        return cls(load_passages(paths))

    @classmethod
    def from_passages(cls, passages: list[Passage]) -> "KeywordRetriever":
        return cls(passages)

    def search(self, query: str, k: int = 4) -> list[Passage]:
        return rank(query, self.passages, k)


# ---------------------------------------------------------------- AnswerStore
class JsonlAnswerStore:
    """Append-only JSONL file. First write wins; the index is rebuilt on open."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._index: dict[str, Answer] = {}
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    a = Answer.model_validate_json(line)
                    self._index.setdefault(a.request_id, a)

    def get(self, request_id: str) -> Optional[Answer]:
        return self._index.get(request_id)

    def put(self, answer: Answer) -> bool:
        with self._lock:
            if answer.request_id in self._index:
                return False
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(answer.model_dump_json() + "\n")
            self._index[answer.request_id] = answer
            return True


# ---------------------------------------------------------------- Clock
class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)

