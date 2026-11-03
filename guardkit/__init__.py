"""guardkit: prompt-injection test harness and composable guardrails (lesson 24).

The pieces, in the order a request flows through them:

    docs.py        a handful of Acme corpus documents, split into chunks, with classification
    retrieval.py   a tiny self-contained BM25 index (no ragkit dependency)
    models.py      ObedientModel (offline, SIMULATED naive model that follows injected
                   instructions) and LLMKitModel (a real model through llmkit)
    answerer.py    a RAG-like answerer: input checks -> ACL -> retrieve -> screen untrusted ->
                   prompt -> model -> output checks -> actions
    defenses.py    the layers: AclFilter, InstructionHierarchy, Spotlight, InputClassifier,
                   OutputValidator, ToolAllowlist, ConfirmSideEffects (compose any subset)
    detectors.py   injection detectors: HeuristicDetector (regex, multilingual) and
                   LLMDetector (llmkit structured output)
    validate.py    reference output validator (lesson exercise 4)
    acl.py         reference ACL rules (exercise 5)
    render.py      safe HTML rendering of model output and a parameterized SQL tool (exercise 7)
    redact.py      PII redaction for logs, Israeli ID checksum (exercise 8)
    evaluate.py    attack success rate and false-positive rate over JSONL suites
    data/          attacks.jsonl and benign.jsonl
"""

from .types import Chunk, Finding, Trace, User
from .answerer import Answerer, SYSTEM_PROMPT, CANARY
from .models import LLMKitModel, ObedientModel
from .defenses import (AclFilter, ConfirmSideEffects, InputClassifier, InstructionHierarchy,
                       Layer, OutputValidator, Spotlight, ToolAllowlist, build_layers, LAYER_NAMES)
from .detectors import HeuristicDetector, LLMDetector
from .evaluate import load_attacks, load_benign, run_suite, Report

__all__ = [
    "Chunk", "Finding", "Trace", "User", "Answerer", "SYSTEM_PROMPT", "CANARY", "LLMKitModel",
    "ObedientModel", "AclFilter", "ConfirmSideEffects", "InputClassifier", "InstructionHierarchy",
    "Layer", "OutputValidator", "Spotlight", "ToolAllowlist", "build_layers", "LAYER_NAMES",
    "HeuristicDetector", "LLMDetector", "load_attacks", "load_benign", "run_suite", "Report",
]
