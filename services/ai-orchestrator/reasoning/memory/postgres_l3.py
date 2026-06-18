"""
PostgresTierStore — production-grade L3 backend (Phase 2 wire).

Drop-in replacement for InMemoryTierStore at the L3_CONSOLIDATED tier.
Same TierStore ABC — MemoryService swaps without code changes.

Behaviour:
  * put()   — INSERT memory_l3 row WITHOUT the embedding. Vector is
              filled in async by a background embedding job that calls
              llm-gateway /v1/embed (separate process — this commit
              ships the job module too).
  * get()   — SELECT by (tenant_id, record_id) — RLS-scoped via
              acquire_for_tenant.
  * list_all() — SELECT * FROM memory_l3 WHERE tenant_id — used by
              consolidate / promote / forget scans. Mirrors the
              in-memory contract.
  * delete() — DELETE one row by id; returns bool.
  * forget(tenant_id) — DELETE all tenant rows. Counts wiped.

For semantic similarity retrieval (the reason we picked pgvector over
plain Postgres), call `semantic_search()` — same module, different
method. MemoryService.retrieve() Phase 2 dispatches to this when the
backend is Postgres-backed.

K-1: every method uses acquire_for_tenant(tenant_id) which sets
LOCAL app.enterprise_id — the RLS policy then filters.
K-20: embedding_model recorded per row; semantic_search filters by
the current EMBEDDING_MODEL so model upgrade evicts cache misses.
"""
from __future__ import annotations

import json
import os
from typing import Optional
from uuid import UUID

import structlog

from .stores import TierStore
from .types import MemoryRecord, MemoryTier, MemoryType

log = structlog.get_logger()


# Current model name — read here so a single env-var flip evicts all
# stale embeddings on next query. Matches llm-gateway/providers.py
# EMBEDDING_MODEL.
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "bge-m3")


