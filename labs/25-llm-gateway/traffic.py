"""Exercise 6, part 1: a simulated week of Acme traffic through a gateway, into an audit log.

    python labs/25-llm-gateway/traffic.py
    python labs/25-llm-gateway/cost_report.py

Writes state/audit_traffic.jsonl (deleted and rebuilt on every run; same seed, same week).
Runs a gateway in this process with a simulated clock (Sunday 18 Oct to Saturday 24 Oct
2026, Acme's work week is Sunday to Thursday), its own mock servers on free ports, and
the lab's real keys and policy. Costs are computed with real per-token prices (Haiku-like,
Sonnet-like, GPT-mini-like) on the mock's token counts. Free.

The week contains a few things for you to find with cost_report.py. The script does not
tell you what they are; the report should.
"""

import random
from datetime import datetime, timezone

import httpx

from lablib import LAB, STATE, demo_key, load_env

from gatewaykit.audit import AuditLog
from gatewaykit.config import load_config
from gatewaykit.gateway import Gateway
from gatewaykit.keys import KeyStore
from gatewaykit.policy import load_policy
from mockllm import MockConfig, start_in_thread

START = datetime(2026, 10, 18, tzinfo=timezone.utc).timestamp()  # Sunday
DAY, HOUR = 86400, 3600
FILLER = ("Acme Flow lets teams automate approvals, onboarding and reporting workflows. "
          "This paragraph stands in for retrieved context from the knowledge base. ")
REPLY = " ".join(["Here is a summary of the relevant policy and the next steps for the requester."] * 12)


class SimClock:
    def __init__(self):
        self.t = START

    def __call__(self):
        return self.t


def prompt(rng, lo, hi, extra=""):
    n = rng.randint(lo, hi)
    body = (FILLER * (n // len(FILLER) + 1))[:n]
    return f"{extra}\n\n<context>{body}</context>\n\nQuestion: what should I do next?"


def main() -> None:
    load_env()
    rng = random.Random(25)
    keys = {k: demo_key(k) for k in ("support-bot", "hr-assistant", "eng-copilot", "finance-reports")}

    # Own mock servers on free ports, with a longer reply, so we never touch the lab's mocks.
    (srv_a, url_a), (srv_b, url_b) = start_in_thread(MockConfig(reply=REPLY)), start_in_thread(MockConfig(reply=REPLY))
    cfg = load_config(LAB / "gateway.yaml")
    for group in cfg.models.values():
        for d in group.deployments:
            d.base_url = url_a if d.base_url.endswith("8765") else url_b
    cfg.audit_path = STATE / "audit_traffic.jsonl"
    if cfg.audit_path.exists():
        cfg.audit_path.unlink()
    clock = SimClock()
    gw = Gateway(cfg, KeyStore.load(cfg.keys_path), load_policy(cfg.policy_path), audit=AuditLog(cfg.audit_path),
                 clock=clock, monotonic=clock)

    events = []  # (ts, key_name or raw key, model, prompt, headers_extra)

    def at(day, hour_lo, hour_hi):
        return START + day * DAY + rng.uniform(hour_lo, hour_hi) * HOUR

    for day in range(7):
        workday = day <= 4  # Sunday..Thursday
        for _ in range(40 if workday else 6):
            pii = rng.choice(["", "", "", "Customer: dana.levi@acme.example, 054-1234567.",
                              "Caller +972-3-555-0199 asked about invoice 123456789."])
            events.append((at(day, 6, 16), "support-bot", "haiku", prompt(rng, 1500, 4000, pii), {}))
        if workday:
            for _ in range(12):
                events.append((at(day, 7, 15), "hr-assistant", "sonnet",
                               prompt(rng, 2000, 6000, "Employee 039337423 asked about relocation."), {}))
            for _ in range(2):
                events.append((at(day, 7, 15), "hr-assistant", "gpt", prompt(rng, 500, 800), {}))
            for _ in range(25):
                events.append((at(day, 6, 17), "eng-copilot", rng.choice(["haiku", "haiku", "sonnet", "gpt"]),
                               prompt(rng, 1000, 5000), {}))
            for _ in range(3):
                events.append((at(day, 8, 12), "finance-reports", "sonnet", prompt(rng, 1500, 3000), {}))
    # a few requests labeled restricted
    for day in (1, 2, 4):
        events.append((at(day, 9, 11), "support-bot", "haiku", prompt(rng, 500, 900, "card 4580-1234-5678-9012"),
                       {"x-data-classification": "restricted"}))
    # random keys
    for _ in range(18):
        events.append((at(rng.randrange(7), 0, 24), "sk-gw-" + "".join(rng.choices("abcdefghijk0123456789", k=32)),
                       "haiku", "hi", {}))
    # Thursday night
    for _ in range(14):
        events.append((at(4, 0.3, 0.6), "eng-copilot", rng.choice(["claude-opus-5-5", "gpt-5", "o4"]), "hi", {}))
    for _ in range(140):
        events.append((at(4, 0.6, 3.5), "eng-copilot", "sonnet", prompt(rng, 7000, 9000), {}))
    events.sort(key=lambda e: e[0])

    outage = (START + 2 * DAY + 10 * HOUR, START + 2 * DAY + 10.7 * HOUR)  # Tuesday 10:00-10:42 UTC
    a_down = False
    for ts, who, model, text, extra in events:
        clock.t = ts
        down = outage[0] <= ts < outage[1]
        if down != a_down:
            httpx.post(f"{url_a}/__admin/config", json={"fail_rate": 1.0 if down else 0.0, "status": 503})
            a_down = down
        key = keys.get(who, who)
        gw.handle("openai", {"authorization": f"Bearer {key}", **extra},
                  {"model": model, "max_tokens": 400, "messages": [{"role": "user", "content": text}]})
    srv_a.shutdown()
    srv_b.shutdown()
    n = len(gw.audit.memory)
    print(f"wrote {n} audit records to {cfg.audit_path.relative_to(LAB.parents[1])}")
    print("next:  python labs/25-llm-gateway/cost_report.py")


if __name__ == "__main__":
    main()
