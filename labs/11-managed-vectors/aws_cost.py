"""Exercise 7: what would Company Brain's vector index cost on AWS, at 1M and 10M chunks?

    python labs/11-managed-vectors/aws_cost.py                          # 1M and 10M, 1024 dims
    python labs/11-managed-vectors/aws_cost.py --dims 384 --queries 300000
    python labs/11-managed-vectors/aws_cost.py --n 210 --dims 384       # Acme today

Prices are us-east-1 list prices (November 2026, see ragkit/vectors/sizing.py for sources)
and every row prints its assumptions. They are ESTIMATES: before you commit, put the same
numbers into the AWS Pricing Calculator (https://calculator.aws/) and, better, run a week of
real traffic and read Cost Explorer. The point of the exercise is to know which knob moves
which line: vectors x dims (storage, RAM), queries (S3 Vectors), always-on hours (OCUs, ACUs,
instances), quantization (RAM -> instance size).

Options:
  S3 Vectors                  pay per GB stored + per query; nothing while idle; ~100 ms warm,
                              <1 s cold; no HNSW knobs; Bedrock Knowledge Bases integration
  OpenSearch Serverless       classic: OCUs billed every hour, at least 2 (dev/test 1);
                              next-gen (2026): scales to zero, ~10 s cold start; full hybrid search
  Aurora Serverless+pgvector  SQL + vectors in one database, ACUs (2 GiB each); 0 ACU auto-pause
  EC2 + Qdrant (self-hosted)  cheapest per GB of RAM, but you run backups, upgrades, HA
  Pinecone (not AWS)          for scale comparison only; read/write units not modelled
"""

from __future__ import annotations

import argparse

from common import fmt_mb  # noqa: E402
from ragkit.vectors.sizing import PRICES_DATE, PRICES_SOURCES, compare, hnsw_ram_bytes  # noqa: E402


def ints(s: str) -> list[int]:
    return [int(float(x)) for x in s.split(",") if x]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=ints, default=[1_000_000, 10_000_000], help="vectors, comma-separated")
    ap.add_argument("--dims", type=ints, default=[1024])
    ap.add_argument("--queries", type=int, default=100_000, help="queries per month")
    ap.add_argument("--active-hours", type=float, default=200,
                    help="hours per month a scale-to-zero option is awake (next-gen OpenSearch)")
    a = ap.parse_args()
    print(f"prices: us-east-1, {PRICES_DATE}; {a.queries:,} queries/month\n")
    for n in a.n:
        for d in a.dims:
            r = hnsw_ram_bytes(n, d)
            rq = hnsw_ram_bytes(n, d, quantization="int8")
            print(f"=== {n:,} vectors x {d} dims   raw float32 {fmt_mb(n * d * 4)}   "
                  f"HNSW RAM {fmt_mb(r['total_ram'])} (int8: {fmt_mb(rq['total_ram'])})")
            rows = compare(n, d, a.queries, active_hours=a.active_hours)
            for x in sorted(rows, key=lambda x: x["total"]):
                print(f"  ${x['total']:>9,.2f}/mo  {x['option']:<42} {x['assumes']}")
            s3 = next(x for x in rows if x["option"] == "S3 Vectors")
            print(f"  (S3 Vectors one-off initial load: ${s3['one_off_load']:,.2f}; per query ${s3['per_query']:.6f})\n")
    print("teardown: every option except S3 Vectors bills while idle. After a lab run:")
    print("  - S3 Vectors: python labs/11-managed-vectors/s3vectors_demo.py --teardown (or terraform destroy)")
    print("  - OpenSearch Serverless classic: delete the COLLECTION (the OCUs stop with it)")
    print("  - Aurora: delete the cluster, or set min capacity 0 (auto-pause; storage still bills)")
    print("  - EC2: terminate the instance AND delete its EBS volume and snapshots")
    print("\nsources: " + "; ".join(PRICES_SOURCES))


if __name__ == "__main__":
    main()