class PostgresTierStore(TierStore):
    """Postgres + pgvector backend for L3 memory.

    Constructor takes an acquire_for_tenant async-context-manager
    factory so tests can inject a mock without monkey-patching the
    shared.db module.
    """

    def __init__(self, *, acquire_for_tenant, tier: MemoryTier = MemoryTier.L3_CONSOLIDATED):
        self.tier = tier
        self._acquire = acquire_for_tenant

    # ─── Write ────────────────────────────────────────────────────

    async def put(self, record: MemoryRecord) -> MemoryRecord:
        """Insert a memory row WITHOUT the embedding. The bg embedding
        job (embedding_worker.py) fills the vector later.

        Gap 2 (chaos-matrix.md 2026-05-20): wrapped in retry_db_write
        so a transient pgvector pool blip doesn't lose the write on
        first try. After exhaustion raises DbWriteExhausted — caller
        (MemoryService.write) decides whether to absorb best-effort
        or surface to the user."""
        record.tier = self.tier

        async def _do():
            async with self._acquire(record.tenant_id) as conn:
                await conn.execute(
                    """INSERT INTO memory_l3
                           (record_id, tenant_id, memory_type, content,
                            session_id, entity_id, occurred_at,
                            user_flagged_important, linked_outcome_value,
                            session_appearance_count, extra_metadata,
                            confidence, trust_source, last_verified_at)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::jsonb,
                               $12, $13, $14)
                       ON CONFLICT (record_id) DO UPDATE
                         SET content = EXCLUDED.content,
                             session_appearance_count = memory_l3.session_appearance_count
                                                        + EXCLUDED.session_appearance_count,
                             -- ADR-0032: confidence is monotonic via put —
                             -- reinforce() RAISES it (EXCLUDED higher → wins),
                             -- an ordinary re-write never LOWERS it. Fading is
                             -- modelled by the age-decay trust score, not by
                             -- shrinking the stored confidence.
                             confidence = GREATEST(memory_l3.confidence,
                                                   EXCLUDED.confidence),
                             -- ADR-0030: verify() supplies last_verified_at so it
                             -- persists; a NULL incoming keeps the existing stamp.
                             last_verified_at = COALESCE(EXCLUDED.last_verified_at,
                                                         memory_l3.last_verified_at),
                             trust_source = COALESCE(EXCLUDED.trust_source,
                                                     memory_l3.trust_source),
                             updated_at = NOW()""",
                    record.record_id, record.tenant_id,
                    record.memory_type.value, record.content,
                    record.session_id, record.entity_id,
                    record.occurred_at, record.user_flagged_important,
                    record.linked_outcome_value,
                    record.session_appearance_count,
                    json.dumps(record.metadata, ensure_ascii=False),
                    record.confidence, record.trust_source,
                    record.last_verified_at,
                )

        from ai_orchestrator.shared.db_retry import retry_db_write
        await retry_db_write("memory_l3.put", _do)
        return record

    # ─── Read ─────────────────────────────────────────────────────

    async def get(self, tenant_id: UUID, record_id: UUID) -> Optional[MemoryRecord]:
        async with self._acquire(tenant_id) as conn:
            row = await conn.fetchrow(
                """SELECT record_id, tenant_id, memory_type, content,
                          session_id, entity_id, occurred_at,
                          user_flagged_important, linked_outcome_value,
                          session_appearance_count, extra_metadata,
                          confidence, trust_source, last_verified_at
                   FROM memory_l3
                   WHERE record_id = $1""",
                record_id,
            )
        return self._row_to_record(row) if row else None

    async def list_all(self, tenant_id: UUID) -> list[MemoryRecord]:
        async with self._acquire(tenant_id) as conn:
            rows = await conn.fetch(
                """SELECT record_id, tenant_id, memory_type, content,
                          session_id, entity_id, occurred_at,
                          user_flagged_important, linked_outcome_value,
                          session_appearance_count, extra_metadata,
                          confidence, trust_source, last_verified_at
                   FROM memory_l3
                   ORDER BY occurred_at DESC"""
            )
        return [self._row_to_record(r) for r in rows]

    async def semantic_search(
        self, tenant_id: UUID, query_embedding: list[float], *,
        top_k: int = 5, model_name: Optional[str] = None,
    ) -> list[tuple[MemoryRecord, float]]:
        """Return top-k records ordered by cosine similarity to
        query_embedding. Returns (record, distance) tuples; distance
        is the pgvector cosine distance (smaller = more similar).

        K-20 — filters by embedding_model so a model upgrade gives
        zero results until the bg job re-embeds (preferable to
        returning stale-model neighbours)."""
        model = model_name or EMBEDDING_MODEL
        async with self._acquire(tenant_id) as conn:
            rows = await conn.fetch(
                """SELECT record_id, tenant_id, memory_type, content,
                          session_id, entity_id, occurred_at,
                          user_flagged_important, linked_outcome_value,
                          session_appearance_count, extra_metadata,
                          confidence, trust_source, last_verified_at,
                          embedding <=> $1 AS distance
                   FROM memory_l3
                   WHERE embedding IS NOT NULL
                     AND embedding_model = $2
                   ORDER BY embedding <=> $1
                   LIMIT $3""",
                _vec_to_pg(query_embedding), model, top_k,
            )
        return [(self._row_to_record(r), float(r["distance"])) for r in rows]

    # ─── Embedding fill (called by bg worker) ─────────────────────

    async def set_embedding(
        self, tenant_id: UUID, record_id: UUID,
        embedding: list[float], *, model_name: Optional[str] = None,
    ) -> bool:
        """Bg worker entrypoint. Returns True when a row was updated."""
        model = model_name or EMBEDDING_MODEL
        async with self._acquire(tenant_id) as conn:
            row = await conn.fetchrow(
                """UPDATE memory_l3
                   SET embedding = $1, embedding_model = $2, updated_at = NOW()
                   WHERE record_id = $3 AND tenant_id = $4
                   RETURNING record_id""",
                _vec_to_pg(embedding), model, record_id, tenant_id,
            )
        return row is not None

    async def list_unembedded(
        self, tenant_id: UUID, *, limit: int = 100,
    ) -> list[MemoryRecord]:
        """Bg worker scan — find rows without an embedding yet."""
        async with self._acquire(tenant_id) as conn:
            rows = await conn.fetch(
                """SELECT record_id, tenant_id, memory_type, content,
                          session_id, entity_id, occurred_at,
                          user_flagged_important, linked_outcome_value,
                          session_appearance_count, extra_metadata,
                          confidence, trust_source, last_verified_at
                   FROM memory_l3
                   WHERE embedding IS NULL
                   ORDER BY created_at ASC
                   LIMIT $1""",
                limit,
            )
        return [self._row_to_record(r) for r in rows]

    # ─── Delete / forget ──────────────────────────────────────────

    async def delete(self, tenant_id: UUID, record_id: UUID) -> bool:
        async with self._acquire(tenant_id) as conn:
            result = await conn.execute(
                "DELETE FROM memory_l3 WHERE record_id = $1",
                record_id,
            )
        return result.endswith(" 1")

    async def forget(self, tenant_id: UUID) -> int:
        """RLS-scoped DELETE wipes only the tenant's rows."""
        async with self._acquire(tenant_id) as conn:
            row = await conn.fetchrow(
                "DELETE FROM memory_l3 RETURNING COUNT(*) OVER () AS c",
            )
        return int(row["c"]) if row else 0

    # ─── Helpers ──────────────────────────────────────────────────

    def _row_to_record(self, row) -> MemoryRecord:
        meta = row["extra_metadata"]
        if isinstance(meta, str):
            meta = json.loads(meta)
        return MemoryRecord(
            tenant_id=row["tenant_id"],
            memory_type=MemoryType(row["memory_type"]),
            content=row["content"],
            record_id=row["record_id"],
            tier=self.tier,
            occurred_at=row["occurred_at"],
            session_id=row["session_id"],
            entity_id=row["entity_id"],
            session_appearance_count=row["session_appearance_count"],
            user_flagged_important=row["user_flagged_important"],
            linked_outcome_value=float(row["linked_outcome_value"]),
            metadata=meta or {},
            confidence=float(row["confidence"]),     # NOT NULL (default 0.70)
            trust_source=row["trust_source"],         # nullable
            last_verified_at=row["last_verified_at"], # nullable
        )


def _vec_to_pg(v: list[float]) -> str:
    """pgvector accepts the literal '[1,2,3]' format on parameter
    binding. asyncpg uses this string repr when binding to a VECTOR
    column."""
    return "[" + ",".join(repr(float(x)) for x in v) + "]"
