"""The architecture artifacts, checked by code (archkit, lesson 19).

    python -m cbrain arch

1. arch/company_brain.arch.yaml loads (archkit.spec) and passes archkit's five rules: external input
   guarded, LLM resilience, PII classified, write tools approved, observability.
2. The three ADRs in arch/adr/ pass archkit's ADR lint (sections, options, outcome, consequences with a
   negative one, cost and latency with numbers, a measurable confirmation).
3. The Mermaid diagram is generated from the spec (never drawn by hand): results/arch.mmd + arch.html.
"""

from __future__ import annotations

from pathlib import Path

from . import PROJECT

ARCH = PROJECT / "arch" / "company_brain.arch.yaml"
ADR_DIR = PROJECT / "arch" / "adr"


def check_spec() -> list:
    from archkit import load_spec
    from archkit.rules import check
    return check(load_spec(ARCH))


def check_adrs() -> dict[str, list]:
    from archkit.adr import lint_adr
    return {p.name: lint_adr(p.read_text(encoding="utf-8")) for p in sorted(ADR_DIR.glob("*.md"))}


def write_diagram(out_dir: Path) -> Path:
    from archkit import load_spec
    from archkit.mermaid import to_html, to_mermaid
    code = to_mermaid(load_spec(ARCH))
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "arch.mmd").write_text(code, encoding="utf-8")
    (out_dir / "arch.html").write_text(to_html(code, "Company Brain architecture"), encoding="utf-8")
    return out_dir / "arch.mmd"


def check_all(verbose: bool = False) -> bool:
    findings = check_spec()
    adrs = check_adrs()
    errors = [f for f in findings if f.severity == "error"] + [f for fs in adrs.values() for f in fs
                                                               if f.severity == "error"]
    if verbose:
        print(f"spec {ARCH.name}: {len(findings)} findings")
        for f in findings:
            print(f"  {f}")
        for name, fs in adrs.items():
            print(f"ADR {name}: {'ok' if not fs else ''}")
            for f in fs:
                print(f"  {f}")
        print(f"diagram: {write_diagram(PROJECT / 'results')}")
        print("OK" if not errors else f"{len(errors)} errors")
    return not errors
