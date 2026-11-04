"""Exercise 6: what survives when a long conversation is squeezed into a token budget?

    python labs/04-context-engineering/compaction_eval.py --model fake --summarizer heuristic   # free
    python labs/04-context-engineering/compaction_eval.py                                     # live: Haiku 5.5
    python labs/04-context-engineering/compaction_eval.py --budget 300 --keep-last 2 --show
    python labs/04-context-engineering/compaction_eval.py --compact ref                       # the reference compact()

The conversation (labs/04-context-engineering/data/long_conversation.json, 56 messages, ~1.1K tokens):
an employee, in the FIRST 24 messages, mentions 12 facts about themselves, e.g.
  "My employee ID is A-4471", "My manager is Yossi Levi", "I have a sesame allergy",
  "My partner is due on 3 May", "My car's plate is 52-718-34";
then 32 messages of ordinary policy questions follow. After the conversation is fitted into
--budget tokens, the assistant is asked one probe question per fact ("What is my employee ID?")
and a reply counts if it contains the fact.

Strategies:
  full      the whole conversation (no budget): the ceiling
  truncate  sliding window: drop the oldest turns until it fits (ctxkit.compaction.truncate)
  compact   YOUR compact() from mine.py: summary of old turns + recent turns verbatim

Offline: --model fake is a string search (ctxkit.fake.ExtractiveLLM) that "answers" only if the
fact is still written somewhere in the prompt, so it measures retention, not understanding.
--summarizer heuristic keeps the employee's sentences with digits or "my/I am" in them.
Live: the same model writes the summary (llm_summarizer) and answers the probes.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
ROOT = LAB.parents[1]
sys.path[:0] = [str(ROOT), str(LAB)]
from ctxkit.compaction import llm_summarizer, messages_tokens, truncate  # noqa: E402
from ctxkit.fake import ExtractiveLLM, heuristic_summarizer  # noqa: E402
from ctxkit.tokens import count_tokens, tokenizer_name  # noqa: E402
from ctxkit.confirm import add_cost_args, confirm_paid, price_for, usd  # noqa: E402
from llmkit import LLM, ChatRequest, LLMError, Message, load_dotenv  # noqa: E402

SYSTEM = ("You are Acme Ltd.'s HR assistant, in an ongoing chat with one employee. Answer the employee's "
          "question about themselves from what they told you earlier in this conversation (it may appear "
          "inside <conversation_summary>). Reply in one short sentence. If they never told you, say you don't know.")
NEXT = "[[NEXT QUESTION]]"


def load():
    data = json.loads((LAB / "data" / "long_conversation.json").read_text(encoding="utf-8"))
    return [Message(m["role"], m["content"]) for m in data["messages"]], data["probes"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="anthropic:claude-haiku-5-5", help="or 'fake' (offline string search)")
    ap.add_argument("--summarizer", default="llm", choices=["llm", "heuristic"])
    ap.add_argument("--compact", default="mine", choices=["mine", "ref"])
    ap.add_argument("--budget", type=int, default=400, help="token budget for the history (o200k tokens)")
    ap.add_argument("--keep-last", type=int, default=4)
    ap.add_argument("--show", action="store_true", help="print the fitted history of each strategy")
    add_cost_args(ap, default_cap=0.25)
    a = ap.parse_args()
    load_dotenv(str(ROOT / ".env"))
    if a.compact == "ref":
        from ctxkit.compaction import compact
    else:
        from mine import compact

    convo, probes = load()
    fake = a.model == "fake"
    if not fake:
        full_tok = messages_tokens(convo, count_tokens) * 1.3
        price = price_for(a.model)
        # 3 strategies x probes, each at most the full history; plus the summarizer, which may be
        # called several times as compact() shrinks keep_last (each call re-reads the old part)
        n_probe = 3 * len(probes)
        n_sum = 6 if a.summarizer == "llm" else 0
        est = n_probe * usd(price, full_tok, 100) + n_sum * usd(price, full_tok, 400)
        confirm_paid(f"about {n_probe} probe calls + up to {n_sum} summary calls to {a.model}", est,
                     yes=a.yes, max_cost=a.max_cost, paid=price is not None)
    llm = ExtractiveLLM({p["question"]: p["answer"] for p in probes}) if fake else LLM(a.model)
    if a.summarizer == "llm" and fake:
        sys.exit("--model fake needs --summarizer heuristic (a fake model cannot write summaries)")
    summarize = heuristic_summarizer if a.summarizer == "heuristic" else llm_summarizer(llm)

    base = convo + [Message("user", NEXT)]
    print(f"conversation: {len(convo)} messages, {messages_tokens(convo, count_tokens):,} tokens ({tokenizer_name()}); "
          f"budget {a.budget}; keep_last {a.keep_last}; model {a.model}; summarizer {a.summarizer}\n")
    fitted = {"full": base, "truncate": truncate(base, a.budget, count_tokens)}
    try:
        fitted["compact"] = compact(base, a.budget, count_tokens, summarize, keep_last=a.keep_last)
    except NotImplementedError as e:
        print(f"(compact skipped: {e}; use --compact ref to see the reference)\n")
    summary_cost = sum(r.cost_usd or 0 for r in getattr(summarize, "results", []))

    rows = {}
    for name, hist in fitted.items():
        got, cost = [], 0.0
        for p in probes:
            msgs = hist[:-1] + [Message("user", hist[-1].text.replace(NEXT, p["question"]))]
            try:
                r = llm.complete(ChatRequest(messages=msgs, system=SYSTEM, max_tokens=100,
                                             effort=None if fake else "low"))
                ok = p["answer"].lower() in r.text.lower()
                cost += r.cost_usd or 0.0
                got.append((p["question"], ok, r.text.strip()))
            except LLMError as e:
                got.append((p["question"], False, f"ERROR {e}"))
        rows[name] = got
        toks = messages_tokens(hist, count_tokens)
        extra = f" + summary ${summary_cost:.4f}" if name == "compact" and summary_cost else ""
        print(f"{name:<9} history {len(hist):>3} msgs {toks:>6,} tok | facts recalled "
              f"{sum(ok for _, ok, _ in got):>2}/{len(probes)} | answers ${cost:.4f}{extra}")
        if a.show:
            for m in hist:
                print(f"    {m.role:>9}: {m.text[:160]!r}")
    print()
    names = list(rows)
    for i, p in enumerate(probes):
        marks = "  ".join(f"{n}:{'Y' if rows[n][i][1] else '-'}" for n in names)
        print(f"  {p['question']:<48} {marks}")
    print("\nlook at the misses: is the fact missing from the history, or there but not used?")


if __name__ == "__main__":
    main()
