"""ctxkit: context engineering helpers for lesson 4.

    tokens      count tokens offline (tiktoken o200k_base) or with Claude's free count_tokens
    layers      break an Anthropic request into layers and count each one (reference for ex 1)
    layout      a cache-friendly HR assistant request (reference for ex 2)
    compaction  truncation, summarization and compaction of long conversations (reference for ex 6)
    cachemodel  expected cost of prompt caching for a traffic pattern
    haystack    needle-in-a-haystack prompts for the position test
    fake        offline stand-ins: an extractive "model" and a heuristic summarizer

The lab's mine.py asks you to write your own versions of layers, layout and compaction.
Try not to read those three modules before your tests pass.
"""

from .cachemodel import CacheScenario, break_even_hit_rate, hit_probability, scenario_cost
from .compaction import compact, llm_summarizer, messages_tokens, truncate
from .layers import Layer, layer_report
from .tokens import count_tokens, is_exact_o200k, tokenizer_name

__all__ = [
    "CacheScenario", "break_even_hit_rate", "hit_probability", "scenario_cost",
    "compact", "llm_summarizer", "messages_tokens", "truncate",
    "Layer", "layer_report", "count_tokens", "tokenizer_name", "is_exact_o200k",
]
