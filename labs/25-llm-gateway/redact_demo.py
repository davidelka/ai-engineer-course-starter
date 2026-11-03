"""Exercise 4: your redact() on Acme-like messages, then inside a gateway: what the app sent,
what the provider received, what the app got back, and what the audit log kept.

    python labs/25-llm-gateway/redact_demo.py              # uses mine.redact
    python labs/25-llm-gateway/redact_demo.py --reference  # gatewaykit's version, to compare

Runs its own in-process gateway (no terminal 1 needed) with log_content: redacted and
an audit file of its own: state/audit_redact.jsonl. Free: mock servers only.
"""

import argparse
import json
import sys

from fastapi.testclient import TestClient

from lablib import LAB, STATE, build, demo_key, load_env, start_mocks

from gatewaykit.app import create_app

SAMPLES = [
    "Hi, I'm Dana (dana.levi@acme.example). Please give me read access to Jira.",
    "שלום, אני דנה, ת.ז. 123456782, טלפון 054-1234567. אפשר גישה ל-Jira?",
    "Customer called from +972-3-555-0199 about invoice 123456789 and order 2026-11-01.",
    "Forward to DANA.LEVI@acme.example and dana.levi@acme.example; backup 0541234567 / +972 54 123 4567.",
    "office 035550193",
]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--reference", action="store_true")
    a = p.parse_args()
    if a.reference:
        from gatewaykit.redact import redact
    else:
        sys.path.insert(0, str(LAB))
        from mine import redact

    print("A. redact() with all three types\n")
    for s in SAMPLES:
        r = redact(s)
        print(f"  in : {s}\n  out: {r.text}\n  counts={r.counts}\n")

    print("B. inside a gateway. hr-assistant (floor: confidential -> redact phone_il, il_id; emails pass)")
    load_env()
    start_mocks()
    audit_path = STATE / "audit_redact.jsonl"
    if audit_path.exists():
        audit_path.unlink()
    gw = build(LAB / "gateway.yaml", "" if a.reference else "redact")
    gw.cfg.log_content = "redacted"
    gw.audit.path = audit_path
    client = TestClient(create_app(gw))
    key = demo_key("hr-assistant")
    msg = "Employee 123456782 (054-1234567, michal@acme.example) asked about leave."
    for restore in (False, True):
        gw.cfg.restore_pii_in_response = restore
        r = client.post("/v1/chat/completions", headers={"authorization": f"Bearer {key}"},
                        json={"model": "haiku", "messages": [{"role": "user", "content": msg}]})
        answer = r.json()["choices"][0]["message"]["content"]
        print(f"\n  restore_pii_in_response={restore}")
        print(f"  app sent        : {msg}")
        print(f"  app got back    : {answer}")
        print(f"  x-gateway-redactions: {r.headers.get('x-gateway-redactions')}")
    print("  (the mock's answer echoes the first 80 characters of what it RECEIVED, so with restore=False")
    print("   the answer shows exactly what the provider saw)")

    rec = json.loads(audit_path.read_text(encoding="utf-8").splitlines()[-1])
    print("\nC. the audit record of the last request (no raw PII; fingerprints let you correlate):")
    for k in ("key_id", "classification", "redactions", "pii_fingerprints", "prompt_redacted"):
        print(f"  {k}: {json.dumps(rec.get(k), ensure_ascii=False)}")
    leaked = [v for v in ("123456782", "054-1234567") if v in audit_path.read_text(encoding="utf-8")]
    print(f"\n  raw values found in the audit file: {leaked or 'none'}")


if __name__ == "__main__":
    main()
