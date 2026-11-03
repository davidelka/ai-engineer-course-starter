"""Exercise 4, part 2: watch the repair loop with YOUR extract_json and format_errors.

Terminal 1:  python -m mockllm --json-fault bad_enum --json-fault-first 1
Terminal 2:  python labs/03-structured-outputs/repair_demo.py
             python labs/03-structured-outputs/repair_demo.py --reference   # llmkit's versions

Try every fault: fence, prose, truncated, missing_field, wrong_type, bad_enum,
extra_field, out_of_range. Use --json-fault-first 100 to see it give up.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
sys.path[:0] = [str(LAB.parents[1]), str(LAB)]
from acme_schema import AccessRequest  # noqa: E402
from llmkit import LLM  # noqa: E402
from llmkit.structured import StructuredError, complete_structured  # noqa: E402
from llmkit.structured import extract_json as ref_extract, format_errors as ref_format  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="mock:mock-model")
    ap.add_argument("--mode", default="native", choices=["native", "prompt"])
    ap.add_argument("--max-repairs", type=int, default=2)
    ap.add_argument("--reference", action="store_true")
    a = ap.parse_args()
    if a.reference:
        extract, explain = ref_extract, ref_format
    else:
        from mine import extract_json as extract, format_errors as explain

    llm = LLM(a.model)
    try:
        res = complete_structured(llm, "Read access to the Platform Confluence space, please. Dana",
                                  AccessRequest, mode=a.mode, max_repairs=a.max_repairs,
                                  extract=extract, explain=explain)
        for i, err in enumerate(res.errors, 1):
            print(f"attempt {i} failed, sent back to the model:\n{err}\n")
        print(f"VALID after {res.attempts} attempt(s), {res.repairs} repair(s), "
              f"{res.input_tokens} in / {res.output_tokens} out tokens")
        print(res.value.model_dump_json(indent=2))
    except StructuredError as e:
        for i, err in enumerate(e.errors, 1):
            print(f"attempt {i} failed:\n{err}\n")
        print(f"GAVE UP: {e}\nlast reply: {e.last_text[:300]}")


if __name__ == "__main__":
    main()
