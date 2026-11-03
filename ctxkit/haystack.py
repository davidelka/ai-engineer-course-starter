"""Needle-in-a-haystack prompts for the position test (exercise 5).

A haystack is a list of real-looking documents (Acme handbook sections). One of them gets
a needle: a single sentence with the answer. Distractors are near-miss sentences that look
like the answer but are not (Chroma's "Context Rot" report found that even one distractor
lowers accuracy, and more so as the context grows).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from .tokens import count_tokens


@dataclass
class Needle:
    question: str
    sentence: str  # inserted into the haystack
    answer: str  # what a correct reply must contain
    distractors: tuple[str, ...] = ()


NEEDLES = [
    Needle(
        question="What is the door code for the server room on floor 7 of the Haifa office?",
        sentence="The door code for the server room on floor 7 of the Haifa office is 4-8-1-5-2, changed every quarter by Facilities.",
        answer="48152",
        distractors=(
            "The door code for the storage room on floor 3 of the Haifa office is 7-7-2-0-9.",
            "The door code for the server room in the Tel Aviv office was 3-1-6-6-4 until it was replaced by badge access.",
            "Floor 4 of the Beersheba office has a server room; its door code is 9-0-3-3-1 and it changes every month.",
        ),
    ),
    Needle(
        question="Who must approve a purchase of conference sponsorship above 20,000 NIS?",
        sentence="Conference sponsorships above 20,000 NIS must be approved by Orly Ben-David, the VP Marketing, before any commitment is made.",
        answer="Orly Ben-David",
        distractors=(
            "Conference travel above 20,000 NIS per team per quarter is approved by the department's finance partner, Amit Levi.",
            "Sponsorships of community events below 5,000 NIS are approved by the Office Manager, Rina Cohen.",
        ),
    ),
]


def split_sections(markdown: str) -> list[str]:
    """Split a markdown file on '## ' headings into sections (heading kept)."""
    parts = re.split(r"(?m)^(?=## )", markdown)
    return [p.strip() for p in parts if p.strip().startswith("## ")]


def build_haystack(sections: list[str], target_tokens: int, needle: Needle, position: float,
                   n_distractors: int = 0, count: Callable[[str], int] = count_tokens) -> tuple[str, int]:
    """Return (documents_xml, token_count). Sections are repeated in order until the target
    size is reached; the needle goes at `position` (0 = first document, 1 = last); the
    distractors are spread evenly, away from the needle."""
    docs, total, i = [], 0, 0
    while total < target_tokens and sections:
        s = sections[i % len(sections)]
        docs.append(s)
        total += count(s)
        i += 1
    if not docs:
        docs = [""]
    n = len(docs)
    at = min(n - 1, max(0, round(position * (n - 1))))
    docs[at] = _insert_sentence(docs[at], needle.sentence)
    ds = needle.distractors[:n_distractors]
    for k, d in enumerate(ds):
        j = round((k + 1) * n / (len(ds) + 1)) % n
        if j == at:
            j = (j + 1) % n
        docs[j] = _insert_sentence(docs[j], d)
    xml = "<documents>\n" + "\n".join(
        f'<document index="{k + 1}">\n{d}\n</document>' for k, d in enumerate(docs)) + "\n</documents>"
    return xml, count(xml)


def _insert_sentence(section: str, sentence: str) -> str:
    """Put the sentence in the middle of the section, on its own line."""
    lines = section.splitlines()
    mid = max(1, len(lines) // 2)
    return "\n".join(lines[:mid] + [sentence] + lines[mid:])


def is_correct(reply: str, answer: str) -> bool:
    """Digits-only comparison for codes ("4-8-1-5-2" == "48152"), case-insensitive otherwise."""
    if answer.isdigit():
        return answer in re.sub(r"\D", "", reply)
    return answer.lower() in reply.lower()
