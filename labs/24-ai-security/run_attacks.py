"""Run the attack suite (and the benign set) against the answerer with chosen defense layers.

    python labs/24-ai-security/run_attacks.py                                  # offline, undefended
    python labs/24-ai-security/run_attacks.py --layers acl,hierarchy,spotlight --show
    python labs/24-ai-security/run_attacks.py --model anthropic:claude-haiku-5-5   # live, about $0.02
    python labs/24-ai-security/run_attacks.py --trace i01 --layers spotlight   # full prompt of one attack
    python labs/24-ai-security/run_attacks.py --mine --layers acl,output       # YOUR validator and ACL

--model obedient is a SIMULATION (guardkit/models.py): a naive model that follows injected
instructions with probabilities we chose. Its ASR numbers show the shape of the trade-off,
they are not a measurement of any real model. Use a real model for that.
"""

from __future__ import annotations

import argparse
import json

import _common  # noqa: F401  (sys.path)
from _common import DEFAULT_LIVE, RESULTS, classifier_llm, make_model, mine_hooks

from guardkit import Answerer, User, build_layers, load_attacks, load_benign, run_suite  # noqa: E402
from guardkit.evaluate import attack_succeeded, user_for  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="obedient", help=f"obedient (offline sim) or an llmkit spec, e.g. {DEFAULT_LIVE}")
    ap.add_argument("--layers", default="", help="comma list: acl,hierarchy,spotlight[:static|random|datamark],"
                    "classifier[:strict],classifier-llm,output,allowlist,confirm")
    ap.add_argument("--untrusted", default="redact", choices=["redact", "drop"], help="what the classifier does to a flagged document")
    ap.add_argument("--classifier-model", default=DEFAULT_LIVE, help="model for classifier-llm")
    ap.add_argument("--mine", action="store_true", help="use mine.validate_output and mine.acl_allows")
    ap.add_argument("--only", default="", help="comma list of categories or ids to run")
    ap.add_argument("--no-benign", action="store_true")
    ap.add_argument("--show", action="store_true", help="print every row with layer events and the answer")
    ap.add_argument("--trace", default="", help="one attack or benign id: print system prompt, user prompt, raw and final output")
    ap.add_argument("--save", default="", help="file name under results/ for the JSON report")
    a = ap.parse_args()

    names = [n for n in a.layers.split(",") if n.strip()]
    llm = classifier_llm(a.classifier_model) if "classifier-llm" in names else None
    layers_kw = dict(llm=llm, untrusted_action=a.untrusted, **mine_hooks(a.mine))
    model = make_model(a.model)

    def make():
        return Answerer(model, build_layers(names, **layers_kw))

    attacks, benign = load_attacks(), load_benign()
    if a.trace:
        row = next((r for r in attacks + benign if r["id"] == a.trace), None)
        if row is None:
            raise SystemExit(f"no attack or benign row with id {a.trace}")
        tr = make().ask(row["question"], user_for(row), extra_docs=[row["inject_doc"]] if row.get("inject_doc") else (),
                        tool_result=row.get("tool_result"))
        print("=" * 30, "SYSTEM", "=" * 30, "\n" + tr.system)
        print("=" * 30, "USER MESSAGE", "=" * 30, "\n" + tr.prompt)
        print("=" * 30, "RAW MODEL OUTPUT", "=" * 30, "\n" + tr.raw_output)
        print("=" * 30, "WHAT THE USER SEES", "=" * 30, "\n" + tr.output)
        print("=" * 30, "LAYER EVENTS", "=" * 30)
        for e in tr.events or ["(none)"]:
            print(" -", e)
        if "success" in row:
            ok, why = attack_succeeded(row, tr)
            print("\nATTACK SUCCEEDED:" if ok else "\nattack failed", why)
        print(f"\ncost ${tr.cost_usd:.5f}, calls {tr.calls}")
        return

    if a.only:
        keep = {x.strip() for x in a.only.split(",")}
        attacks = [r for r in attacks if r["id"] in keep or r["category"] in keep]
        benign = [r for r in benign if r["id"] in keep or "benign" in keep]
    if a.no_benign:
        benign = []
    if not model.__class__.__name__.startswith("Obedient"):
        print(f"live run: {len(attacks) + len(benign)} requests to {a.model} (Haiku 5.5: roughly $0.0003 each)")
    rep = run_suite(make, attacks, benign, label="+".join(names) or "undefended",
                    progress=(lambda i: print(".", end="", flush=True)) if a.model != "obedient" else None)
    print()
    print(rep.format(show=a.show))
    if a.save:
        RESULTS.mkdir(exist_ok=True)
        path = RESULTS / a.save
        path.write_text(json.dumps(rep.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\nsaved {path}")


if __name__ == "__main__":
    main()
