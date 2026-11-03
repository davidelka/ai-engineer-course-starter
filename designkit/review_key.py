"""Answer key for the design review in labs/20-design-driven/designs/answer_service_v2.md.
Do not read before you finish your review (exercise 8)."""

FLAWS = {
    "D2": {
        "checklist": {"C1"},
        "title": "Vendor type in the model port",
        "why": "complete() returns anthropic.types.Message and the service reads content[0].text. Switching "
               "to OpenAI or a fake now means faking Anthropic's SDK objects: the port is not a port.",
        "fix": "Return a domain Completion(text, model, input_tokens, output_tokens, cost_usd).",
    },
    "D3": {
        "checklist": {"C3", "C1"},
        "title": "Retriever port shaped by one implementation",
        "why": "search(embedding, top_k, ef_search) assumes vector search with HNSW, and the service owns "
               "the embedding model. Keyword or hybrid search cannot implement it; changing the embedding "
               "model touches the core. It also returns untyped dicts.",
        "fix": "search(query: str, k: int) -> list[Passage]; embedding and ef_search live inside the adapter.",
    },
    "D4": {
        "checklist": {"C2"},
        "title": "Retries at two layers, no error contract",
        "why": "SDK retries 2 (3 tries) x service retries 3 (4 tries) = up to 12 calls per question during an "
               "outage, a retry storm exactly when the provider is overloaded. Raw SDK exceptions reach the "
               "API, so the service cannot tell transient from permanent, and HTTP 500 leaks internals.",
        "fix": "Retries only in the adapter; it raises ModelUnavailable (transient) or ModelRejected "
               "(permanent); the service degrades on the first and fails loudly on the second.",
    },
    "D5": {
        "checklist": {"C6"},
        "title": "Policy check after the model call",
        "why": "A salary question or a question from a non-employee is already sent to retrieval and to a "
               "third-party model, and paid for, before the policy refuses it. Filtering the answer does "
               "not undo that the data left.",
        "fix": "Policy on the question first; only allowed questions reach retrieval and the model. An "
               "output check can be added on top.",
    },
    "D6": {
        "checklist": {"C4"},
        "title": "No idempotency, but automatic retries",
        "why": "The gateway retries after 5 s while p95 is 4 s, so slow requests run twice: two model calls, "
               "two rows, two different answers for one question. An auto-increment id cannot deduplicate.",
        "fix": "Client-generated request_id as the idempotency key; store.get before work; put with first "
               "write wins.",
    },
    "D8": {
        "checklist": {"C5"},
        "title": "Unversioned prompt, cache key without the version",
        "why": "Editing the prompt in place means no way to know which prompt produced an answer, no "
               "rollback, and for 24 hours the cache serves answers from the OLD prompt, because the key is "
               "only the question.",
        "fix": "Versioned prompts in a registry, pinned by the service, prompt_version stored on each answer, "
               "cache key includes the prompt fingerprint.",
    },
    "D9": {
        "checklist": {"C8"},
        "title": "Breaking rename of a public field",
        "why": "Renaming citations to sources breaks the Slack bot and the HR portal on deploy day. 'They "
               "will update when they can' means they are broken until then.",
        "fix": "Add sources next to citations and deprecate, or publish the new shape as a new major "
               "version (/v2) and keep v1 for a period.",
    },
    "D11": {
        "checklist": {"C7"},
        "title": "Only live end-to-end tests",
        "why": "Nightly tests against the real API are slow, cost money, are flaky, and cannot produce the "
               "interesting cases on demand (timeouts, refusals, a race between two retries). 'Glue code' "
               "is exactly where the ordering and error-handling bugs live.",
        "fix": "Unit tests of the service with fakes on every commit; a contract suite per port; the live "
               "golden set stays as a nightly eval on top.",
    },
}

# Sections that look suspicious to some reviewers but are fine.
FINE = {
    "D1": "Context with real numbers: good, it lets the reviewer check D6 against p95.",
    "D7": "Clock injected and logs carry request_id and metadata without content: this is C9 done right.",
    "D10": "A domain-shaped port with a clear promise and a shared contract suite: good.",
    "D12": "Shadow mode and a rollback flag: a sound rollout.",
}
