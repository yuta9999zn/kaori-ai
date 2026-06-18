"""MemoryService — the public API surface for Stage 7.

Composes 4 TierStores (one per tier) into a single facade. Methods
match the spec at PIPELINE_UNIFIED.md §7.6:
  write / retrieve / consolidate / promote / forget / introspect

Tier-assignment rules (where new records land on write):
  EPISODIC    → L2  (gets consolidated to L3 every 24h)
  SEMANTIC    → L4
  PROCEDURAL  → L4
  OPERATIONAL → L3
  DECISION    → L3  (promoted to L4 once linked to outcome)
  (no automatic L1 — L1 is "current request scope" and lives in the
  caller's Python context, not in any persistent store)

retrieve() walks tiers in this order per §7.4:
  L2 last 10 conversation turns (when session_id set)
  L3 top-K semantic-similar
  L4 top-3 domain knowledge
Stops when top_k results reached.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

import structlog

from .stores import InMemoryTierStore, TierStore, cheap_text_match
from .types import (
    MemoryRecord, MemoryTier, MemoryType, classic_memory_class,
    compute_importance, compute_trust, experience_level,
    reinforce_confidence, trust_factor,
)

log = structlog.get_logger()


# Type → default tier on write.
_DEFAULT_TIER: dict[MemoryType, MemoryTier] = {
    MemoryType.EPISODIC:    MemoryTier.L2_SHORT,
    MemoryType.SEMANTIC:    MemoryTier.L4_LONG,
    MemoryType.PROCEDURAL:  MemoryTier.L4_LONG,
    MemoryType.OPERATIONAL: MemoryTier.L3_CONSOLIDATED,
    MemoryType.DECISION:    MemoryTier.L3_CONSOLIDATED,
}


# Importance promotion threshold per §7.5 + 7.6.
PROMOTION_THRESHOLD = 0.7
# Forget threshold (90d-old records below this score get wiped).
FORGET_THRESHOLD = 0.3
FORGET_AGE_DAYS = 90
# ADR-0036 — memory → tenant-KB promotion maturity gate (const fallback for the
# ai_config knobs `memory_kb_promote_min_trust` / `_min_appearances`).
KB_PROMOTE_MIN_TRUST = 0.8
KB_PROMOTE_MIN_APPEARANCES = 2


class MemoryService:
    """Facade over 4 TierStores."""

    def __init__(
        self, *,
        l1: Optional[TierStore] = None,
        l2: Optional[TierStore] = None,
        l3: Optional[TierStore] = None,
        l4: Optional[TierStore] = None,
    ):
        self.l1 = l1 or InMemoryTierStore(MemoryTier.L1_WORKING)
        self.l2 = l2 or InMemoryTierStore(MemoryTier.L2_SHORT)
        self.l3 = l3 or InMemoryTierStore(MemoryTier.L3_CONSOLIDATED)
        self.l4 = l4 or InMemoryTierStore(MemoryTier.L4_LONG)

    def _tier_store(self, tier: MemoryTier) -> TierStore:
        return {
            MemoryTier.L1_WORKING:  self.l1,
            MemoryTier.L2_SHORT:    self.l2,
            MemoryTier.L3_CONSOLIDATED: self.l3,
            MemoryTier.L4_LONG:     self.l4,
        }[tier]

    # ─── write ─────────────────────────────────────────────────

    async def write(
        self, tenant_id: UUID, memory_type: MemoryType,
        content: str, *,
        session_id: Optional[str] = None,
        entity_id: Optional[UUID] = None,
        metadata: Optional[dict[str, Any]] = None,
        user_flagged_important: bool = False,
        linked_outcome_value: float = 0.0,
        best_effort: bool = True,
    ) -> Optional[MemoryRecord]:
        """Land a new memory at the default tier for its type.

        Gap 2 (chaos-matrix.md 2026-05-20): `best_effort=True` (default)
        means a downed L3 pgvector tier OR exhausted retry returns
        None instead of raising. The workflow that wrote the memory
        continues; the memory is lost (future RAG retrievals just
        won't find it).

        Pass `best_effort=False` for user-driven explicit writes (e.g.
        a "remember this" button) where the caller WANTS to surface
        the failure as a 500 + can retry on user request.
        """
        target_tier = _DEFAULT_TIER[memory_type]
        record = MemoryRecord(
            tenant_id=tenant_id, memory_type=memory_type, content=content,
            tier=target_tier, session_id=session_id, entity_id=entity_id,
            metadata=metadata or {},
            user_flagged_important=user_flagged_important,
            linked_outcome_value=linked_outcome_value,
        )
        try:
            return await self._tier_store(target_tier).put(record)
        except Exception as exc:  # noqa: BLE001
            if not best_effort:
                raise
            # In-memory backends (Phase 1) never fail, so the only path
            # here is Postgres / Redis / Neo4j adapters raising on
            # connection-class errors. Log + skip; the memory is gone
            # but the caller (workflow node, chat agent) keeps going.
            log.warning(
                "memory.write.fail_open",
                tenant_id=str(tenant_id),
                memory_type=memory_type.value,
                target_tier=target_tier.value,
                error_type=type(exc).__name__,
                detail=str(exc)[:200],
            )
            return None

    # ─── retrieve ──────────────────────────────────────────────

    async def retrieve(
        self, tenant_id: UUID, query: str, *,
        top_k: int = 5, tier: str = "auto",
        session_id: Optional[str] = None,
        entity_id: Optional[UUID] = None,
        entity_boost: float = 2.0,
        expand_links: bool = True,
        expand_limit: Optional[int] = None,
        min_score: float = 0.0,
    ) -> list[MemoryRecord]:
        """RAG-style retrieval across tiers per §7.4.

        tier='auto' walks L2 → L3 → L4 in spec order; an explicit tier
        name (e.g. 'L3_CONSOLIDATED') restricts the scan.

        Mem0-inspired (ship 2026-05-17):
        - `entity_id`: when set, records whose ``entity_id`` matches get
          their text-match score multiplied by ``entity_boost`` (default
          2.0). Records WITHOUT entity_id still surface but ranked lower.
          This is "entity-aware retrieval" — caller resolves entity from
          the query via Stage 5 Ontology (Neo4j) and passes the UUID in.
        """
        # 1. Resolve tier list
        if tier == "auto":
            tiers_to_walk = [MemoryTier.L2_SHORT, MemoryTier.L3_CONSOLIDATED, MemoryTier.L4_LONG]
        else:
            try:
                tiers_to_walk = [MemoryTier(tier)]
            except ValueError as e:
                raise ValueError(
                    f"tier must be 'auto' or one of {[t.value for t in MemoryTier]}; "
                    f"got {tier!r}"
                ) from e

        # 2. Score every candidate across the walked tiers; also index ALL
        #    records by id so associative expansion can pull linked neighbours
        #    that share no query words (the point of associative recall).
        now = datetime.now(timezone.utc)
        scored: list[tuple[float, MemoryRecord]] = []
        all_by_id: dict[str, MemoryRecord] = {}
        for t in tiers_to_walk:
            for r in await self._tier_store(t).list_all(tenant_id):
                # Session filter: L2 conversation turns are session-scoped
                if t == MemoryTier.L2_SHORT and session_id and r.session_id != session_id:
                    continue
                all_by_id[str(r.record_id)] = r
                score = cheap_text_match(query, r.content)
                # `min_score` is a RAW relevance floor (applied before trust
                # down-ranking) so a weak lexical overlap — e.g. shared
                # stopwords between an off-domain query and a memory — does not
                # surface and inflate the agent |OR| gate's memory mass
                # (audit 2026-06-02). Default 0.0 keeps the legacy score>0.
                if score > 0 and score >= min_score:
                    # Entity-aware boost — records matching the entity get
                    # bumped so they rank above generic matches.
                    if entity_id is not None and r.entity_id == entity_id:
                        score *= entity_boost
                    # ADR-0030 trust: down-rank stale/low-trust memories (factor
                    # in [0.4, 1]) so a confident-but-unchecked old fact sinks
                    # below fresher matches, but a strong hit is never silenced.
                    score *= trust_factor(r, now=now)
                    scored.append((score, r))

        # 3. Top-K
        scored.sort(key=lambda x: x[0], reverse=True)
        results = [r for _s, r in scored[:top_k]]

        # 3b. Reinforce the retrieval signal: bump appearance count on the
        #     records that actually surfaced AND persist it. The bump feeds the
        #     §7.5 importance "repeat" term; without the put() it would be lost on
        #     DB-backed stores (list_all returns fresh objects each call, so an
        #     in-memory-only bump never reaches the row). Bounded to ≤ top_k
        #     writes; best-effort so a failed write never breaks the read path.
        for r in results:
            r.session_appearance_count += 1
            try:
                await self._tier_store(r.tier).put(r)
            except Exception as exc:  # noqa: BLE001
                log.warning(
                    "memory.retrieve.bump_persist_fail",
                    tenant_id=str(tenant_id), record_id=str(r.record_id),
                    error_type=type(exc).__name__,
                )

        # 4. Associative recall (ADR-0032): follow each hit's links one hop to
        #    pull in connected neighbours, even if they didn't match the query.
        #    Edges live in metadata["links"] (a list of record-id strings),
        #    written at consolidation; tagged via= so the caller sees the path.
        #    Bounded to `expand_limit` neighbours (default top_k) so a densely
        #    linked hit can't balloon the result set unboundedly.
        if expand_links:
            remaining = top_k if expand_limit is None else expand_limit
            seen = {str(r.record_id) for r in results}
            for r in list(results):
                if remaining <= 0:
                    break
                for link_id in (r.metadata or {}).get("links", []):
                    if remaining <= 0:
                        break
                    nb = all_by_id.get(str(link_id))
                    if nb is not None and str(nb.record_id) not in seen:
                        # Tag the path on a COPY — the `_via` marker is transient
                        # routing info; mutating nb would persist it onto the
                        # stored record (in-memory backend shares the object).
                        tagged = replace(
                            nb, metadata={**(nb.metadata or {}), "_via": str(r.record_id)})
                        results.append(tagged)
                        seen.add(str(nb.record_id))
                        remaining -= 1
        return results

    # ─── verify (ADR-0030 trust reset) ─────────────────────────

    async def verify(self, tenant_id: UUID, record_id: UUID) -> bool:
        """Re-confirm a memory is still valid today → stamp last_verified_at,
        resetting its trust decay (ADR-0030). Searches all tiers; returns True
        when a record was found and re-stamped. Caller logs K-6 audit.

        Also the target of reinforce-on-use: when a retrieved memory
        demonstrably helped a good answer, the caller calls verify() so used
        memories stay fresh and idle ones age out of trust.
        """
        now = datetime.now(timezone.utc)
        for store in (self.l1, self.l2, self.l3, self.l4):
            r = await store.get(tenant_id, record_id)
            if r is not None:
                r.last_verified_at = now
                await store.put(r)
                return True
        return False

    async def reinforce(self, tenant_id: UUID, record_id: UUID) -> bool:
        """Reinforce-on-use (ADR-0032 maturation): a memory that demonstrably
        helped a good answer is both re-verified (decay reset) AND nudged up the
        confidence learning-curve toward its ceiling. Used memories grow more
        trusted over time; idle ones decay — "càng dùng càng chắc". Returns True
        if found."""
        now = datetime.now(timezone.utc)
        for store in (self.l1, self.l2, self.l3, self.l4):
            r = await store.get(tenant_id, record_id)
            if r is not None:
                r.last_verified_at = now
                reinforce_confidence(r)
                await store.put(r)
                return True
        return False

    async def link(self, tenant_id: UUID, a_id: UUID, b_id: UUID, *, mutual: bool = True) -> bool:
        """Create an associative edge a→b (and b→a if mutual) between two
        memories, stored in metadata["links"] (ADR-0032). retrieve(expand_links)
        follows these one hop. Returns True if at least one endpoint was found."""
        found = False
        pairs = [(a_id, b_id), (b_id, a_id)] if mutual else [(a_id, b_id)]
        for src, dst in pairs:
            for store in (self.l1, self.l2, self.l3, self.l4):
                r = await store.get(tenant_id, src)
                if r is not None:
                    links = list((r.metadata or {}).get("links", []))
                    if str(dst) not in links:
                        links.append(str(dst))
                    r.metadata = {**(r.metadata or {}), "links": links}
                    await store.put(r)
                    found = True
                    break
        return found

    async def experience(self, tenant_id: UUID, *, now: Optional[datetime] = None) -> dict:
        """Tenant maturation level (ADR-0032) over long-term (L3+L4) memory:
        how much MAINTAINED, trusted knowledge has accumulated — "càng nhiều
        tháng càng biết nhiều". Returns experience 0-1 + band + tenure_days."""
        records = await self.l4.list_all(tenant_id)
        records += await self.l3.list_all(tenant_id)
        return experience_level(records, now=now)

    # ─── consolidate (L2 → L3) ─────────────────────────────────

    async def consolidate(self, tenant_id: UUID) -> int:
        """Daily cron entrypoint — drain L2 episodic records into L3.

        Per §7.3 the spec calls for a "summarization step (Qwen 14B →
        200-token summary)" before L3 land. Phase 1.5 ships the move
        without summarisation; summarisation lands as a follow-up
        wrapper once we want to compress L2 noise.
        """
        moved = 0
        records = await self.l2.list_all(tenant_id)
        for r in records:
            await self.l2.delete(tenant_id, r.record_id)
            r.tier = MemoryTier.L3_CONSOLIDATED
            await self.l3.put(r)
            moved += 1
        return moved

    # ─── promote (L3 → L4) ─────────────────────────────────────

    async def promote(
        self, tenant_id: UUID, *,
        importance_threshold: Optional[float] = None,
        now: Optional[datetime] = None,
    ) -> int:
        """Score L3 records; move score > threshold to L4. Per §7.5.

        CR-0019 — when the caller doesn't pin a threshold it falls back to the
        platform `memory_promotion_threshold` knob (then the const default)."""
        if importance_threshold is None:
            from ai_orchestrator.shared import ai_config  # noqa: E402
            importance_threshold = await ai_config.get_float(
                "memory_promotion_threshold", PROMOTION_THRESHOLD)
        if now is None:
            now = datetime.now(timezone.utc)
        moved = 0
        for r in await self.l3.list_all(tenant_id):
            if compute_importance(r, now=now) > importance_threshold:
                await self.l3.delete(tenant_id, r.record_id)
                r.tier = MemoryTier.L4_LONG
                await self.l4.put(r)
                moved += 1
        return moved

    # ─── promote memory → tenant KB (ADR-0032/0033 loop) ──────
    async def promote_to_knowledge(
        self, tenant_id: UUID, *, knowledge_store,
        min_trust: Optional[float] = None, min_appearances: Optional[int] = None,
        now: Optional[datetime] = None,
    ) -> int:
        """Close the "kho tự nâng cấp" loop: a MATURE, validated procedural/
        semantic memory becomes part of the tenant's OWN foundational KB
        (tier 4) so it feeds the coverage gate ("học 1 hiểu 10").

        Tenant-scoped only (K-1) — promotion goes to the tenant's tier-4
        knowledge, NOT global curated (that elevation is a human-gated curation
        step). Idempotent: a deterministic doc id (uuid5 of the memory) makes
        re-promotion upsert the same KB row, and the memory is flagged so it is
        promoted once. LLM-free + cheap — safe to run in the consolidate cron.

        ADR-0036 follow-up — when the caller doesn't pin the gates they fall
        back to the platform `memory_kb_promote_min_trust` /
        `memory_kb_promote_min_appearances` knobs (then the const defaults), so
        the maturity bar is tunable per deployment without a redeploy.
        """
        from uuid import NAMESPACE_URL, uuid5
        from ..knowledge.store import KnowledgeDocument  # local: avoid coupling

        if min_trust is None or min_appearances is None:
            from ai_orchestrator.shared import ai_config  # noqa: E402
            if min_trust is None:
                min_trust = await ai_config.get_float(
                    "memory_kb_promote_min_trust", KB_PROMOTE_MIN_TRUST)
            if min_appearances is None:
                min_appearances = await ai_config.get_int(
                    "memory_kb_promote_min_appearances", KB_PROMOTE_MIN_APPEARANCES)
        if now is None:
            now = datetime.now(timezone.utc)
        promotable = {MemoryType.PROCEDURAL, MemoryType.SEMANTIC, MemoryType.OPERATIONAL}
        promoted = 0
        for store in (self.l4, self.l3):
            for r in await store.list_all(tenant_id):
                if r.memory_type not in promotable:
                    continue
                if r.metadata.get("promoted_to_kb"):
                    continue
                if r.session_appearance_count < min_appearances:
                    continue
                if compute_trust(r, now=now)["score"] < min_trust:
                    continue
                title = (r.metadata.get("name") or r.content)[:120]
                doc = KnowledgeDocument(
                    title=title, content=r.content, tier=4, tenant_id=tenant_id,
                    category=classic_memory_class(r.memory_type),
                    source="memory_promotion", confidence=r.confidence,
                    document_id=uuid5(NAMESPACE_URL, f"kaori-mem:{r.record_id}"),
                )
                try:
                    await knowledge_store.put(doc, scope_tenant_id=tenant_id)
                except Exception as exc:  # noqa: BLE001 — best-effort, never abort cron
                    log.warning("memory.promote_to_kb.fail", tenant_id=str(tenant_id),
                                record_id=str(r.record_id), error=str(exc)[:160])
                    continue
                r.metadata["promoted_to_kb"] = True
                await store.put(r)   # persist the flag
                promoted += 1
        return promoted

    async def seed_procedural_from_kb(
        self, tenant_id: UUID, *, knowledge_store, limit: int = 10,
    ) -> int:
        """Bootstrap the PROCEDURAL room ("phương-pháp") from the curated
        foundational KB (ADR-0032 bridge). For each top foundational principle
        (tier 1-2) we write a thin recipe memory that POINTS at the KB doc — it
        does NOT copy the principle body (no duplication, per ADR-0033). The
        recipe is a navigable handle that consolidation/recall can link from.
        Idempotent via a deterministic record id."""
        from uuid import NAMESPACE_URL, uuid5

        docs = await knowledge_store.list_documents(tenant_id, limit=100)
        foundational = [d for d in docs if (d.tier or 9) <= 2][:limit]
        seeded = 0
        for d in foundational:
            rec = MemoryRecord(
                tenant_id=tenant_id, memory_type=MemoryType.PROCEDURAL,
                content=f"Áp dụng nguyên tắc nền: «{d.title}» (KB#{str(d.document_id)[:8]}).",
                tier=MemoryTier.L4_LONG, trust_source="seed", confidence=0.75,
                metadata={"name": f"recipe:{d.title}", "from_kb": str(d.document_id)},
            )
            rec.record_id = uuid5(NAMESPACE_URL, f"kaori-recipe:{tenant_id}:{d.document_id}")
            await self.l4.put(rec)
            seeded += 1
        return seeded

    # ─── forget (TTL + GDPR) ───────────────────────────────────

    async def forget(
        self, tenant_id: UUID, *,
        full_tenant_wipe: bool = False,
        below_score: Optional[float] = None,
        age_days: Optional[int] = None,
        now: Optional[datetime] = None,
    ) -> int:
        """Two modes:

        full_tenant_wipe=True — GDPR right-to-erasure; remove every
        memory across all 4 tiers for this tenant.

        full_tenant_wipe=False (default) — TTL sweep; remove L3 records
        older than `age_days` AND below `below_score`.
        """
        if full_tenant_wipe:
            total = 0
            for t in (self.l1, self.l2, self.l3, self.l4):
                total += await t.forget(tenant_id)
            return total

        # CR-0019 — TTL-sweep knobs default to the platform config (then const).
        if below_score is None or age_days is None:
            from ai_orchestrator.shared import ai_config  # noqa: E402
            if below_score is None:
                below_score = await ai_config.get_float("memory_forget_threshold", FORGET_THRESHOLD)
            if age_days is None:
                age_days = await ai_config.get_int("memory_forget_age_days", FORGET_AGE_DAYS)

        if now is None:
            now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=age_days)
        wiped = 0
        for r in await self.l3.list_all(tenant_id):
            if r.occurred_at < cutoff and compute_importance(r, now=now) < below_score:
                await self.l3.delete(tenant_id, r.record_id)
                wiped += 1
        return wiped

    # ─── introspect (audit) ────────────────────────────────────

    async def introspect(self, tenant_id: UUID, entity_id: UUID) -> list[MemoryRecord]:
        """Return every memory linked to `entity_id` across all tiers.
        Used by the admin audit UI per §7.6."""
        out: list[MemoryRecord] = []
        for t in (self.l1, self.l2, self.l3, self.l4):
            for r in await t.list_all(tenant_id):
                if r.entity_id == entity_id:
                    out.append(r)
        return out
