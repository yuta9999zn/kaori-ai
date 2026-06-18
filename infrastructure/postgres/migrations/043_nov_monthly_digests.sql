-- 043_nov_monthly_digests.sql — NOV-CORE-013/015 persistence.
--
-- Phase 1.5 P15-S9 D7 — monthly NOV digests, one row per (enterprise,
-- month). The NOV monthly workflow (workflow_runtime/workflows/
-- nov_monthly_digest.py) writes here on the 1st of each month (per
-- tenant timezone); the dashboard endpoint reads back the current row +
-- the 6-month trend.
--
-- Why a separate digest table (instead of recomputing on read)
-- ============================================================
--   * NOV inputs (revenue, cost) decay if upstream rows mutate (cost
--     correction, late revenue attribution). Snapshot at month-close
--     locks in the value the manager will see; recomputing on the 5th
--     of next month should yield the same number as on the 1st.
--   * Trend queries become a single index scan (per-tenant, ORDER BY
--     month_start DESC LIMIT 6) instead of joining 4 source tables for
--     6 months.
--   * Audit — a manager arguing the number can ask "show me the digest
--     row that was written on date X" and get a deterministic answer.

CREATE TABLE IF NOT EXISTS nov_monthly_digests (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id            UUID NOT NULL,

    -- Month identity (first day of the month, UTC) — naming matches
    -- enterprise_monthly_billing convention so SREs reading both tables
    -- side-by-side don't context-switch on column names.
    month_start              DATE NOT NULL,

    -- NUMERIC(14,4) per K-9 — money is never FLOAT.
    revenue_vnd              NUMERIC(14,4) NOT NULL,
    cost_vnd                 NUMERIC(14,4) NOT NULL,
    nov_vnd                  NUMERIC(14,4) NOT NULL,

    -- Provenance — which method produced revenue, with what confidence
    revenue_method           TEXT NOT NULL DEFAULT 'pre_post',
    revenue_confidence       NUMERIC(5,4) NOT NULL DEFAULT 0.7000,

    -- Cost breakdown (4 components per estimate_*_cost) — kept for
    -- drill-down on the dashboard tile without rejoining sources.
    people_cost_vnd          NUMERIC(14,4) NOT NULL DEFAULT 0,
    ai_cost_vnd              NUMERIC(14,4) NOT NULL DEFAULT 0,
    infra_cost_vnd           NUMERIC(14,4) NOT NULL DEFAULT 0,
    integration_cost_vnd     NUMERIC(14,4) NOT NULL DEFAULT 0,

    -- Workflow run id that wrote this digest (NULL for dev/manual writes).
    -- Useful for tracing back to the Temporal workflow execution that
    -- produced the snapshot — every digest has a story.
    written_by_workflow_run  TEXT,

    computed_at              TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Same-month rewrites (recompute after a cost correction landed)
    -- bump this counter so the dashboard can flag "this number was
    -- revised N times this month".
    revision                 INTEGER NOT NULL DEFAULT 1,

    notes                    TEXT
);

-- One digest per (enterprise, month). Recompute UPDATEs the row in
-- place (handler increments `revision`) — never INSERTs a duplicate.
CREATE UNIQUE INDEX IF NOT EXISTS nov_monthly_digests_enterprise_month_uniq
    ON nov_monthly_digests (enterprise_id, month_start);

-- Trend query path — fetch latest 6 months for the dashboard tile.
CREATE INDEX IF NOT EXISTS nov_monthly_digests_trend_idx
    ON nov_monthly_digests (enterprise_id, month_start DESC);

-- Negative-NOV alert lookup — NOV-CORE-016 helper: list enterprises
-- whose current month is negative, paginated.
CREATE INDEX IF NOT EXISTS nov_monthly_digests_negative_idx
    ON nov_monthly_digests (month_start, nov_vnd)
    WHERE nov_vnd < 0;

-- RLS — every read MUST scope by enterprise_id (K-1 / ADR-0013).
ALTER TABLE nov_monthly_digests ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS nov_monthly_digests_tenant_isolation ON nov_monthly_digests;
CREATE POLICY nov_monthly_digests_tenant_isolation ON nov_monthly_digests
    USING (enterprise_id::text = current_setting('app.current_enterprise_id', true))
    WITH CHECK (enterprise_id::text = current_setting('app.current_enterprise_id', true));

COMMENT ON TABLE nov_monthly_digests IS
    'P15-S9 D7 — monthly NOV snapshots per enterprise. Written by the NOV monthly workflow; read by the ROI dashboard endpoint.';
COMMENT ON COLUMN nov_monthly_digests.revision IS
    'Bumped on UPSERT. Lets dashboard flag "this number was revised N times this month" if a late cost correction triggered recompute.';
COMMENT ON COLUMN nov_monthly_digests.month_start IS
    'First day of the digest month, UTC. Match enterprise_monthly_billing.billing_month convention so cross-table joins are obvious.';
