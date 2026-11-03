"""Exercise 8 (optional, AWS account, ~0 cost): the Acme corpus in Amazon S3 Vectors.

    uv pip install boto3                     # not a course dependency; only this script needs it
    aws configure                            # or AWS_PROFILE=...; region with S3 Vectors, e.g. eu-central-1
    python labs/11-managed-vectors/s3vectors_demo.py --bucket acme-brain-<yourname> --region eu-central-1
    python labs/11-managed-vectors/s3vectors_demo.py --bucket acme-brain-<yourname> --region eu-central-1 --teardown

What it does
  1. creates a vector bucket + index (cosine, dim of your embedder, "chunk" non-filterable),
     unless they exist (or create them with the Terraform in labs/11-managed-vectors/terraform/);
  2. PutVectors the 210 Acme chunks (lesson 10's cached embeddings: no model cost);
  3. queries the 79 golden questions, compares with the exact numpy top-10 (agree@10), and
     runs the contractor/engineering ACL filters (acl_where) to show the filter is server-side;
  4. prints what it cost (an estimate from sizing.py) and how to delete everything.
Cost: 210 x 384-dim vectors are ~1.3 MB: storage ~$0.0001/month, PUT ~$0.0003, 79 queries
~$0.0002. Effectively free; the teardown still matters (good habit, and bigger tests).
Region: S3 Vectors is in 14 regions (Dec 2025); Tel Aviv (il-central-1) was not in that list.
Bucket names are global-ish per account/region: add your name.
"""

from __future__ import annotations

import argparse
import sys

import numpy as np

from common import DEFAULT_MODEL, acme_vectors, numpy_store  # noqa: E402
from ragkit.vectors.filters import acl_where  # noqa: E402
from ragkit.vectors.s3vectors_store import S3VectorsStore  # noqa: E402
from ragkit.vectors.sizing import s3vectors_monthly  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bucket", required=True)
    ap.add_argument("--index", default="acme-chunks")
    ap.add_argument("--region", default="eu-central-1")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--teardown", action="store_true", help="delete the index and the bucket, then exit")
    ap.add_argument("--yes", action="store_true")
    a = ap.parse_args()
    try:
        import boto3  # type: ignore
    except ImportError:
        sys.exit("this optional exercise needs boto3: uv pip install boto3")
    client = boto3.client("s3vectors", region_name=a.region)
    store = S3VectorsStore(client, bucket=a.bucket, index=a.index)
    if a.teardown:
        store.teardown()
        print(f"deleted index {a.index} and bucket {a.bucket} (if empty) in {a.region}")
        return

    ch, vecs, qa, qv = acme_vectors(a.model)
    est = s3vectors_monthly(len(ch), vecs.shape[1], 1000)
    print(f"about to create s3vectors bucket '{a.bucket}' / index '{a.index}' in {a.region} and upload "
          f"{len(ch)} vectors x {vecs.shape[1]} dims (estimated ${est['total']:.4f}/month at 1k queries)")
    if not a.yes and input("continue? [y/N] ").strip().lower() != "y":
        return
    try:
        store.create_index(vecs.shape[1])
    except Exception as exc:
        if "Conflict" in type(exc).__name__ or "exist" in str(exc).lower():
            print("index exists: reusing it")
            store.dim = vecs.shape[1]
        else:
            raise
    store.add(ch, vecs)
    print(f"stored {len(store)} vectors")

    base = numpy_store(ch, vecs)
    agree = []
    for v in qv:
        got = {h.chunk.id for h in store.search(v, 10)}
        want = {h.chunk.id for h in base.search(v, 10)}
        agree.append(len(got & want) / 10)
    print(f"agree@10 with exact numpy over {len(qv)} golden questions: {np.mean(agree):.3f} "
          "(AWS promises 90%+ average recall; on 210 vectors expect ~1.0)")
    q = next(i for i, x in enumerate(qa) if x["id"] == "q014")
    for role in ("engineering", "contractor"):
        hits = store.search(qv[q], 5, where=acl_where(role))
        print(f"  {role:<12} {qa[q]['question'][:50]}... -> "
              + ", ".join(f"{h.chunk.doc_id}[{h.chunk.classification}]" for h in hits))
    print(f"\nteardown when done:\n  python labs/11-managed-vectors/s3vectors_demo.py --bucket {a.bucket} "
          f"--region {a.region} --teardown")


if __name__ == "__main__":
    main()
