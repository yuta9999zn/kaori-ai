"""KnowledgeStore — Postgres + pgvector backend for the domain knowledge base.

Mirrors reasoning/memory/postgres_l3.py: the constructor takes an
``acquire_for_tenant`` async-context-manager factory so tests inject a mock
without monkey-patching shared.db.

K-1: every method goes through acquire_for_tenant(enterprise_id), which sets
the RLS GUC. The migration-106 policy then exposes GLOBAL rows (tenant_id IS
NULL, tiers 1-3) + the tenant's OWN rows (tier 4), but only lets the tenant
WRITE its own. K-20: embedding_model pinned per row; semantic_search filters by
it so a model upgrade evicts stale vectors.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

import structlog

log = structlog.get_logger()

# Same env knob as memory/postgres_l3 + llm-gateway so one flip evicts stale
# vectors everywhere.
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "bge-m3")


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


# ADR-0033 maturation — confidence climbs toward a per-TIER ceiling on each
# validated citation (reinforce). Foundational tiers cap higher than market /
# tenant (a curated formula earns more trust than a market heuristic). Never 1.0
# (epistemic humility). Mirrors the ADR-0032 memory learning curve.
_KB_LEARN_RATE = _env_float("KAORI_KB_LEARN_RATE", 0.12)
_KB_CONF_CEILING = {1: 0.98, 2: 0.95, 3: 0.85, 4: 0.80}   # regulatory>curated>market>tenant
_KB_DEFAULT_CEILING = 0.80


def kb_confidence_ceiling(tier: int) -> float:
    return _KB_CONF_CEILING.get(tier, _KB_DEFAULT_CEILING)


def kb_reinforced_confidence(tier: int, confidence: float,
                             learn_rate: float = _KB_LEARN_RATE) -> float:
    """One validated-citation step up the learning curve toward the tier ceiling
    (fast early, plateauing). A fact cited many times ends up trusted more."""
    ceiling = kb_confidence_ceiling(tier)
    return round(min(ceiling, confidence + learn_rate * (ceiling - confidence)), 4)


def _ceiling_case_sql(tier_col: str) -> str:
    """Render the per-tier ceiling as a SQL ``CASE`` built FROM ``_KB_CONF_CEILING``
    — the single source of truth, so ceilings aren't hardcoded twice (Python +
    inline SQL). Values are our own floats (no user input → no injection)."""
    whens = " ".join(f"WHEN {t} THEN {c}" for t, c in sorted(_KB_CONF_CEILING.items()))
    return f"CASE {tier_col} {whens} ELSE {_KB_DEFAULT_CEILING} END"


@dataclass
class KnowledgeDocument:
    """One knowledge entry. ``tenant_id`` NULL = global (tier 1-3); non-NULL =
    tenant-specific (tier 4). The migration CHECK enforces that scope."""
    title: str
    content: str
    tier: int
    document_id: UUID = field(default_factory=uuid4)
    tenant_id: Optional[UUID] = None
    category: Optional[str] = None
    source: Optional[str] = None
    source_url: Optional[str] = None
    lang: str = "vi"
    status: str = "active"
    tags: list = field(default_factory=list)
    distance: Optional[float] = None      # set by semantic_search
    created_at: Optional[datetime] = None
    # ADR-0033 aging + version history
    confidence: float = 0.70
    use_count: int = 0
    last_reinforced_at: Optional[datetime] = None
    valid_until: Optional[datetime] = None      # tier-3 freshness hint
    supersedes: Optional[UUID] = None           # this row replaced that one
    superseded_by: Optional[UUID] = None        # that row replaced this one
    change_reason: Optional[str] = None


class KnowledgeStore:
    def __init__(self, *, acquire_for_tenant, acquire_admin=None):
        self._acquire = acquire_for_tenant
        # Admin/cross-tenant acquire for maturing GLOBAL knowledge (tenant RLS
        # can't write tier 1-3 rows). Lazily defaults to acquire_cross_tenant.
        self._acquire_admin = acquire_admin

    # ─── Write ────────────────────────────────────────────────────
    async def put(
        self, doc: KnowledgeDocument, *,
        embedding: Optional[list[float]] = None,
        model_name: Optional[str] = None,
        scope_tenant_id: Optional[UUID] = None,
    ) -> UUID:
        """Insert/upsert a knowledge row. ``scope_tenant_id`` is the enterprise
        whose RLS GUC scopes the write (defaults to ``doc.tenant_id``) — pass it
        explicitly for the tenant path where doc.tenant_id == the caller."""
        model = model_name if embedding else None
        if embedding and model_name is None:
            model = EMBEDDING_MODEL
        scope = scope_tenant_id if scope_tenant_id is not None else doc.tenant_id
        async with self._acquire(scope) as conn:
            row = await conn.fetchrow(
                """INSERT INTO knowledge_documents
                       (document_id, tenant_id, tier, category, title, content,
                        source, source_url, lang, status, embedding,
                        embedding_model, tags,
                        confidence, valid_until, supersedes, change_reason)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13::jsonb,
                           $14, $15, $16, $17)
                   ON CONFLICT (document_id) DO UPDATE
                     SET title = EXCLUDED.title,
                         content = EXCLUDED.content,
                         category = EXCLUDED.category,
                         source = EXCLUDED.source,
                         source_url = EXCLUDED.source_url,
                         status = EXCLUDED.status,
                         embedding = EXCLUDED.embedding,
                         embedding_model = EXCLUDED.embedding_model,
                         tags = EXCLUDED.tags,
                         -- ADR-0033: confidence monotonic via put (reinforce
                         -- raises it; an ordinary re-write never lowers it).
                         confidence = GREATEST(knowledge_documents.confidence,
                                               EXCLUDED.confidence),
                         valid_until = EXCLUDED.valid_until,
                         supersedes = COALESCE(EXCLUDED.supersedes,
                                               knowledge_documents.supersedes),
                         change_reason = COALESCE(EXCLUDED.change_reason,
                                                  knowledge_documents.change_reason),
                         updated_at = NOW()
                   RETURNING document_id""",
                doc.document_id, doc.tenant_id, doc.tier, doc.category,
                doc.title, doc.content, doc.source, doc.source_url,
                doc.lang, doc.status,
                _vec_to_pg(embedding) if embedding else None, model,
                json.dumps(doc.tags, ensure_ascii=False),
                doc.confidence, doc.valid_until, doc.supersedes, doc.change_reason,
            )
        return row["document_id"] if row else doc.document_id

    async def set_embedding(
        self, scope_tenant_id: Optional[UUID], document_id: UUID,
        embedding: list[float], *, model_name: Optional[str] = None,
    ) -> bool:
        """Fill the embedding of a row landed without one (seeded global rows /
        bg re-embed). Returns True when a row was updated."""
        model = model_name or EMBEDDING_MODEL
        async with self._acquire(scope_tenant_id) as conn:
            row = await conn.fetchrow(
                """UPDATE knowledge_documents
                   SET embedding = $1, embedding_model = $2, updated_at = NOW()
                   WHERE document_id = $3
                   RETURNING document_id""",
                _vec_to_pg(embedding), model, document_id,
            )
        return row is not None

    # ─── Read ─────────────────────────────────────────────────────
    async def list_documents(
        self, scope_tenant_id: Optional[UUID], *,
        status: str = "active", category: Optional[str] = None,
        limit: int = 100,
    ) -> list[KnowledgeDocument]:
        """List rows visible to the tenant (RLS = global + own). ``category``
        optional filter."""
        async with self._acquire(scope_tenant_id) as conn:
            rows = await conn.fetch(
                """SELECT document_id, tenant_id, tier, category, title, content,
                          source, source_url, lang, status, tags, created_at
                   FROM knowledge_documents
                   WHERE status = $1
                     AND ($2::text IS NULL OR category = $2)
                   ORDER BY tier ASC, created_at DESC
                   LIMIT $3""",
                status, category, limit,
            )
        return [self._row_to_doc(r) for r in rows]

    async def semantic_search(
        self, scope_tenant_id: Optional[UUID], query_embedding: list[float], *,
        top_k: int = 5, model_name: Optional[str] = None,
        category: Optional[str] = None, status: str = "active",
    ) -> list[KnowledgeDocument]:
        """Top-k knowledge docs by cosine distance to ``query_embedding``.
        RLS exposes global + own; K-20 filters by embedding_model. Each returned
        doc carries ``distance`` (smaller = closer)."""
        model = model_name or EMBEDDING_MODEL
        async with self._acquire(scope_tenant_id) as conn:
            rows = await conn.fetch(
                """SELECT document_id, tenant_id, tier, category, title, content,
                          source, source_url, lang, status, tags, created_at,
                          confidence, use_count, last_reinforced_at,
                          embedding <=> $1 AS distance
                   FROM knowledge_documents
                   WHERE embedding IS NOT NULL
                     AND embedding_model = $2
                     AND status = $3
                     AND ($4::text IS NULL OR category = $4)
                   ORDER BY embedding <=> $1
                   LIMIT $5""",
                _vec_to_pg(query_embedding), model, status, category, top_k,
            )
        return [self._row_to_doc(r) for r in rows]

    async def list_unembedded(
        self, scope_tenant_id: Optional[UUID], *, limit: int = 100,
    ) -> list[KnowledgeDocument]:
        """Rows without an embedding yet (seeded global rows awaiting re-embed)."""
        async with self._acquire(scope_tenant_id) as conn:
            rows = await conn.fetch(
                """SELECT document_id, tenant_id, tier, category, title, content,
                          source, source_url, lang, status, tags, created_at
                   FROM knowledge_documents
                   WHERE embedding IS NULL AND status = 'active'
                   ORDER BY created_at ASC
                   LIMIT $1""",
                limit,
            )
        return [self._row_to_doc(r) for r in rows]

    # ─── Aging + version history (ADR-0033) ───────────────────────
    async def reinforce(self, scope_tenant_id: Optional[UUID], document_id: UUID) -> bool:
        """Validated-citation bump: confidence climbs toward its per-tier ceiling
        (foundational caps higher), use_count++, clock reset. Server-side so it's
        atomic under concurrent citations. Returns True if a row was updated."""
        async with self._acquire(scope_tenant_id) as conn:
            row = await conn.fetchrow(
                f"""UPDATE knowledge_documents AS k
                   SET confidence = LEAST(c.ceiling,
                                          k.confidence + $2 * (c.ceiling - k.confidence)),
                       use_count = k.use_count + 1,
                       last_reinforced_at = NOW(),
                       updated_at = NOW()
                   FROM (SELECT {_ceiling_case_sql('tier')} AS ceiling
                         FROM knowledge_documents WHERE document_id = $1) c
                   WHERE k.document_id = $1
                   RETURNING k.document_id""",
                document_id, _KB_LEARN_RATE,
            )
        return row is not None

    async def reinforce_global(self, document_ids: list) -> int:
        """Admin-context reinforce of GLOBAL foundational/market docs (tenant_id
        IS NULL) — closes the ADR-0033 aging loop for SHARED knowledge, which the
        tenant RLS write-policy forbids. The explicit ``tenant_id IS NULL`` guard
        means that even under the admin bypass this can ONLY bump global rows'
        maturity (confidence/use_count) — never any tenant's data. Batch UPDATE;
        returns the number of rows reinforced."""
        ids = list(document_ids or [])
        if not ids:
            return 0
        acquire = self._acquire_admin
        if acquire is None:
            from ...shared.db import acquire_cross_tenant
            acquire = acquire_cross_tenant
        async with acquire() as conn:
            rows = await conn.fetch(
                f"""UPDATE knowledge_documents AS k
                   SET confidence = LEAST(
                           {_ceiling_case_sql('k.tier')},
                           k.confidence + $2 * (
                               ({_ceiling_case_sql('k.tier')}) - k.confidence)),
                       use_count = k.use_count + 1,
                       last_reinforced_at = NOW(),
                       updated_at = NOW()
                   WHERE k.document_id = ANY($1::uuid[])
                     AND k.tenant_id IS NULL
                     AND k.status = 'active'
                   RETURNING k.document_id""",
                ids, _KB_LEARN_RATE,
            )
        return len(rows)

    async def supersede(
        self, scope_tenant_id: Optional[UUID], old_id: UUID,
        new_doc: KnowledgeDocument, *, change_reason: str,
        embedding: Optional[list[float]] = None, model_name: Optional[str] = None,
    ) -> UUID:
        """Replace ``old_id`` with ``new_doc`` while KEEPING history: the new row
        lands active with supersedes=old_id + change_reason; the old row becomes
        status='archived', superseded_by=new. The old version stays queryable so
        the system can explain *why* the knowledge changed ("vì sao lại vậy")."""
        new_doc.supersedes = old_id
        new_doc.status = "active"
        new_doc.change_reason = change_reason
        new_id = await self.put(new_doc, embedding=embedding,
                                model_name=model_name, scope_tenant_id=scope_tenant_id)
        async with self._acquire(scope_tenant_id) as conn:
            await conn.execute(
                """UPDATE knowledge_documents
                   SET status = 'archived', superseded_by = $2, updated_at = NOW()
                   WHERE document_id = $1""",
                old_id, new_id,
            )
        return new_id

    async def version_history(
        self, scope_tenant_id: Optional[UUID], document_id: UUID,
    ) -> list[KnowledgeDocument]:
        """Newest→oldest version chain (follows ``supersedes`` backward). Each row
        carries ``change_reason`` so a caller can render how a fact evolved + why."""
        out: list[KnowledgeDocument] = []
        cur: Optional[UUID] = document_id
        seen: set = set()
        async with self._acquire(scope_tenant_id) as conn:
            while cur is not None and cur not in seen:
                seen.add(cur)
                row = await conn.fetchrow(
                    """SELECT document_id, tenant_id, tier, category, title, content,
                              source, source_url, lang, status, tags, created_at,
                              confidence, use_count, last_reinforced_at, valid_until,
                              supersedes, superseded_by, change_reason
                       FROM knowledge_documents WHERE document_id = $1""",
                    cur,
                )
                if row is None:
                    break
                doc = self._row_to_doc(row)
                out.append(doc)
                cur = doc.supersedes
        return out

    # ─── Helpers ──────────────────────────────────────────────────
    def _row_to_doc(self, row) -> KnowledgeDocument:
        tags = row["tags"]
        if isinstance(tags, str):
            tags = json.loads(tags)
        return KnowledgeDocument(
            document_id=row["document_id"],
            tenant_id=row["tenant_id"],
            tier=row["tier"],
            category=row["category"],
            title=row["title"],
            content=row["content"],
            source=row["source"],
            source_url=row["source_url"],
            lang=row["lang"],
            status=row["status"],
            tags=tags or [],
            distance=float(row["distance"]) if "distance" in row.keys() and row["distance"] is not None else None,
            created_at=row["created_at"],
            # ADR-0033 fields — read defensively so older SELECTs (which don't
            # project them) still map cleanly to dataclass defaults.
            confidence=float(row["confidence"]) if "confidence" in row.keys() else 0.70,
            use_count=row["use_count"] if "use_count" in row.keys() else 0,
            last_reinforced_at=row["last_reinforced_at"] if "last_reinforced_at" in row.keys() else None,
            valid_until=row["valid_until"] if "valid_until" in row.keys() else None,
            supersedes=row["supersedes"] if "supersedes" in row.keys() else None,
            superseded_by=row["superseded_by"] if "superseded_by" in row.keys() else None,
            change_reason=row["change_reason"] if "change_reason" in row.keys() else None,
        )


def _vec_to_pg(v: list[float]) -> str:
    """pgvector accepts the literal '[1,2,3]' string on parameter binding —
    same encoding memory/postgres_l3.py uses."""
    return "[" + ",".join(repr(float(x)) for x in v) + "]"
