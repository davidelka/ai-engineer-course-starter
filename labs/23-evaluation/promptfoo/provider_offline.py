"""promptfoo Python provider (offline): evalkit's RuleFollowingAnswerer behind promptfoo's call_api.

promptfoo renders the chat prompt file (prompt_v1.json / prompt_v2.json) and passes it here as a
JSON string: [{"role": "system", ...}, {"role": "user", ...}]. We rebuild an llmkit ChatRequest
from it, so the simulation sees exactly the system prompt that promptfoo would send to Claude.
Docs: https://www.promptfoo.dev/docs/providers/python/
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evalkit.rag import RuleFollowingAnswerer  # noqa: E402
from llmkit import ChatRequest, Message  # noqa: E402

ANSWERER = RuleFollowingAnswerer()


def call_api(prompt, options, context):
    try:
        msgs = json.loads(prompt)
    except json.JSONDecodeError:
        msgs = [{"role": "user", "content": prompt}]
    system = "\n".join(m["content"] for m in msgs if m["role"] == "system")
    user = [m["content"] for m in msgs if m["role"] == "user"][-1]
    res = ANSWERER.complete(ChatRequest(messages=[Message("user", user)], system=system, max_tokens=400))
    return {"output": res.text, "tokenUsage": {"prompt": res.usage.input_tokens, "completion": res.usage.output_tokens,
                                              "total": res.usage.input_tokens + res.usage.output_tokens}, "cost": 0.0}
