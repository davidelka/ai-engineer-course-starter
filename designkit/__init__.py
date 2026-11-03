"""designkit: lesson 20 (Design-Driven Development) reference code.

Company Brain's answer service, designed as ports and adapters:
  types.py      domain types and the error contract (given to the student)
  domain.py     pure business rules: policy, ranking, prompt building, citations
  ports.py      the four ports as typing.Protocol            (reference for exercise 2)
  fakes.py      fake adapters for tests                      (reference for exercise 2)
  service.py    AnswerService, written against ports only    (reference for exercise 3)
  contract.py   reusable contract test suites per port       (reference for exercise 4)
  adapters.py   real adapters: llmkit model, keyword search, JSONL store, system clock
  sqlite_store.py  the adapter a coding agent builds         (reference for exercise 5)
  registry.py   prompt/schema registry with pins and a compatibility check (exercise 6)
  sequence.py   Mermaid sequence-diagram parser and the design rules       (exercise 7)
  review_key.py answer key for the design review                          (exercise 8)
"""

from .types import (Answer, AnswerRequest, BrainError, Completion, ModelRejected, ModelUnavailable, Passage,
                    PolicyDecision, PromptVersion, RetrieverUnavailable)

__all__ = ["Answer", "AnswerRequest", "BrainError", "Completion", "ModelRejected", "ModelUnavailable", "Passage",
           "PolicyDecision", "PromptVersion", "RetrieverUnavailable"]
