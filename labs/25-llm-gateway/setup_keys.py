"""Create the lab's virtual keys (once).

    python labs/25-llm-gateway/setup_keys.py           # refuses if keys already exist
    python labs/25-llm-gateway/setup_keys.py --force   # new keys; the old ones stop working

Writes two files under labs/25-llm-gateway/state/ (git-ignored):
  keys.yaml       what the gateway reads: one record per key, with its SHA-256, never the key
  demo_keys.env   the raw keys, so the lab scripts can use them. In a real company this
                  file would not exist: each team gets its key once, into its own secret store.

The four keys model four Acme apps:
  support-bot      team support      models: haiku             $2.00 / 30 days, soft $1.50, 120 rpm
  hr-assistant     team hr           models: haiku, sonnet     $5.00 / 30 days, floor: confidential
  eng-copilot      team engineering  models: haiku, sonnet, gpt $20.00 / 30 days, soft $15.00
  finance-reports  team finance      models: sonnet            $0.002 (tiny, for exercise 2), floor: confidential
"""

import argparse
import secrets
import sys

from lablib import DEMO_KEYS, STATE

from gatewaykit.keys import KeyStore

KEYS = [
    dict(key_id="support-bot", team="support", owner="noa.peretz@acme.example", models=["haiku"],
         max_budget_usd=2.0, soft_budget_usd=1.5, budget_period_days=30, rpm_limit=120,
         classification_floor="internal"),
    dict(key_id="hr-assistant", team="hr", owner="michal.bar@acme.example", models=["haiku", "sonnet"],
         max_budget_usd=5.0, soft_budget_usd=4.0, budget_period_days=30, classification_floor="confidential"),
    dict(key_id="eng-copilot", team="engineering", owner="yossi.katz@acme.example",
         models=["haiku", "sonnet", "gpt", "haiku-flaky"], max_budget_usd=20.0, soft_budget_usd=15.0,
         budget_period_days=30),
    dict(key_id="finance-reports", team="finance", owner="ronit.adler@acme.example", models=["sonnet"],
         max_budget_usd=0.002, soft_budget_usd=0.001, budget_period_days=30, classification_floor="confidential"),
]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--force", action="store_true")
    a = p.parse_args()
    store_path = STATE / "keys.yaml"
    if store_path.exists() and not a.force:
        sys.exit(f"{store_path} exists. Use --force to replace every key (old keys stop working).")
    STATE.mkdir(exist_ok=True)
    if store_path.exists():
        store_path.unlink()
    store = KeyStore.load(store_path)
    lines = ["# Raw lab keys. git-ignored. Never commit, never paste anywhere."]
    for spec in KEYS:
        spec = dict(spec)
        raw, vk = store.create(spec.pop("key_id"), spec.pop("team"), **spec)
        lines.append(f"KEY_{vk.key_id.upper().replace('-', '_')}={raw}")
        print(f"  {vk.key_id:16} team={vk.team:12} models={','.join(vk.models):28} budget=${vk.max_budget_usd}")
    lines.append(f"GATEWAY_MASTER_KEY=sk-gw-admin-{secrets.token_urlsafe(24)}")
    lines.append(f"GATEWAY_PII_SALT={secrets.token_hex(16)}")
    DEMO_KEYS.write_text("\n".join(lines) + "\n", encoding="utf-8")
    DEMO_KEYS.chmod(0o600)
    print(f"\nwrote {store_path.relative_to(STATE.parent.parent.parent)} (hashes) and "
          f"{DEMO_KEYS.relative_to(STATE.parent.parent.parent)} (raw keys, mode 600). Values are not printed.")


if __name__ == "__main__":
    main()
