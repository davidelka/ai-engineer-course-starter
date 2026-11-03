"""Exercise 7: an LLM reviews a spec for ambiguity, and we keep only grounded findings.

    python labs/06-spec-driven/spec_review.py --offline                     # free: mockllm + a fixture
    python labs/06-spec-driven/spec_review.py --model anthropic:claude-haiku-5-5
    python labs/06-spec-driven/spec_review.py --spec labs/06-spec-driven/spec/draft-vague.spec.md
    python labs/06-spec-driven/spec_review.py --model anthropic:claude-sonnet-5-5 --no-contract

--offline starts mockllm in this process with a HAND-WRITTEN reply from fixtures/ (not a
recording of a model), so the whole pipeline runs: llmkit -> structured output -> grounding.
The live run sends the spec (and the contract) once: roughly 7-8k input tokens, about one
tenth of a cent on Haiku 5.5.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
ROOT = LAB.parents[1]
sys.path[:0] = [str(ROOT), str(LAB)]
from llmkit import LLM, load_dotenv  # noqa: E402
from llmkit.structured import StructuredError, complete_structured  # noqa: E402
from spectools.lint import lint_spec  # noqa: E402
from spectools.review import REVIEW_SYSTEM, SpecReview, ground_findings, review_prompt  # noqa: E402
from spectools.spec import parse_spec  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", default=str(LAB / "spec" / "access-requests.spec.md"))
    ap.add_argument("--contract", default=str(LAB / "spec" / "openapi.yaml"))
    ap.add_argument("--no-contract", action="store_true", help="review the spec text alone")
    ap.add_argument("--model", default="anthropic:claude-haiku-5-5")
    ap.add_argument("--offline", action="store_true", help="mockllm with the fixture reply, no API key")
    ap.add_argument("--show-dropped", action="store_true")
    a = ap.parse_args()

    spec_path = Path(a.spec)
    spec_text = spec_path.read_text(encoding="utf-8")
    contract_text = "" if a.no_contract else Path(a.contract).read_text(encoding="utf-8")
    spec = parse_spec(spec_text)

    server = None
    mode = "native"
    if a.offline:
        from mockllm import MockConfig, start_in_thread
        fixture = LAB / "fixtures" / f"review_{spec_path.name.replace('.spec.md', '')}.json"
        if not fixture.exists():
            print(f"no offline fixture for {spec_path.name} (looked for {fixture.name})")
            return 2
        reply = json.dumps({"findings": json.loads(fixture.read_text(encoding="utf-8"))["findings"]})
        server, url = start_in_thread(MockConfig(reply=reply, ttft=0, tps=0))
        llm = LLM("mock:mock-model", base_url=url)
        mode = "prompt"  # with a schema in the request, mockllm would invent a sample object instead
        print(f"OFFLINE: mockllm returns the hand-written {fixture.name}\n")
    else:
        load_dotenv(str(ROOT / ".env"))
        llm = LLM(a.model)

    try:
        res = complete_structured(llm, review_prompt(spec_text, contract_text), SpecReview,
                                  system=REVIEW_SYSTEM, mode=mode, max_tokens=4000)
    except StructuredError as e:
        print(f"review failed at stage {e.stage}: {e}")
        return 1
    finally:
        if server:
            server.shutdown()

    review: SpecReview = res.value
    g = ground_findings(review, spec_text + "\n" + contract_text, spec.ids())
    lint_ids = {f.req_id for f in lint_spec(spec)}
    print(f"{len(review.findings)} findings from the model, {len(g.kept)} grounded, {len(g.dropped)} dropped\n")
    for i, f in enumerate(g.kept, 1):
        overlap = " (the linter also flags this requirement)" if f.requirement_id in lint_ids else ""
        print(f"{i}. [{f.problem}] {f.requirement_id or 'spec'}{overlap}")
        print(f"   quote:   {' '.join(f.quote.split())[:160]}")
        print(f"   why:     {f.explanation}")
        print(f"   rewrite: {f.suggested_rewrite}\n")
    if g.dropped:
        print("Dropped (not grounded in the text the model saw):")
        for f, why in g.dropped:
            print(f"  - {f.requirement_id or 'spec'}: {why}" + (f"  quote={f.quote[:80]!r}" if a.show_dropped else ""))
    cost = f"${res.cost_usd:.5f}" if res.cost_usd else "n/a"
    print(f"\n{res.input_tokens} in / {res.output_tokens} out tokens, cost {cost}, "
          f"{res.latency_s:.1f}s, {res.repairs} repair(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
