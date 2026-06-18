-- =====================================================================
-- 070_distilled_decisions_cache.sql
--
-- P2-S21 D4 — cache table tracking which decision_audit_log rows have
-- been distilled by TraceDistillerWorker (T-Cube → Memory L4 PROCEDURAL).
--
-- Design choices
-- --------------
-- - PRIMARY KEY = decision_id ensures idempotent re-runs: re-distilling
--   the same row is a NO-OP (INSERT … ON CONFLICT DO NOTHING).
-- - enterprise_id duplicated (FK denormalized) so RLS filter is cheap;
--   tenant scoping matches the parent decision_audit_log.
-- - error_message NULLABLE: if all 3 forms distill OK, error stays NULL.
--   If LLM gateway 503 etc., row inserted with error_message set so
--   retry batching can skip recent-failures via a freshness window.
-- - distiller_model + distiller_version recorded so re-distill on model
--   upgrade (K-20 pin change) becomes queryable: rows with old version
--   can be re-processed.
--
-- K-rules
-- -------
-- K-1: RLS-style filter via enterprise_id; explicit policy on parent
--      table already covers cross-tenant leak.
-- K-2: Cache is append-mostly; UPDATE only for error→success transition
--      on retry. No DELETE except via 90-day forget cron (matches
--      MemoryService FORGET_AGE_DAYS).
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS distilled_decisions (
    decision_id         UUID         PRIMARY KEY
                                     REFERENCES decision_audit_log(decision_id),
    enterprise_id       UUID         NOT NULL
                                     REFERENCES enterprises(enterprise_id),
    distilled_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    distiller_model     VARCHAR(64),
    distiller_version   VARCHAR(64),
    forms_stored        INTEGER      NOT NULL DEFAULT 0,
    error_message       TEXT,
    retry_count         INTEGER      NOT NULL DEFAULT 0,

    CONSTRAINT chk_distilled_forms_range CHECK (forms_stored BETWEEN 0 AND 3),
    CONSTRAINT chk_distilled_retry_nonneg CHECK (retry_count >= 0)
);

-- Worker-side query pattern: find next batch of un-distilled decisions
-- per tenant where confidence >= threshold. Partial index excludes
-- successfully distilled rows so the worker doesn't re-scan them.
CREATE INDEX IF NOT EXISTS idx_distilled_decisions_pending_retry
    ON distilled_decisions(enterprise_id, distilled_at)
    WHERE error_message IS NOT NULL;

COMMENT ON TABLE distilled_decisions IS
    'P2-S21 D4 — cache marking which decision_audit_log rows have been '
    'T-Cube distilled into Memory L4 PROCEDURAL. Idempotent re-run safe.';

COMMENT ON COLUMN distilled_decisions.forms_stored IS
    '3 = struct + semantic + reflect all landed. <3 = partial failure '
    '(error_message populated). Worker retries when retry_count < cap.';

COMMENT ON COLUMN distilled_decisions.error_message IS
    'NULL on success. Set to LLM error string when distillation fails. '
    'Worker uses presence to filter retry batches via partial index.';

COMMIT;
