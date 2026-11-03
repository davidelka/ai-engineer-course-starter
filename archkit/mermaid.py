"""Spec -> Mermaid flowchart (lesson 19). The diagram is generated, never drawn by hand,
so it cannot drift away from the spec that the rules check.

Output contract (the lab tests check it):
  - first line: "flowchart LR"
  - one subgraph per boundary that has components:
        subgraph b_<id>["<boundary name> · <trust>"]
          ...nodes...
        end
  - one node per component, id "c_<id>", label "<name><br/><small>kind · tech</small>"
    shapes: llm {{...}}, datastore/cache [(...)], guardrail/classifier [[...]],
            human_approval [/.../], everything else [...]
  - one edge per flow, in spec order: c_a -->|"data"| c_b ; pii flows use ==> (thick)
  - then one dotted edge per component whose fallback is another component:
        c_a -.->|"fallback"| c_b
  - classDef lines for kinds, then "class c_x,c_y <kind>" lines
Ids are prefixed (b_, c_) because a bare node called "end" breaks Mermaid.
Quotes in labels are written as #quot; (Mermaid's entity syntax).
"""

from __future__ import annotations

from .spec import Spec

SHAPES = {
    "llm": ("{{", "}}"),
    "datastore": ("[(", ")]"),
    "cache": ("[(", ")]"),
    "guardrail": ("[[", "]]"),
    "classifier": ("[[", "]]"),
    "human_approval": ("[/", "/]"),
}

STYLES = {
    "llm": "fill:#e2e8fb,stroke:#2446c4,stroke-width:2px",
    "guardrail": "fill:#dcf1e5,stroke:#1f7a4d",
    "classifier": "fill:#dcf1e5,stroke:#1f7a4d",
    "tool": "fill:#fcebd4,stroke:#c56a06",
    "human_approval": "fill:#fcebd4,stroke:#c56a06,stroke-width:2px",
    "observability": "fill:#eef1f6,stroke:#586079,stroke-dasharray:4 3",
    "eval": "fill:#eef1f6,stroke:#586079,stroke-dasharray:4 3",
}


def esc(text: str) -> str:
    return str(text).replace('"', "#quot;")


def node(c) -> str:
    left, right = SHAPES.get(c.kind, ("[", "]"))
    meta = c.kind + (f" · {c.tech}" if c.tech else (f" · {c.model}" if c.model else ""))
    return f'c_{c.id}{left}"{esc(c.name)}<br/><small>{esc(meta)}</small>"{right}'


def to_mermaid(spec: Spec) -> str:
    lines = ["flowchart LR"]
    for b in spec.boundaries:
        members = [c for c in spec.components if c.boundary == b.id]
        if not members:
            continue
        lines.append(f'  subgraph b_{b.id}["{esc(b.name)} · {b.trust}"]')
        for c in members:
            lines.append("    " + node(c))
        lines.append("  end")
    for f in spec.flows:
        arrow = "==>" if f.classification == "pii" else "-->"
        label = f.data + (" (pii)" if f.classification == "pii" else "")
        lines.append(f'  c_{f.src} {arrow}|"{esc(label)}"| c_{f.dst}')
    for c in spec.components:
        if c.fallback and c.fallback != c.id and spec.has_component(c.fallback):
            lines.append(f'  c_{c.id} -.->|"fallback"| c_{c.fallback}')
    used = {c.kind for c in spec.components}
    for kind, style in STYLES.items():
        if kind in used:
            lines.append(f"  classDef {kind} {style}")
    for kind in STYLES:
        ids = [f"c_{c.id}" for c in spec.components if c.kind == kind]
        if ids:
            lines.append(f"  class {','.join(ids)} {kind}")
    return "\n".join(lines) + "\n"


HTML = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>body{{font-family:system-ui,sans-serif;margin:16px;background:#fff}} .mermaid{{overflow:auto}}</style>
</head><body>
<h2>{title}</h2>
<pre class="mermaid">
{code}
</pre>
<script type="module">
import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@12.2.0/dist/mermaid.esm.min.mjs";
mermaid.initialize({{ startOnLoad: true, securityLevel: "loose", flowchart: {{ htmlLabels: true }} }});
</script>
</body></html>
"""


def to_html(code: str, title: str) -> str:
    """A standalone page that renders the diagram with Mermaid from a CDN (needs internet)."""
    import html
    return HTML.format(title=html.escape(title), code=html.escape(code))
