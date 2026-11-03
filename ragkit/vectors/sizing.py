"""Memory and monthly-cost estimates for vector indexes (lesson 11).

Memory model (HNSW, the layout hnswlib/FAISS/pgvector/Qdrant all approximate)
  vector bytes        dim x bytes per dimension (float32 4, float16 2, int8 1, binary 1/8,
                      PQ = pq_bytes per vector)
  graph bytes/node    layer 0 keeps up to 2*M neighbor ids (4 bytes each) + a 4-byte count;
                      a node reaches layer >= 1 with probability 1/M, so it has on average
                      1/(M-1) upper layers, each with up to M ids + count:
                      (2M*4 + 4) + (M*4 + 4) / (M - 1)          M=16 -> ~136.5 bytes
  quantized index     RAM = quantized vectors + graph (+ the float32 originals if they also
                      stay in RAM; usually they go to disk and are read only for rescoring)
Real systems add per-point overhead (ids, payload, allocator slack); multiply by ~1.2-1.5
for capacity planning and MEASURE (Qdrant telemetry, pg_relation_size) before buying.

Prices: AWS us-east-1 list prices as published in November 2026 (sources in PRICES_SOURCES).
They change; the lab prints the date next to every number. Every estimate states its
assumptions, because the hard part of vector-DB cost is assumptions, not arithmetic.
"""

from __future__ import annotations

import math
from typing import Optional

GIB = 1024 ** 3
HOURS = 730                     # hours per month (AWS convention)
BYTES_PER_DIM = {"float32": 4.0, "float16": 2.0, "int8": 1.0, "binary": 1 / 8}

PRICES_DATE = "2026-11"
PRICES = {
    # Amazon S3 Vectors (GA 2025-12-02; >10M-vector query tier cut ~80% in June 2026)
    "s3v_storage_gb_month": 0.06,
    "s3v_put_gb": 0.20,
    "s3v_query_per_1000": 0.0025,
    "s3v_tb_first_100k": 0.004,          # $ per TB of index data processed per query,
    "s3v_tb_100k_to_10m": 0.002,         #   tiered by the number of vectors in the index
    "s3v_tb_over_10m": 0.0004,
    # Amazon OpenSearch Serverless
    "aoss_ocu_hour": 0.24,               # indexing and search OCUs, each ~6 GiB RAM
    "aoss_storage_gb_month": 0.024,      # managed storage (S3-backed)
    "aoss_classic_min_ocu": 2.0,         # classic: 1 indexing + 1 search (dev/test: 0.5 + 0.5)
    # Aurora PostgreSQL Serverless (formerly "Serverless v2"), Aurora Standard
    "aurora_acu_hour": 0.12,             # 1 ACU ~ 2 GiB RAM; min 0 ACU = auto-pause
    "aurora_storage_gb_month": 0.10,
    # Self-hosted on EC2 (Qdrant or Postgres in Docker), on-demand Linux, approximate
    "ec2_r7g_large_hour": 0.1071,        # 2 vCPU, 16 GiB
    "ec2_r7g_xlarge_hour": 0.2142,       # 4 vCPU, 32 GiB
    "ebs_gp3_gb_month": 0.08,
    # Pinecone serverless, Standard plan (not AWS-native; for comparison only)
    "pinecone_min_month": 50.0,
    "pinecone_storage_gb_month": 0.33,
}
PRICES_SOURCES = [
    "https://aws.amazon.com/s3/pricing/ (S3 Vectors tab)",
    "https://aws.amazon.com/opensearch-service/pricing/",
    "https://aws.amazon.com/rds/aurora/pricing/",
    "https://aws.amazon.com/ec2/pricing/on-demand/",
    "https://www.pinecone.io/pricing/",
]


