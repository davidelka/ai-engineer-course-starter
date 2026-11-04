"""Provider adapters: one interface, four backends.

Every adapter takes the same `CallSpec` and returns the same `Result`, so the
experiment runner never knows which provider it talks to. This is the
"replaceable adapter" idea from topic 2, in its simplest form.

Sampling parameters (temperature, top_p, top_k) are sent ONLY when set.
Most frontier models in 2026 reject them; when that happens the error is
captured in `Result.error` instead of crashing the whole experiment.
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class CallSpec:
    model: str
    system: str
    user: str
    max_tokens: int = 1024
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    effort: Optional[str] = None  # low | medium | high (provider-specific mapping)


@dataclass
class Result:
    text: str = ""
    in_tokens: int = 0
    out_tokens: int = 0
    stop_reason: str = ""
    latency_s: float = 0.0
    error: Optional[str] = None
    raw_meta: dict = field(default_factory=dict)


def _timed(fn: Callable[[], Result]) -> Result:
    t0 = time.perf_counter()
    try:
        res = fn()
    except Exception as exc:  # report, never crash the experiment
        res = Result(error=f"{type(exc).__name__}: {exc}")
    res.latency_s = time.perf_counter() - t0
    return res


# ---------------------------------------------------------------- Anthropic
def call_anthropic(spec: CallSpec) -> Result:
    import anthropic

    client = anthropic.Anthropic()
    extra: dict = {}
    # temperature / top_p / top_k are deprecated in the SDK signature, so they
    # go through extra_body. Newer models answer with HTTP 400 if they differ
    # from the defaults; that is part of what the lab shows.
    for name in ("temperature", "top_p", "top_k"):
        value = getattr(spec, name)
        if value is not None:
            extra[name] = value

    kwargs: dict = dict(
        model=spec.model,
        max_tokens=spec.max_tokens,
        system=spec.system,
        messages=[{"role": "user", "content": spec.user}],
    )
    if spec.effort:
        kwargs["output_config"] = {"effort": spec.effort}
    if extra:
        kwargs["extra_body"] = extra
        # Newer API versions (the header the SDK sends by default, e.g. 2026-10-21) removed
        # sampling parameters from the request schema entirely ("Extra inputs are not
        # permitted"). The original 2023-06-01 version still accepts them, and then each
        # model decides: older models honor them, newer ones reject non-default values.
        kwargs["extra_headers"] = {"anthropic-version": "2023-06-01"}

    def run() -> Result:
        resp = client.messages.create(**kwargs)
        # Select by type: on many current models a thinking block comes first.
        text = "".join(b.text for b in resp.content if b.type == "text")
        return Result(
            text=text,
            in_tokens=resp.usage.input_tokens,
            out_tokens=resp.usage.output_tokens,
            stop_reason=resp.stop_reason or "",
        )

    return _timed(run)


# ------------------------------------------------------------------- OpenAI
def _openai_stop_reason(resp) -> str:
    """Why a Responses API call stopped.

    `status` is "completed" for a normal answer. A cut-off answer has status "incomplete" and
    the reason (e.g. "max_output_tokens" or "content_filter") in `incomplete_details.reason`;
    that reason is what stop_reason should carry, like max_tokens on Anthropic.
    """
    status = getattr(resp, "status", None) or ""
    if status == "incomplete":
        details = getattr(resp, "incomplete_details", None)
        reason = getattr(details, "reason", None) if details is not None else None
        return reason or status
    return status


def call_openai(spec: CallSpec) -> Result:
    from openai import OpenAI

    client = OpenAI()
    kwargs: dict = dict(
        model=spec.model,
        instructions=spec.system,
        input=spec.user,
        max_output_tokens=spec.max_tokens,
    )
    if spec.temperature is not None:
        kwargs["temperature"] = spec.temperature
    if spec.top_p is not None:
        kwargs["top_p"] = spec.top_p
    if spec.effort:
        kwargs["reasoning"] = {"effort": spec.effort}

    def run() -> Result:
        resp = client.responses.create(**kwargs)
        usage = resp.usage
        return Result(
            text=resp.output_text or "",
            in_tokens=getattr(usage, "input_tokens", 0) if usage else 0,
            out_tokens=getattr(usage, "output_tokens", 0) if usage else 0,
            stop_reason=_openai_stop_reason(resp),
        )

    return _timed(run)


# ------------------------------------------------------------------- Gemini
def call_gemini(spec: CallSpec) -> Result:
    from google import genai
    from google.genai import types

    client = genai.Client()  # reads GEMINI_API_KEY (or GOOGLE_API_KEY)
    cfg: dict = dict(system_instruction=spec.system, max_output_tokens=spec.max_tokens)
    for name in ("temperature", "top_p", "top_k"):
        value = getattr(spec, name)
        if value is not None:
            cfg[name] = value
    if spec.effort:
        cfg["thinking_config"] = types.ThinkingConfig(thinking_level=spec.effort)

    def run() -> Result:
        resp = client.models.generate_content(
            model=spec.model, contents=spec.user, config=types.GenerateContentConfig(**cfg)
        )
        meta = resp.usage_metadata
        finish = ""
        if resp.candidates and resp.candidates[0].finish_reason:
            finish = str(resp.candidates[0].finish_reason)
        return Result(
            text=resp.text or "",
            in_tokens=(meta.prompt_token_count or 0) if meta else 0,
            out_tokens=(meta.candidates_token_count or 0) if meta else 0,
            stop_reason=finish,
        )

    return _timed(run)


# ------------------------------------------------------------------- Ollama
def call_ollama(spec: CallSpec) -> Result:
    """Local open model via Ollama: the one place where every sampling knob works."""
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    options: dict = {"num_predict": spec.max_tokens}
    for name in ("temperature", "top_p", "top_k"):
        value = getattr(spec, name)
        if value is not None:
            options[name] = value
    body = {
        "model": spec.model,
        "stream": False,
        "options": options,
        "messages": [
            {"role": "system", "content": spec.system},
            {"role": "user", "content": spec.user},
        ],
    }

    def run() -> Result:
        req = urllib.request.Request(
            f"{host}/api/chat",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=300) as r:
            data = json.loads(r.read())
        return Result(
            text=data.get("message", {}).get("content", ""),
            in_tokens=data.get("prompt_eval_count", 0),
            out_tokens=data.get("eval_count", 0),
            stop_reason=data.get("done_reason", ""),
        )

    return _timed(run)


PROVIDERS: dict[str, Callable[[CallSpec], Result]] = {
    "anthropic": call_anthropic,
    "openai": call_openai,
    "gemini": call_gemini,
    "ollama": call_ollama,
}


def get_provider(name: str) -> Callable[[CallSpec], Result]:
    try:
        return PROVIDERS[name]
    except KeyError:
        raise ValueError(f"Unknown provider '{name}'. Choose from: {', '.join(PROVIDERS)}")
