"""Add defense layers one at a time and measure attack success rate (ASR), false positives
(FPR), collateral harm to benign users and utility. Also runs each layer ALONE, so you see
what each one contributes by itself and what it misses.

    python labs/24-ai-security/defense_ladder.py                      # offline (simulated model)
    python labs/24-ai-security/defense_ladder.py --model anthropic:claude-haiku-5-5   # live, about $0.15 (9 configurations x 56 requests)
    python labs/24-ai-security/defense_ladder.py --mine               # with YOUR validator and ACL
    python labs/24-ai-security/defense_ladder.py --classifier-llm     # adds an LLM classifier rung (live)

The live run stops early if the running cost passes --max-cost (default $0.25).
"""

from __future__ import annotations

import argparse
import json

import _common  # noqa: F401
from _common import DEFAULT_LIVE, RESULTS, classifier_llm, make_model, mine_hooks

from guardkit import Answerer, build_layers, load_attacks, load_benign, run_suite  # noqa: E402

LADDER = [
    [],
    ["acl"],
    ["acl", "hierarchy"],
    ["acl", "hierarchy", "spotlight"],
    ["acl", "hierarchy", "spotlight", "classifier"],
    ["acl", "hierarchy", "spotlight", "classifier", "output"],
    ["acl", "hierarchy", "spotlight", "classifier", "output", "allowlist", "confirm"],
]
VARIANTS = [
    ("strict classifier", ["acl", "hierarchy", "spotlight", "classifier:strict", "output", "allowlist", "confirm"], "redact"),
    ("classifier drops whole docs", ["acl", "hierarchy", "spotlight", "classifier", "output", "allowlist", "confirm"], "drop"),
]
ALONE = ["acl", "hierarchy", "spotlight:static", "spotlight:datamark", "classifier", "output", "allowlist", "confirm"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="obedient")
    ap.add_argument("--mine", action="store_true")
    ap.add_argument("--classifier-llm", action="store_true", help=f"add a rung with LLMDetector ({DEFAULT_LIVE})")
    ap.add_argument("--alone", action="store_true", help="also run each layer alone with a live model (doubles the cost; always on offline)")
    ap.add_argument("--max-cost", type=float, default=0.25)
    a = ap.parse_args()

    model = make_model(a.model)
    hooks = mine_hooks(a.mine)
    llm = classifier_llm(DEFAULT_LIVE) if a.classifier_llm else None
    attacks, benign = load_attacks(), load_benign()
    runs = [("+".join(l) or "undefended", l, "redact") for l in LADDER] + VARIANTS
    if a.classifier_llm:
        runs.append(("LLM classifier instead", ["acl", "hierarchy", "spotlight", "classifier-llm", "output", "allowlist", "confirm"], "redact"))
    if a.model == "obedient" or a.alone:
        runs += [(f"ALONE {n}", [n], "redact") for n in ALONE]

    total, out = 0.0, []
    print(f"model: {a.model}{'  (SIMULATED, see guardkit/models.py)' if a.model == 'obedient' else ''}")
    for label, names, ua in runs:
        if label == "ALONE acl":
            print("\neach layer alone:")
        if label == "strict classifier":
            print("\nvariants of the full stack:")
        rep = run_suite(lambda: Answerer(model, build_layers(names, llm=llm, untrusted_action=ua, **hooks)),
                        attacks, benign, label=label)
        total += rep.cost_usd
        print(rep.summary_line())
        out.append(rep.to_dict())
        if total > a.max_cost:
            print(f"stopping: cost ${total:.3f} passed --max-cost {a.max_cost}")
            break
    print(f"\ntotal cost ${total:.4f}")
    RESULTS.mkdir(exist_ok=True)
    name = "ladder-" + a.model.replace(":", "_").replace("/", "_") + ("-mine" if a.mine else "") + ".json"
    (RESULTS / name).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"saved results/{name}")


if __name__ == "__main__":
    main()