def bytes_per_vector(dim: int, quantization: Optional[str] = None, pq_bytes: Optional[int] = None) -> float:
    q = quantization or "float32"
    if q == "pq":
        return float(pq_bytes if pq_bytes is not None else max(1, dim // 8))
    if q == "binary":
        return float(math.ceil(dim / 8))
    if q in ("scalar",):
        q = "int8"
    if q not in BYTES_PER_DIM:
        raise ValueError(f"unknown quantization {quantization!r}")
    return dim * BYTES_PER_DIM[q]


def graph_bytes_per_node(m: int = 16) -> float:
    if m < 2:
        return 0.0                      # m=0: no global graph (Qdrant per-tenant mode)
    return (2 * m * 4 + 4) + (m * 4 + 4) / (m - 1)


def hnsw_ram_bytes(n: int, dim: int, *, m: int = 16, quantization: Optional[str] = None,
                   originals_in_ram: Optional[bool] = None, pq_bytes: Optional[int] = None) -> dict:
    """RAM (and disk) for an HNSW index of n vectors. Returns a dict of byte counts:
    vectors_ram, quantized_ram, graph_ram, originals_disk, total_ram."""
    q = quantization if quantization not in (None, "float32") else None
    if originals_in_ram is None:
        originals_in_ram = q is None
    orig = n * dim * 4.0
    quant = n * bytes_per_vector(dim, q, pq_bytes) if q else 0.0
    graph = n * graph_bytes_per_node(m)
    vec_ram = orig if originals_in_ram else 0.0
    return {"vectors_ram": vec_ram, "quantized_ram": quant, "graph_ram": graph,
            "originals_disk": 0.0 if originals_in_ram else orig,
            "total_ram": vec_ram + quant + graph}


def raw_gb(n: int, dim: int, metadata_bytes: int = 0) -> float:
    return n * (dim * 4 + metadata_bytes) / GIB


# ---------------------------------------------------------------- monthly cost models
def s3vectors_monthly(n: int, dim: int, queries: int, *, filterable_md: int = 200,
                      nonfilterable_md: int = 1500, updates_fraction: float = 0.05) -> dict:
    """Amazon S3 Vectors: storage + PUTs + per-query fees. Query data processed = the index's
    vector data + filterable metadata (non-filterable metadata is not counted), tiered by the
    number of vectors. `updates_fraction`: share of vectors re-PUT per month (re-embeddings,
    edits); the initial load is reported separately as one-off."""
    p = PRICES
    per_vec = dim * 4 + filterable_md + nonfilterable_md
    storage = n * per_vec / GIB * p["s3v_storage_gb_month"]
    initial_put = n * max(per_vec, 0) / GIB * p["s3v_put_gb"]
    monthly_put = initial_put * updates_fraction
    tb_per_vec = (dim * 4 + filterable_md) / 1024 ** 4
    tiers = [(min(n, 100_000), p["s3v_tb_first_100k"]),
             (max(0, min(n, 10_000_000) - 100_000), p["s3v_tb_100k_to_10m"]),
             (max(0, n - 10_000_000), p["s3v_tb_over_10m"])]
    per_query = p["s3v_query_per_1000"] / 1000 + sum(cnt * tb_per_vec * price for cnt, price in tiers)
    query = queries * per_query
    total = storage + monthly_put + query
    return {"option": "S3 Vectors", "storage": storage, "writes": monthly_put, "queries": query,
            "compute": 0.0, "total": total, "one_off_load": initial_put, "per_query": per_query,
            "assumes": f"{filterable_md} B filterable + {nonfilterable_md} B non-filterable metadata "
                       f"per vector; {updates_fraction:.0%} of vectors re-written per month; no idle cost"}


def opensearch_serverless_monthly(n: int, dim: int, *, m: int = 16, quantization: Optional[str] = None,
                                  generation: str = "classic", active_hours: float = HOURS,
                                  ram_fraction: float = 0.5, dev_test: bool = False) -> dict:
    """OpenSearch Serverless vector collection. ASSUMPTION (verify in the AWS calculator):
    about `ram_fraction` of each search OCU's 6 GiB can hold the HNSW graph+vectors, and
    indexing OCUs = 1 (steady trickle of updates). classic: billed every hour, at least
    aoss_classic_min_ocu (dev/test halves it). nextgen: scales to zero, billed for
    `active_hours` (+10 idle minutes after the last request, folded into active_hours)."""
    p = PRICES
    ram = hnsw_ram_bytes(n, dim, m=m, quantization=quantization)["total_ram"]
    search_ocu = max(1.0, math.ceil(ram / (6 * GIB * ram_fraction)))
    index_ocu = 1.0
    ocu = search_ocu + index_ocu
    if generation == "classic":
        floor = p["aoss_classic_min_ocu"] / (2 if dev_test else 1)
        ocu = max(ocu if not dev_test else ocu / 2, floor)
        hours = HOURS
    else:
        hours = active_hours
    compute = ocu * hours * p["aoss_ocu_hour"]
    storage = raw_gb(n, dim, 1500) * p["aoss_storage_gb_month"]
    return {"option": f"OpenSearch Serverless ({generation}{', dev/test' if dev_test else ''})",
            "storage": storage, "writes": 0.0, "queries": 0.0, "compute": compute,
            "total": compute + storage, "ocu": ocu,
            "assumes": f"{search_ocu:.0f} search + {index_ocu:.0f} indexing OCU(s), {ram_fraction:.0%} of "
                       f"6 GiB per OCU usable for the index, {hours:.0f} billed hours"}


def aurora_pgvector_monthly(n: int, dim: int, *, m: int = 16, halfvec: bool = False,
                            active_hours: float = HOURS, ram_fraction: float = 0.6,
                            min_acu: float = 0.5) -> dict:
    """Aurora PostgreSQL Serverless + pgvector HNSW. ASSUMPTION: the HNSW index should fit in
    ~`ram_fraction` of the ACUs' memory (2 GiB per ACU) to avoid disk reads."""
    p = PRICES
    ram = hnsw_ram_bytes(n, dim, m=m, quantization="float16" if halfvec else None,
                         originals_in_ram=not halfvec)["total_ram"]
    acu = max(min_acu, math.ceil(ram / (2 * GIB * ram_fraction) * 2) / 2)
    compute = acu * active_hours * p["aurora_acu_hour"]
    table_gb = raw_gb(n, dim, 1500) * (0.5 if halfvec else 1.0) + ram / GIB
    storage = table_gb * p["aurora_storage_gb_month"]
    return {"option": f"Aurora Serverless + pgvector{' (halfvec)' if halfvec else ''}",
            "storage": storage, "writes": 0.0, "queries": 0.0, "compute": compute,
            "total": compute + storage, "acu": acu,
            "assumes": f"{acu:g} ACU for {active_hours:.0f} h; table+index on Aurora storage; "
                       "I/O charges not included"}


def ec2_qdrant_monthly(n: int, dim: int, *, m: int = 16, quantization: Optional[str] = "scalar",
                       disk_gb: Optional[float] = None) -> dict:
    """Self-hosted Qdrant on one EC2 instance (no replica). Picks r7g.large (16 GiB) or
    r7g.xlarge (32 GiB) by RAM need x1.5 headroom; beyond that: shard across nodes."""
    p = PRICES
    ram = hnsw_ram_bytes(n, dim, m=m, quantization=quantization)["total_ram"] * 1.5
    if ram <= 12 * GIB:
        inst, hourly = "r7g.large", p["ec2_r7g_large_hour"]
        nodes = 1
    else:
        inst, hourly = "r7g.xlarge", p["ec2_r7g_xlarge_hour"]
        nodes = max(1, math.ceil(ram / (26 * GIB)))
    disk = disk_gb if disk_gb is not None else max(20.0, 2 * raw_gb(n, dim, 1500))
    compute = nodes * hourly * HOURS
    storage = disk * p["ebs_gp3_gb_month"]
    return {"option": f"EC2 + Qdrant ({nodes} x {inst})", "storage": storage, "writes": 0.0,
            "queries": 0.0, "compute": compute, "total": compute + storage, "nodes": nodes,
            "assumes": f"{quantization or 'float32'} vectors in RAM with x1.5 headroom, originals on "
                       f"{disk:.0f} GB gp3; no replica, backups, or your time"}


def pinecone_monthly(n: int, dim: int) -> dict:
    p = PRICES
    storage = raw_gb(n, dim, 1500) * p["pinecone_storage_gb_month"]
    total = max(p["pinecone_min_month"], storage)
    return {"option": "Pinecone Standard (storage only)", "storage": storage, "writes": 0.0,
            "queries": 0.0, "compute": 0.0, "total": total,
            "assumes": "read/write units NOT included (they depend on namespace size and traffic); "
                       "$50 monthly minimum"}


def compare(n: int, dim: int, queries: int, **kw) -> list[dict]:
    return [s3vectors_monthly(n, dim, queries),
            opensearch_serverless_monthly(n, dim, generation="classic"),
            opensearch_serverless_monthly(n, dim, generation="nextgen", active_hours=kw.get("active_hours", 200)),
            aurora_pgvector_monthly(n, dim),
            aurora_pgvector_monthly(n, dim, halfvec=True),
            ec2_qdrant_monthly(n, dim),
            pinecone_monthly(n, dim)]


__all__ = ["PRICES", "PRICES_DATE", "PRICES_SOURCES", "bytes_per_vector", "graph_bytes_per_node",
           "hnsw_ram_bytes", "raw_gb", "s3vectors_monthly", "opensearch_serverless_monthly",
           "aurora_pgvector_monthly", "ec2_qdrant_monthly", "pinecone_monthly", "compare"]
