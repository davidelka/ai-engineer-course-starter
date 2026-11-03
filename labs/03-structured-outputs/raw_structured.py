"""Exercise 1: native structured output over plain HTTP, no SDK, no llmkit loop.

    python labs/03-structured-outputs/raw_structured.py                       # Claude, native schema
    python labs/03-structured-outputs/raw_structured.py --twice               # 2nd call: grammar is cached
    python labs/03-structured-outputs/raw_structured.py --bad-schema          # minLength=2 on `tool`: rejected, ignored or enforced?
    python labs/03-structured-outputs/raw_structured.py --bad-schema minlength40   # minLength=40: tells "ignored" from "enforced"
    python labs/03-structured-outputs/raw_structured.py --bad-schema pattern       # the email pattern, sent raw (400 in our Oct 2026 test)
    python labs/03-structured-outputs/raw_structured.py --bad-schema addprops      # additionalProperties: true on the root
    python labs/03-structured-outputs/raw_structured.py --provider openai --show-body
    python labs/03-structured-outputs/raw_structured.py --mock                # free

Prints where the schema goes in the request, the raw reply text, and whether
it parses and validates against the Pydantic model.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx

LAB = Path(__file__).resolve().parent
ROOT = LAB.parents[1]
sys.path[:0] = [str(ROOT), str(LAB)]
from acme_schema import AccessRequest  # noqa: E402
from llmkit import load_dotenv  # noqa: E402
from llmkit.structured import provider_schema  # noqa: E402

MESSAGE = ("Hi, I'm Dana Levi (dana.levi@acme.example). Could I get read access to the "
           "Platform team Confluence space for 30 days? Need it to review the on-call runbooks.")
SYSTEM = "Extract the access request. Use null for anything the message does not state."
MODELS = {"anthropic": "claude-haiku-5-5", "openai": "gpt-5.4-mini", "gemini": "gemini-3.6-flash"}
MOCK = os.environ.get("MOCKLLM_URL", "http://127.0.0.1:8765")


def build(provider: str, model: str, key: str, schema: dict):
    if provider == "anthropic":
        return ("https://api.anthropic.com/v1/messages",
                {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                {"model": model, "max_tokens": 1024, "system": SYSTEM,
                 "messages": [{"role": "user", "content": MESSAGE}],
                 "output_config": {"format": {"type": "json_schema", "schema": schema}}})
    if provider == "openai":
        return ("https://api.openai.com/v1/responses",
                {"authorization": f"Bearer {key}", "content-type": "application/json"},
                {"model": model, "instructions": SYSTEM, "input": MESSAGE, "max_output_tokens": 1500,
                 "reasoning": {"effort": "low"},
                 "text": {"format": {"type": "json_schema", "name": "AccessRequest", "schema": schema, "strict": True}}})
    return (f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            {"x-goog-api-key": key, "content-type": "application/json"},
            {"systemInstruction": {"parts": [{"text": SYSTEM}]},
             "contents": [{"role": "user", "parts": [{"text": MESSAGE}]}],
             "generationConfig": {"responseMimeType": "application/json", "responseJsonSchema": schema}})


def reply_text(provider: str, body: dict) -> tuple[str, str]:
    if provider == "anthropic":
        return "".join(b.get("text", "") for b in body.get("content", []) if b.get("type") == "text"), body.get("stop_reason", "")
    if provider == "openai":
        parts = [p for i in body.get("output", []) if i.get("type") == "message" for p in i.get("content", [])]
        return "".join(p.get("text", "") or p.get("refusal", "") for p in parts), body.get("status", "")
    c = (body.get("candidates") or [{}])[0]
    return "".join(p.get("text", "") for p in (c.get("content") or {}).get("parts", [])), c.get("finishReason", "")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=list(MODELS), default="anthropic")
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--twice", action="store_true", help="send the same request twice and compare latency")
    ap.add_argument("--bad-schema", nargs="?", const="minlength", choices=["minlength", "minlength40", "pattern", "addprops"],
                    help="send a keyword the docs list as unsupported, and see what the provider really does")
    ap.add_argument("--show-body", action="store_true")
    a = ap.parse_args()
    load_dotenv(str(ROOT / ".env"))

    schema, notes = provider_schema(AccessRequest, a.provider)
    if a.bad_schema == "minlength":
        schema["properties"]["tool"]["minLength"] = 2
        print("added minLength=2 to `tool` on purpose")
    elif a.bad_schema == "minlength40":
        schema["properties"]["tool"]["minLength"] = 40
        print("added minLength=40 to `tool` on purpose (real tool names are much shorter)")
    elif a.bad_schema == "pattern":
        schema["properties"]["requester_email"]["anyOf"][0]["pattern"] = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
        print("put the email pattern back into the schema on purpose")
    elif a.bad_schema == "addprops":
        schema["additionalProperties"] = True
        print("set additionalProperties: true on the root on purpose")
    if a.bad_schema:
        print("possible outcomes: HTTP 400 = the provider rejects the keyword; HTTP 200 = it accepted it,\n"
              "and then the reply shows whether it was enforced or silently ignored\n")
    env = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY"}[a.provider]
    key = "mock-key" if a.mock else os.environ.get(env, "")
    if not key:
        sys.exit(f"{env} is not set in .env (or use --mock)")
    url, headers, body = build(a.provider, "mock-model" if a.mock else MODELS[a.provider], key, schema)
    if a.mock:
        url = MOCK + url[url.index("/v1"):]
    where = {"anthropic": "output_config.format", "openai": "text.format", "gemini": "generationConfig.responseJsonSchema"}
    print(f"POST {url}\nschema sent in: {where[a.provider]}")
    for n in notes:
        print(f"  schema note: {n}")
    if a.show_body:
        print(json.dumps(body, indent=2, ensure_ascii=False)[:3000])

    with httpx.Client(timeout=120) as http:
        for i in range(2 if a.twice else 1):
            t0 = time.perf_counter()
            r = http.post(url, headers=headers, json=body)
            dt = time.perf_counter() - t0
            print(f"\n--- call {i + 1}: HTTP {r.status_code} in {dt:.2f}s")
            if r.status_code >= 400:
                print(r.text[:800])
                return
            text, stop = reply_text(a.provider, r.json())
            print(f"stop: {stop}\nraw reply text:\n{text}")
            try:
                obj = AccessRequest.model_validate_json(text)
                print("\nPydantic: VALID")
                if a.bad_schema in ("minlength", "minlength40"):
                    need = 2 if a.bad_schema == "minlength" else 40
                    print(f"len(tool) = {len(obj.tool)}, the schema asked for at least {need}: "
                          + ("met" if len(obj.tool) >= need else "NOT met, so the keyword was accepted but not enforced"))
                print(json.dumps(obj.model_dump(), indent=2, ensure_ascii=False))
            except Exception as exc:  # noqa: BLE001
                print(f"\nPydantic: INVALID\n{exc}")


if __name__ == "__main__":
    main()
