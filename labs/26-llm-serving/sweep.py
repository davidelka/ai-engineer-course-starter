"""Exercise 5: run locust at increasing concurrency, chart p50/p95/TTFT, find the knee.

Start these first (two terminals):
    python -m servekit.mock --ttft 0.3 --tps 40 --words 60
    python -m servekit --max-concurrency 8 --max-queue 16 --rate 100 --burst 100 --load-test-keys 128

Then:
    python labs/26-llm-serving/sweep.py                       # users 1,2,4,...,64, 20s each
    python labs/26-llm-serving/sweep.py --users 1 4 16 64 --seconds 15

Writes results/sweep.csv and results/sweep.png, and prints one line per level.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
sys.path.insert(0, str(LAB.parent.parent))

from servekit.loadtest import find_knee, level_from_stats, plot, read_locust_stats, write_csv  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="http://127.0.0.1:8000")
    p.add_argument("--users", type=int, nargs="+", default=[1, 2, 4, 8, 16, 32, 64])
    p.add_argument("--seconds", type=int, default=20)
    p.add_argument("--out", default=str(LAB / "results"))
    a = p.parse_args()
    if not shutil.which("locust"):
        sys.exit("locust is not installed: uv pip install -r labs/26-llm-serving/requirements.txt")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    levels = []
    print(f"{'users':>5} {'ok/s':>6} {'p50':>7} {'p95':>7} {'ttft50':>7} {'ttft95':>7} {'fail':>6}")
    for u in a.users:
        prefix = out / f"u{u}"
        cmd = ["locust", "-f", str(LAB / "locustfile.py"), "--host", a.host, "--headless", "-u", str(u),
               "-r", str(u), "-t", f"{a.seconds}s", "--csv", str(prefix), "--only-summary",
               "--loglevel", "WARNING"]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        lv = level_from_stats(u, read_locust_stats(f"{prefix}_stats.csv"))
        levels.append(lv)
        print(f"{u:>5} {lv.rps:>6.2f} {lv.p50_ms:>7.0f} {lv.p95_ms:>7.0f} {lv.ttft_p50_ms:>7.0f} "
              f"{lv.ttft_p95_ms:>7.0f} {lv.failures:>6}")
    write_csv(levels, out / "sweep.csv")
    knee = find_knee(levels)
    if knee:
        print(f"\nknee (max throughput/p95): {knee.users} users, {knee.rps} streams/s, p95 {knee.p95_ms:.0f} ms")
    if plot(levels, out / "sweep.png"):
        print(f"chart: {out / 'sweep.png'}")
    else:
        print("matplotlib not installed: chart skipped (CSV written)")


if __name__ == "__main__":
    main()
