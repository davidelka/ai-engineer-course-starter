# Design review checklist: component and interface level

Use it on any design doc for an AI component. For each item, look for the
place in the doc where it is answered, or notice that it is not. Each item has
an id (C1 to C9) that you cite in your review.

- **C1. Ports speak the domain's language.** No vendor or SDK types (an
  `anthropic.types.Message`, an httpx response, a DB row) in a port's
  parameters or return values. Otherwise the "replaceable" adapter is not.
- **C2. Every port has an error contract.** Which errors it raises, which are
  transient (retry may help) and which are permanent (bug or config), and
  exactly ONE layer owns retries. Retries at two layers multiply.
- **C3. Interfaces are shaped by what the domain needs, not by one
  implementation.** A parameter that only makes sense for today's backend
  (an embedding vector, an HNSW knob, a SQL fragment) leaks it into the core.
- **C4. Side effects are idempotent.** If the caller, the gateway or a queue
  retries, nothing happens twice: an idempotency key from the caller, and
  "first write wins" in the store.
- **C5. Prompts and output schemas are versioned.** Immutable versions, a pin
  in the caller, the version recorded on every output, and caches keyed by
  the version too.
- **C6. Guards run before data leaves.** Policy checks run before retrieval,
  before the model call and before content is logged, not after.
- **C7. Testable without the network.** Dependencies injected, a fake per
  port, a contract suite that every adapter (fake and real) passes; a few
  live tests on top, not instead.
- **C8. Public schema changes are compatible or versioned.** Renaming or
  removing a field that clients read is a breaking change: new major version,
  or keep both for a deprecation period.
- **C9. Observability.** A request id flows through every call and log line;
  logs carry metadata (status, latency, cost), not personal content.
