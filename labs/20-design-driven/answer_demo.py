"""Exercise 3: the composition root. The ONLY place that knows which adapters exist.

    python labs/20-design-driven/answer_demo.py "How many vacation days do I get in my first year?"
    python labs/20-design-driven/answer_demo.py "..." --model mock:mock-model        # needs `python -m mockllm`
    python labs/20-design-driven/answer_demo.py "..." --model anthropic:claude-haiku-5-5
    python labs/20-design-driven/answer_demo.py "..." --model openai:gpt-5.4-mini
    python labs/20-design-driven/answer_demo.py "..." --store jsonl --request-id q-001   # run twice: the 2nd is a replay
    python labs/20-design-driven/answer_demo.py "..." --impl ref                       # the reference service

--model fake (the default) needs nothing: no server, no key, no cost.
Swapping the model, the store or the whole service is a change HERE, and
nowhere else. That is the claim of this lesson; this file is where you check it.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import uuid
from pathlib import Path

LAB = Path(__file__).resolve().parent
ROOT = LAB.parents[1]
sys.path[:0] = [str(ROOT), str(LAB)]
from designkit import fakes  # noqa: E402
from designkit.adapters import JsonlAnswerStore, KeywordRetriever, LlmkitChatModel, SystemClock  # noqa: E402
from designkit.types import AnswerRequest, BrainError  # noqa: E402
from llmkit import LLM, load_dotenv  # noqa: E402


def build_service(model_spec: str, store_kind: str, impl: str):
    if impl == "ref":
        from designkit.service import AnswerService
    else:
        from mine import AnswerService
    if model_spec == "fake":
        model = fakes.FakeChatModel()
    else:
        load_dotenv(str(ROOT / ".env"))
        model = LlmkitChatModel(LLM(model_spec))
    store = (JsonlAnswerStore(LAB / "results" / "answers.jsonl") if store_kind == "jsonl"
             else fakes.InMemoryAnswerStore())
    return AnswerService(model, KeywordRetriever.from_files(), store, SystemClock())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("question", nargs="?", default="How many vacation days do I get in my first year?")
    ap.add_argument("--model", default="fake", help="fake | mock:mock-model | anthropic:claude-haiku-5-5 | openai:...")
    ap.add_argument("--store", choices=["memory", "jsonl"], default="memory")
    ap.add_argument("--impl", choices=["mine", "ref"], default="mine")
    ap.add_argument("--email", default="dana@acme.example")
    ap.add_argument("--request-id", default=None, help="idempotency key; default: a fresh uuid")
    ap.add_argument("-v", "--verbose", action="store_true", help="show the service's log lines")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO if a.verbose else logging.WARNING, format="  log: %(message)s")

    svc = build_service(a.model, a.store, a.impl)
    req = AnswerRequest(request_id=a.request_id or str(uuid.uuid4()), user_email=a.email, question=a.question)
    try:
        ans = svc.answer(req)
    except BrainError as exc:
        print(f"{type(exc).__name__}: {exc}")
        return 2
    print(json.dumps(ans.model_dump(mode="json"), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
