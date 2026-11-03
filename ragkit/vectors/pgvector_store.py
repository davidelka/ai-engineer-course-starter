"""PgVectorStore: the VectorStore contract on PostgreSQL + pgvector (lesson 11).

    store = PgVectorStore("postgresql://ragkit:ragkit@localhost:5432/ragkit", table="acme_chunks",
                          index="hnsw", m=16, ef_construction=64, ef_search=40)
    dense = DenseRetriever(embedder, store=store)

Requires `pip install "psycopg[binary]" pgvector` and a server with the `vector` extension
(labs/11-managed-vectors/compose.yaml runs pgvector/pgvector:0.8.7-pg18 locally; on AWS,
Aurora PostgreSQL / RDS for PostgreSQL ship pgvector: CREATE EXTENSION vector).

The table (one row per chunk):
    id text PRIMARY KEY, doc_id text NOT NULL, meta jsonb, chunk jsonb, embedding vector(d)
    + a btree index on doc_id (remove(doc_id), filters) and a GIN index on meta (jsonb filters)
    + the ANN index:  USING hnsw (embedding vector_cosine_ops) WITH (m, ef_construction)
                  or  USING ivfflat (embedding vector_cosine_ops) WITH (lists)

Query-time knobs are session settings, set with SET LOCAL inside the query's transaction:
    hnsw.ef_search          candidate list size (default 40). Also an upper bound on how
                            many rows ONE index scan can return: LIMIT 100 with ef_search 40
                            returns at most 40 rows unless iterative scans are on.
    hnsw.iterative_scan     off | relaxed_order | strict_order (pgvector >= 0.8.0). With a
                            WHERE clause, Postgres filters AFTER the index scan; a selective
                            filter can then leave fewer than k rows. Iterative scans keep
                            walking the graph until enough rows pass the filter (up to
                            hnsw.max_scan_tuples, default 20000).
    ivfflat.probes          lists searched (default 1)

Operators: <=> cosine distance, <-> L2 distance, <#> NEGATIVE inner product. ragkit scores
are "higher is better": cosine 1 - d, dot -d, l2 -d*d.

Everything that builds SQL is a pure function (schema_sql, index_sql, search_sql), so the
SQL can be unit-tested without a database; PgVectorStore only executes it.
"""

from __future__ import annotations

import json
from typing import Optional, Sequence

import numpy as np

from ..retrieval.base import Where
from ..types import Chunk, Hit
from .base import METRICS, check_batch
from .filters import to_sql_where

OPS = {"cosine": ("<=>", "vector_cosine_ops"), "l2": ("<->", "vector_l2_ops"),
       "dot": ("<#>", "vector_ip_ops")}
ITERATIVE = ("off", "relaxed_order", "strict_order")


def _ident(name: str) -> str:
    if not name.replace("_", "").isalnum() or name[0].isdigit():
        raise ValueError(f"unsafe SQL identifier {name!r}")
    return name


def schema_sql(table: str, dim: int, *, halfvec: bool = False) -> list[str]:
    t = _ident(table)
    vtype = f"halfvec({dim})" if halfvec else f"vector({dim})"
    return ["CREATE EXTENSION IF NOT EXISTS vector",
            f"CREATE TABLE IF NOT EXISTS {t} (id text PRIMARY KEY, doc_id text NOT NULL, "
            f"meta jsonb NOT NULL DEFAULT '{{}}', chunk jsonb NOT NULL, embedding {vtype} NOT NULL)",
            f"CREATE INDEX IF NOT EXISTS {t}_doc_id ON {t} (doc_id)",
            f"CREATE INDEX IF NOT EXISTS {t}_meta ON {t} USING gin (meta)"]


def index_sql(table: str, metric: str = "cosine", kind: str = "hnsw", *, m: int = 16,
              ef_construction: int = 64, lists: int = 100, halfvec: bool = False) -> Optional[str]:
    """The ANN index. kind: "hnsw" | "ivfflat" | None (exact scan, the baseline)."""
    if kind in (None, "none", "exact"):
        return None
    t = _ident(table)
    opclass = OPS[metric][1].replace("vector_", "halfvec_") if halfvec else OPS[metric][1]
    if kind == "hnsw":
        return (f"CREATE INDEX IF NOT EXISTS {t}_hnsw ON {t} USING hnsw (embedding {opclass}) "
                f"WITH (m = {int(m)}, ef_construction = {int(ef_construction)})")
    if kind == "ivfflat":
        return (f"CREATE INDEX IF NOT EXISTS {t}_ivfflat ON {t} USING ivfflat (embedding {opclass}) "
                f"WITH (lists = {int(lists)})")
    raise ValueError("index must be 'hnsw', 'ivfflat' or None")


