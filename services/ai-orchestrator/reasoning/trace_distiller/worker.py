"""
P2-S21 D4 — TraceDistillerWorker.

Background batch job that polls `decision_audit_log` for un-distilled
rows (per `distilled_decisions` cache, mig 070), runs T-Cube distillation
on each, and writes 3 forms into Memory L4 PROCEDURAL.

Design — cron-friendly + Temporal-friendly
-------------------------------------------
The worker exposes a single async entrypoint `run_once()` that processes
ONE batch. Callers wire it however suits Phase:

  - Phase 1.5: simple async cron (asyncio.create_task in startup or
    a cronjob calling the helper script).
  - Phase 2+: Temporal scheduled workflow with retry policy. The
    side_effect_class is `write_idempotent` per K-17 because:
      (a) we never re-distill an already-distilled decision_id
      (b) MemoryService.write is idempotent under same (tenant, content,
          metadata.source_decision_id) tuple.

Key invariants
--------------
- K-1 / K-12: tenant_id from decision row, never from caller args.
- K-5: PII redaction (Vietnamese-aware via reasoning.rag.engines.docsage.
  extraction.redact_pii) applied BEFORE distillation. Reasoning column
  often contains customer emails / phones.
- K-6: distilled_decisions row is the audit trail of "did we distill X".
- K-13: idempotency_key behaviour comes from the PK constraint on
  decision_id — ON CONFLICT DO NOTHING makes re-runs safe.
- K-17: side_effect_class = write_idempotent (see above rationale).
- K-20: distiller_model + distiller_version persisted so model upgrades
  can re-process the cache.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
from uuid import UUID

import structlog

from ..memory.service import MemoryService
from ..rag.engines.docsage.extraction import redact_pii
from .transformer import TCubeTransformer, ThinkingTrace

log = structlog.get_logger()


# Tuneable defaults — caller can override per-run.
DEFAULT_BATCH_SIZE          = 20
DEFAULT_CONFIDENCE_THRESHOLD = 0.6     # below this, distillation isn't worth the LLM cost
DEFAULT_MAX_RETRIES         = 3        # after 3 distill failures, leave the row alone


@dataclass
class WorkerStats:
    """Per-run telemetry — returned by run_once() so the caller (cron
    log, Temporal activity result, test assertions) can verify behaviour."""
    candidates_scanned: int  = 0
    distilled_ok:       int  = 0
    distilled_failed:   int  = 0
    skipped_low_conf:   int  = 0
    skipped_max_retry:  int  = 0


class TraceDistillerWorker:
    """Idempotent batch distiller for decision_audit_log → Memory L4 PROCEDURAL.

    Construction injects:
      - `db` — asyncpg connection or pool (must support `fetch`, `execute`)
      - `transformer` — TCubeTransformer (LLM-backed)
      - `memory_service` — MemoryService facade

    The DB shape contract is minimal: we use `fetch` for SELECT and
    `execute` for INSERT. Tests pass an AsyncMock with these two methods.
    """

    def __init__(
        self,
        *,
        db: Any,
        transformer: TCubeTransformer,
        memory_service: MemoryService,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ):
        self._db          = db
        self._transformer = transformer
        self._memory      = memory_service
        self._threshold   = confidence_threshold
        self._max_retries = max_retries

    async def run_once(
        self,
        *,
        batch_size: int = DEFAULT_BATCH_SIZE,
        enterprise_id: Optional[UUID] = None,
    ) -> WorkerStats:
        """Process one batch of un-distilled decisions.

        If `enterprise_id` is None, scans all tenants (admin job). When
        called per-tenant (cron-per-tenant pattern Phase 2), pass the
        filter to scope the query.
        """
        stats = WorkerStats()
        rows = await self._fetch_candidates(batch_size, enterprise_id)
        stats.candidates_scanned = len(rows)

        for row in rows:
            confidence = float(row["confidence"]) if row["confidence"] is not None else 0.0
            if confidence < self._threshold:
                stats.skipped_low_conf += 1
                continue

            prior = await self._get_retry_count(row["decision_id"])
            if prior >= self._max_retries:
                stats.skipped_max_retry += 1
                continue

            trace = self._row_to_trace(row)
            try:
                await self._transformer.transform_and_store(trace, self._memory)
                await self._mark_success(trace)
                stats.distilled_ok += 1
            except Exception as exc:  # noqa: BLE001 — wide catch is intentional
                err = f"{type(exc).__name__}: {exc}"[:1000]
                await self._mark_failure(trace, err, prior_retry=prior)
                stats.distilled_failed += 1
                log.warning("trace_distiller.failed",
                            decision_id=str(trace.source_decision_id),
                            tenant_id=str(trace.tenant_id),
                            retry_count=prior + 1,
                            error=err)

        log.info("trace_distiller.batch_complete",
                 candidates=stats.candidates_scanned,
                 ok=stats.distilled_ok,
                 failed=stats.distilled_failed,
                 skipped_conf=stats.skipped_low_conf,
                 skipped_retry=stats.skipped_max_retry)
        return stats

    # ─── DB layer (small, easy to mock) ─────────────────────────────

    async def _fetch_candidates(
        self,
        batch_size: int,
        enterprise_id: Optional[UUID],
    ) -> list:
        """SELECT decision_audit_log rows not yet successfully distilled.

        A row is a candidate if:
          - No matching `distilled_decisions` row, OR
          - distilled_decisions row exists with error_message NOT NULL
            (retry path)
        """
        # LEFT JOIN keeps decisions without cache row; WHERE filters out
        # successfully-distilled (cache row with error_message IS NULL).
        sql = """
        SELECT
            d.decision_id, d.enterprise_id, d.decision_type, d.subject,
            d.confidence, d.method, d.alternatives, d.llm_provider,
            d.reasoning, d.created_at
        FROM decision_audit_log d
        LEFT JOIN distilled_decisions c ON c.decision_id = d.decision_id
        WHERE d.reasoning IS NOT NULL
          AND (c.decision_id IS NULL OR c.error_message IS NOT NULL)
        """
        params: list[Any] = []
        if enterprise_id is not None:
            params.append(enterprise_id)
            sql += f" AND d.enterprise_id = ${len(params)}"
        params.append(batch_size)
        sql += f" ORDER BY d.created_at ASC LIMIT ${len(params)}"
        return list(await self._db.fetch(sql, *params))

    async def _get_retry_count(self, decision_id: UUID) -> int:
        row = await self._db.fetchrow(
            "SELECT retry_count FROM distilled_decisions WHERE decision_id = $1",
            decision_id,
        )
        return int(row["retry_count"]) if row else 0

    async def _mark_success(self, trace: ThinkingTrace) -> None:
        """Insert (or update from a failure state to success)."""
        await self._db.execute(
            """
            INSERT INTO distilled_decisions
                (decision_id, enterprise_id, distiller_model, distiller_version,
                 forms_stored, error_message)
            VALUES ($1, $2, $3, $4, 3, NULL)
            ON CONFLICT (decision_id) DO UPDATE SET
                distilled_at      = NOW(),
                distiller_model   = EXCLUDED.distiller_model,
                distiller_version = EXCLUDED.distiller_version,
                forms_stored      = 3,
                error_message     = NULL
            """,
            trace.source_decision_id,
            trace.tenant_id,
            self._transformer._model,          # noqa: SLF001 (accessing pinned model)
            getattr(self._transformer, "_version", None),
        )

    async def _mark_failure(
        self,
        trace: ThinkingTrace,
        error: str,
        *,
        prior_retry: int,
    ) -> None:
        await self._db.execute(
            """
            INSERT INTO distilled_decisions
                (decision_id, enterprise_id, distiller_model, distiller_version,
                 forms_stored, error_message, retry_count)
            VALUES ($1, $2, $3, $4, 0, $5, $6)
            ON CONFLICT (decision_id) DO UPDATE SET
                error_message = EXCLUDED.error_message,
                retry_count   = distilled_decisions.retry_count + 1,
                distilled_at  = NOW()
            """,
            trace.source_decision_id,
            trace.tenant_id,
            self._transformer._model,          # noqa: SLF001
            getattr(self._transformer, "_version", None),
            error,
            prior_retry + 1,
        )

    # ─── Trace shaping (PII mask + context build) ───────────────────

    @staticmethod
    def _row_to_trace(row) -> ThinkingTrace:
        """Build a ThinkingTrace from a decision_audit_log row.

        K-5: applies redact_pii to reasoning + subject BEFORE returning.
        The `alternatives` column is folded into problem_context for
        better retrieval matching ("what other paths did we consider?"
        is a useful signal for trace_recall similarity).
        """
        raw_text = redact_pii(row["reasoning"] or "")
        subject = redact_pii(row["subject"] or "")

        alternatives_str = ""
        alts = row["alternatives"]
        if alts:
            # alts is JSONB — may already be dict/list, may be str
            if isinstance(alts, str):
                import json
                try:
                    alts = json.loads(alts)
                except json.JSONDecodeError:
                    alts = None
            if isinstance(alts, (list, dict)):
                alternatives_str = str(alts)[:400]

        problem_context = (
            f"{row['decision_type']}: {subject}"
            + (f" | alternatives: {alternatives_str}" if alternatives_str else "")
        )

        return ThinkingTrace(
            source_decision_id=row["decision_id"],
            tenant_id=row["enterprise_id"],
            raw_text=raw_text,
            problem_context=problem_context,
            source_llm_provider=row["llm_provider"],
            source_llm_version=None,  # not in decision_audit_log v1 schema
            occurred_at=row["created_at"],
        )
