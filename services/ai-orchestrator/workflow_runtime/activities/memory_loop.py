"""
Temporal activities for Stage 7 Memory + Stage 12 Loop scheduling.

Five activities + the workflows that compose them land per-tenant
periodic operations:

  memory_consolidate_for_tenant  — L2 → L3 drain (daily)
  memory_promote_for_tenant      — L3 → L4 score-based promotion (daily)
  memory_forget_sweep_for_tenant — L3 TTL sweep (weekly)
  memory_embed_pending_for_tenant — bg embedding fill (every 1 min)
  loop_evaluate_for_tenant       — Stage 12 A/B evaluation (daily)

Each activity declares its `side_effect_class` per K-17 so the
workflow can pick the right retry policy (read_only / write_idempotent
/ external).

The activities take per-tenant arguments and call back into the
production stores. Temporal cluster owns scheduling (cron) — this
module just defines the units.

Gated by TEMPORAL_ENABLE_WORKER (default false). When the env flag
is off, the worker doesn't register these activities, so a misfire
from a manual schedule create won't run them.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import structlog
from temporalio import activity

log = structlog.get_logger()


# ─── Per-activity side_effect_class declarations (K-17) ─────────────


# Each activity's class informs the workflow's retry policy choice.
SIDE_EFFECT_CLASS = {
    "memory_consolidate_for_tenant":   "write_idempotent",
    "memory_promote_for_tenant":       "write_idempotent",
    "memory_promote_kb_for_tenant":    "write_idempotent",  # idempotent uuid5 upsert
    "memory_forget_sweep_for_tenant":  "write_idempotent",
    "memory_embed_pending_for_tenant": "external",        # llm-gateway call
    "loop_evaluate_for_tenant":        "read_only",       # SELECTs only; writes the decision row separately
}


# ─── Activity payloads ──────────────────────────────────────────────


@dataclass
class TenantTask:
    """All five activities take just a tenant_id string."""
    tenant_id: str


@dataclass
class TenantBatchResult:
    """Uniform return: count of rows touched."""
    tenant_id: str
    activity:  str
    count:     int


# ─── Activities ─────────────────────────────────────────────────────


@activity.defn(name="memory_consolidate_for_tenant")
async def memory_consolidate_for_tenant(task: TenantTask) -> TenantBatchResult:
    """L2 → L3 drain. Returns count of records moved."""
    from uuid import UUID
    from ...reasoning.memory import MemoryService

    svc = _build_memory_service()
    moved = await svc.consolidate(UUID(task.tenant_id))
    log.info("memory.consolidate.activity_done",
             tenant_id=task.tenant_id, moved=moved)
    return TenantBatchResult(
        tenant_id=task.tenant_id,
        activity="memory_consolidate_for_tenant",
        count=moved,
    )


@activity.defn(name="memory_promote_for_tenant")
async def memory_promote_for_tenant(task: TenantTask) -> TenantBatchResult:
    """L3 → L4 promotion for records with score > 0.7."""
    from uuid import UUID

    svc = _build_memory_service()
    promoted = await svc.promote(UUID(task.tenant_id))
    log.info("memory.promote.activity_done",
             tenant_id=task.tenant_id, promoted=promoted)
    return TenantBatchResult(
        tenant_id=task.tenant_id,
        activity="memory_promote_for_tenant",
        count=promoted,
    )


@activity.defn(name="memory_promote_kb_for_tenant")
async def memory_promote_kb_for_tenant(task: TenantTask) -> TenantBatchResult:
    """ADR-0036 — close the "kho tự nâng cấp" loop: lift MATURE, validated
    procedural/semantic memory into the tenant's OWN tier-4 KB so it feeds the
    coverage gate ("học 1 hiểu 10"). Idempotent (uuid5 upsert + flag), LLM-free.
    Runs AFTER promote so only L3→L4-promoted, durable memory is considered."""
    from uuid import UUID

    svc = _build_memory_service()
    kb = _build_knowledge_store()
    promoted = await svc.promote_to_knowledge(UUID(task.tenant_id), knowledge_store=kb)
    log.info("memory.promote_kb.activity_done",
             tenant_id=task.tenant_id, promoted=promoted)
    return TenantBatchResult(
        tenant_id=task.tenant_id,
        activity="memory_promote_kb_for_tenant",
        count=promoted,
    )


@activity.defn(name="memory_forget_sweep_for_tenant")
async def memory_forget_sweep_for_tenant(task: TenantTask) -> TenantBatchResult:
    """L3 TTL sweep — wipe old + low-importance records (age ≥ 90d AND
    score < 0.3 per spec §7.5)."""
    from uuid import UUID

    svc = _build_memory_service()
    wiped = await svc.forget(UUID(task.tenant_id))
    log.info("memory.forget.activity_done",
             tenant_id=task.tenant_id, wiped=wiped)
    return TenantBatchResult(
        tenant_id=task.tenant_id,
        activity="memory_forget_sweep_for_tenant",
        count=wiped,
    )


@activity.defn(name="memory_embed_pending_for_tenant")
async def memory_embed_pending_for_tenant(task: TenantTask) -> TenantBatchResult:
    """Bg embedding fill — call llm-gateway /v1/embed for unembedded
    rows in the L3 Postgres tier."""
    from uuid import UUID
    from ...reasoning.memory.embedding_worker import embed_pending_for_tenant
    from ...reasoning.memory.postgres_l3 import PostgresTierStore
    from ...shared.db import acquire_for_tenant

    store = PostgresTierStore(acquire_for_tenant=acquire_for_tenant)
    embedded = await embed_pending_for_tenant(store, UUID(task.tenant_id))
    log.info("memory.embed.activity_done",
             tenant_id=task.tenant_id, embedded=embedded)
    return TenantBatchResult(
        tenant_id=task.tenant_id,
        activity="memory_embed_pending_for_tenant",
        count=embedded,
    )


@dataclass
class LoopEvaluateTask:
    tenant_id:     str
    experiment_id: str
    metric_name:   str


@dataclass
class LoopEvaluateResult:
    tenant_id:     str
    experiment_id: str
    metric_name:   str
    conclusion:    str
    action:        str
    decision_id:   str


@activity.defn(name="loop_evaluate_for_tenant")
async def loop_evaluate_for_tenant(task: LoopEvaluateTask) -> LoopEvaluateResult:
    """Stage 12 — evaluate one (tenant, experiment, metric) tuple.

    The BaselineTracker is process-wide; in real prod it's swapped for
    a Postgres-backed tracker (Phase 2+ follow-up table). For now the
    activity composes the existing in-memory tracker as a starting
    point — caller injects via _build_baseline_tracker.
    """
    from uuid import UUID
    from ...org_intel.loop import (
        ABTestFramework,
        PromotionEngine,
    )

    tracker = _build_baseline_tracker()
    framework = ABTestFramework(tracker)
    result = framework.evaluate(
        tenant_id=UUID(task.tenant_id),
        experiment_id=task.experiment_id,
        metric_name=task.metric_name,
    )
    decision = PromotionEngine().decide(result)
    log.info("loop.evaluate.activity_done",
             tenant_id=task.tenant_id,
             experiment_id=task.experiment_id,
             conclusion=result.conclusion,
             action=decision.action.value)
    return LoopEvaluateResult(
        tenant_id=task.tenant_id,
        experiment_id=task.experiment_id,
        metric_name=task.metric_name,
        conclusion=result.conclusion,
        action=decision.action.value,
        decision_id=str(decision.decision_id),
    )


# ─── Composition helpers (overridable for tests) ────────────────────


def _build_memory_service():
    """Default production MemoryService — caller may monkeypatch in
    tests to inject mocked tier stores.

    Today returns the all-in-memory service (Phase 1.5 backend). Phase
    2.5 swaps L2 to RedisTierStore + L3 to PostgresTierStore + L4 to
    Neo4jOntologyStore-bridge once we wire the construction at startup.
    """
    from ...reasoning.memory import MemoryService
    return MemoryService()


def _build_knowledge_store():
    """Default production KnowledgeStore (Postgres + pgvector) — caller may
    monkeypatch in tests. RLS-scoped writes via acquire_for_tenant (K-1)."""
    from ...reasoning.knowledge.store import KnowledgeStore
    from ...shared.db import acquire_for_tenant
    return KnowledgeStore(acquire_for_tenant=acquire_for_tenant)


def _build_baseline_tracker():
    """Default production BaselineTracker — caller may monkeypatch in
    tests. Phase 2.5 swaps for a Postgres-backed tracker that reads
    from a baseline_observations table."""
    from ...org_intel.loop import BaselineTracker
    return BaselineTracker()