def session_sql(*, ef_search: Optional[int] = None, iterative_scan: Optional[str] = None,
                max_scan_tuples: Optional[int] = None, probes: Optional[int] = None,
                exact: bool = False) -> list[str]:
    """SET LOCAL statements for one search transaction (integers are inlined after int())."""
    out = []
    if exact:
        out.append("SET LOCAL enable_indexscan = off")    # force the exact sequential scan
    if ef_search is not None:
        out.append(f"SET LOCAL hnsw.ef_search = {int(ef_search)}")
    if iterative_scan is not None:
        if iterative_scan not in ITERATIVE:
            raise ValueError(f"iterative_scan must be one of {ITERATIVE}")
        out.append(f"SET LOCAL hnsw.iterative_scan = {iterative_scan}")
    if max_scan_tuples is not None:
        out.append(f"SET LOCAL hnsw.max_scan_tuples = {int(max_scan_tuples)}")
    if probes is not None:
        out.append(f"SET LOCAL ivfflat.probes = {int(probes)}")
    return out


def search_sql(table: str, metric: str, k: int, where: Where = None, *,
               halfvec: bool = False) -> tuple[str, list]:
    """SELECT ... ORDER BY embedding <op> %s LIMIT k. Params: [query, *filter params, query]."""
    t = _ident(table)
    op = OPS[metric][0]
    cast = "::halfvec" if halfvec else "::vector"
    cond, params = to_sql_where(where)
    sql = (f"SELECT chunk, embedding {op} %s{cast} AS distance FROM {t} WHERE {cond} "
           f"ORDER BY embedding {op} %s{cast} LIMIT {int(k)}")
    return sql, ["Q"] + params + ["Q"]


def to_score(distance: float, metric: str) -> float:
    if metric == "cosine":
        return 1.0 - distance
    if metric == "dot":
        return -distance
    return -distance * distance


def vector_literal(v) -> str:
    """pgvector's text format '[1,2,3]' (works without the pgvector Python package)."""
    return "[" + ",".join(repr(float(x)) for x in np.asarray(v, dtype=np.float32).reshape(-1)) + "]"


