"""Context packing: from 30 ranked candidates to the few chunks the model actually reads.

Retrieval returns candidates; the prompt needs a SELECTION. Three things go wrong if you just
take the first k:

- near-duplicates: it-laptop-policy and it-laptop-faq repeat the same paragraphs, and
  hr-vacation-2026 / hr-vacation-2026-he say the same thing twice. Two copies of one paragraph
  waste the budget and push out the second source a multi-hop question needs.
- one document hogs the prompt: the five best chunks of eng-service-catalog leave no room for
  the postmortem the question also needs.
- size: chunks vary from 30 to 450 tokens. A token budget, not a count, controls cost and
  keeps the evidence out of the "middle of a long context" (lesson 13, lost_in_middle).

pack_context is milestone 4 of the project: you write it in mine.py.
"""

from __future__ import annotations



def pack_context(*args, **kwargs):
    """Milestone 4: runs your mine.pack_context (see acmeqa/hooks.py)."""
    from .hooks import call
    return call("pack_context", *args, **kwargs)
