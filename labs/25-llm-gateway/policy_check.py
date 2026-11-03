"""Exercise 5: the full decision matrix of the policy, before you merge a change to it.

    python labs/25-llm-gateway/policy_check.py               # uses mine.decide
    python labs/25-llm-gateway/policy_check.py --reference   # gatewaykit's decide
    python labs/25-llm-gateway/policy_check.py --policy my_policy.yaml

For every classification and every deployment in gateway.yaml: allowed or denied, and
the rule that decided. Then, per model, the fallback chain that is left after the policy
filter: that is where the surprises are.
"""

import argparse
import sys

from lablib import LAB

from gatewaykit.config import load_config
from gatewaykit.policy import load_policy, redaction_types


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--reference", action="store_true")
    p.add_argument("--policy", default=str(LAB / "policy.yaml"))
    p.add_argument("--config", default=str(LAB / "gateway.yaml"))
    a = p.parse_args()
    if a.reference:
        from gatewaykit.policy import decide
    else:
        sys.path.insert(0, str(LAB))
        from mine import decide
    policy = load_policy(a.policy)
    cfg = load_config(a.config)
    deps = [d for g in cfg.models.values() for d in g.deployments]

    print(f"policy: {a.policy}\n")
    for c in policy["classifications"]:
        print(f"[{c}]  redact: {', '.join(redaction_types(policy, c)) or '-'}")
        for d in deps:
            dec = decide(policy, c, d)
            mark = "ALLOW" if dec.allowed else "deny "
            print(f"   {mark}  {d.id:20} {d.provider:9} {d.model:12} {d.region:7} <- {dec.rule}")
        print()

    print("Fallback chains after the policy filter (what the router may try, in order):")
    for name, group in cfg.models.items():
        for c in policy["classifications"]:
            chain = [d.id for d in group.deployments if decide(policy, c, d).allowed]
            note = "" if len(chain) > 1 else ("   <- NO fallback: one outage = 503" if chain else "   <- always 403")
            print(f"   {name:12} {c:13} {' -> '.join(chain) or '(none)'}{note}")


if __name__ == "__main__":
    main()
