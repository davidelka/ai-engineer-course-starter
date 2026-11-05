"""Check every external link in the course for rot.  python hub/check_links.py [--timeout 15] [--workers 8]

Scans the hub sources (lessons, lab guides, aids, live findings) and every README / *.md in the repo
for http(s) links, requests each one (HEAD, then GET if the server refuses HEAD), and prints the
ones that fail with where they appear. Run it on your own machine every month or so: the course
cites ~400 external pages (papers, docs, videos), and docs move.

Exit code 1 if any link is broken. Links to localhost, example domains and the course's own repo
are skipped. Some sites (YouTube, LinkedIn, some docs behind bot protection) answer 403/429 to
scripts while working fine in a browser: those are reported separately as "check by hand".
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
URL = re.compile(r"""https?://[^\s"'<>()\]\\`]+""")
SKIP = re.compile(r"localhost|127\.0\.0\.1|0\.0\.0\.0|example\.(com|org)|\.example\b|acme\.|github\.com/davidelka|\{|\$")
SOFT = {401, 403, 405, 429, 999}  # bot walls: "check by hand", not "broken"


def collect() -> dict[str, set[str]]:
    where: dict[str, set[str]] = defaultdict(set)
    files = list((ROOT / "hub" / "src").rglob("*.js")) + [p for p in ROOT.rglob("*.md") if ".git" not in p.parts and ".venv" not in p.parts]
    for f in files:
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for u in URL.findall(text):
            u = u.rstrip(".,;:!?*_")
            if not SKIP.search(u):
                where[u].add(str(f.relative_to(ROOT)))
    return where


def check(client: httpx.Client, url: str) -> tuple[str, int | str]:
    try:
        r = client.head(url)
        if r.status_code in (400, 403, 404, 405, 501):  # many servers mishandle HEAD
            r = client.get(url)
        return url, r.status_code
    except httpx.HTTPError as e:
        return url, type(e).__name__


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--timeout", type=float, default=15)
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    where = collect()
    print(f"{len(where)} unique links in {len({f for s in where.values() for f in s})} files")
    headers = {"User-Agent": "Mozilla/5.0 (course link checker)"}
    with httpx.Client(follow_redirects=True, timeout=a.timeout, headers=headers) as client, ThreadPoolExecutor(a.workers) as pool:
        results = list(pool.map(lambda u: check(client, u), sorted(where)))
    broken = [(u, s) for u, s in results if not (isinstance(s, int) and (s < 400 or s in SOFT))]
    soft = [(u, s) for u, s in results if isinstance(s, int) and s in SOFT]
    for title, rows in (("BROKEN", broken), ("check by hand (bot wall or rate limit)", soft)):
        if rows:
            print(f"\n{title}: {len(rows)}")
            for u, s in rows:
                print(f"  [{s}] {u}\n        in: {', '.join(sorted(where[u]))}")
    print(f"\nok: {len(results) - len(broken) - len(soft)}, broken: {len(broken)}, check by hand: {len(soft)}")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