class PgVectorStore:
    def __init__(self, dsn: Optional[str] = None, dim: Optional[int] = None, metric: str = "cosine", *,
                 conn=None, table: str = "ragkit_chunks", index: Optional[str] = "hnsw", m: int = 16,
                 ef_construction: int = 64, lists: int = 100, ef_search: Optional[int] = None,
                 iterative_scan: Optional[str] = None, max_scan_tuples: Optional[int] = None,
                 probes: Optional[int] = None, halfvec: bool = False, recreate: bool = False):
        if metric not in METRICS:
            raise ValueError(f"metric must be one of {METRICS}")
        if conn is None:
            if not dsn:
                raise ValueError("PgVectorStore needs a dsn (postgresql://...) or a connection")
            try:
                import psycopg  # type: ignore
            except ImportError as exc:  # pragma: no cover
                raise ImportError('PgVectorStore needs psycopg: uv pip install "psycopg[binary]" pgvector') from exc
            conn = psycopg.connect(dsn, autocommit=False)
        self.conn = conn
        self.table = _ident(table)
        self.dim, self.metric, self.kind = dim, metric, index
        self.m, self.ef_construction, self.lists = m, ef_construction, lists
        self.ef_search, self.iterative_scan, self.max_scan_tuples, self.probes = (
            ef_search, iterative_scan, max_scan_tuples, probes)
        self.halfvec = halfvec
        self.name = f"pgvector:{table}"
        self._ready = False
        if recreate:
            self._exec([f"DROP TABLE IF EXISTS {self.table}"])
        if dim is not None:
            self._create(dim)

    # ------------------------------------------------------------------ helpers
    def _exec(self, statements: Sequence[str], params: Sequence = ()) -> None:
        with self.conn.cursor() as cur:
            for s in statements:
                cur.execute(s, params or None)
        self.conn.commit()

    def _create(self, dim: int) -> None:
        stmts = schema_sql(self.table, dim, halfvec=self.halfvec)
        # The ANN index is created up front: pgvector maintains HNSW incrementally on insert.
        # For a big initial load it is faster to load first and CREATE INDEX afterwards
        # (with maintenance_work_mem large enough to hold the graph): see build_index().
        ix = index_sql(self.table, self.metric, self.kind, m=self.m,
                       ef_construction=self.ef_construction, lists=self.lists, halfvec=self.halfvec)
        if ix and self.kind == "hnsw":
            stmts.append(ix)
        self._exec(stmts)
        self.dim, self._ready = dim, True

    def build_index(self) -> None:
        """Create the ANN index now (IVFFlat must be built AFTER data: it k-means the rows)."""
        ix = index_sql(self.table, self.metric, self.kind, m=self.m,
                       ef_construction=self.ef_construction, lists=self.lists, halfvec=self.halfvec)
        if ix:
            self._exec([ix])

    # ------------------------------------------------------------------ contract
    def __len__(self) -> int:
        if not self._ready:
            return 0
        with self.conn.cursor() as cur:
            cur.execute(f"SELECT count(*) FROM {self.table}")
            n = cur.fetchone()[0]
        self.conn.commit()
        return int(n)

    def add(self, chunks: Sequence[Chunk], vectors) -> None:
        chunks = list(chunks)
        if not chunks:
            return
        v = check_batch(chunks, vectors, self.dim)
        if not self._ready:
            self._create(v.shape[1])
        cast = "halfvec" if self.halfvec else "vector"
        sql = (f"INSERT INTO {self.table} (id, doc_id, meta, chunk, embedding) "
               f"VALUES (%s, %s, %s::jsonb, %s::jsonb, %s::{cast}) "
               f"ON CONFLICT (id) DO UPDATE SET doc_id = EXCLUDED.doc_id, meta = EXCLUDED.meta, "
               f"chunk = EXCLUDED.chunk, embedding = EXCLUDED.embedding")
        rows = [(c.id, c.doc_id, json.dumps(c.meta, ensure_ascii=False),
                 json.dumps(c.to_dict(), ensure_ascii=False), vector_literal(row))
                for c, row in zip(chunks, v)]
        with self.conn.cursor() as cur:
            cur.executemany(sql, rows)
        self.conn.commit()

    def remove(self, doc_id: str) -> int:
        if not self._ready:
            return 0
        with self.conn.cursor() as cur:
            cur.execute(f"DELETE FROM {self.table} WHERE doc_id = %s", (doc_id,))
            n = cur.rowcount
        self.conn.commit()
        # A deleted row leaves a "tombstone" in the HNSW graph until VACUUM repairs the
        # neighbours that pointed at it; heavy churn -> schedule VACUUM (or REINDEX).
        return int(n or 0)

    def search(self, vector, k: int = 5, where: Where = None, *, ef: Optional[int] = None,
               exact: bool = False) -> list[Hit]:
        if not self._ready:
            return []
        sql, params = search_sql(self.table, self.metric, k, where, halfvec=self.halfvec)
        q = vector_literal(vector)
        params = [q if p == "Q" and i in (0, len(params) - 1) else p for i, p in enumerate(params)]
        sets = session_sql(ef_search=ef if ef is not None else self.ef_search,
                           iterative_scan=self.iterative_scan, max_scan_tuples=self.max_scan_tuples,
                           probes=self.probes, exact=exact)
        with self.conn.cursor() as cur:
            for s in sets:
                cur.execute(s)
            cur.execute(sql, params)
            rows = cur.fetchall()
        self.conn.commit()                         # ends the transaction: SET LOCAL resets
        hits = []
        for i, (chunk, dist) in enumerate(rows):
            d = chunk if isinstance(chunk, dict) else json.loads(chunk)
            s = to_score(float(dist), self.metric)
            hits.append(Hit(chunk=Chunk.from_dict(d), score=s, rank=i + 1, scores={"vector": s},
                            retriever=self.name))
        return hits

    def explain(self, vector, k: int = 5, where: Where = None) -> str:
        """EXPLAIN ANALYZE of a search: shows whether the HNSW index was used, and how many
        rows the filter removed after the index scan ("Rows Removed by Filter")."""
        sql, params = search_sql(self.table, self.metric, k, where, halfvec=self.halfvec)
        q = vector_literal(vector)
        params = [q if p == "Q" and i in (0, len(params) - 1) else p for i, p in enumerate(params)]
        with self.conn.cursor() as cur:
            for s in session_sql(ef_search=self.ef_search, iterative_scan=self.iterative_scan):
                cur.execute(s)
            cur.execute("EXPLAIN (ANALYZE, BUFFERS) " + sql, params)
            out = "\n".join(r[0] for r in cur.fetchall())
        self.conn.commit()
        return out


__all__ = ["PgVectorStore", "schema_sql", "index_sql", "session_sql", "search_sql", "to_score",
           "vector_literal", "OPS", "ITERATIVE"]
