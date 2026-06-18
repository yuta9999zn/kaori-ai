-- 051_silver_per_domain_tables.sql — P15-S11 Tuần 8 Step 4.3a.
--
-- Per anh's directive 2026-05-15:
--
--   "Cần phải có đầy đủ ba lớp đồng bạc vàng, và có chức năng nhiệm vụ
--   riêng, không để chồng chéo."
--
-- Medallion strict separation:
--
--   Bronze (đồng)  — raw immutable JSONB in bronze_rows. Append-only,
--                    SHA-256 dedupe, no typing, no cleaning. K-2 / K-8.
--   Silver (bạc)   — cleaned + typed + ONE-row-per-entity. THIS migration.
--                    Per-domain tables; Bronze→Silver ETL projects JSONB →
--                    typed columns. Silver is where data has its proper
--                    shape; nothing downstream re-extracts JSONB.
--   Gold (vàng)    — aggregations + derived metrics on top of Silver,
--                    dashboard-ready. NEVER reads Bronze. Mig 052.
--
-- The old mig 051 violated this by having Gold views extract JSONB from
-- silver_rows — that's Silver's job. This rewrite ships proper Silver
-- per-domain tables; mig 052 builds Gold views on top.
--
-- Tables (one per business domain, mapped to the 6 dept_types of mig 046):
--
--   silver_customers          ← Marketing + Sales + CS share this
--   silver_orders             ← Sales primary, Marketing campaign attribution
--   silver_tickets            ← Customer Service
--   silver_inventory          ← Warehouse
--   silver_employees          ← HR
--   silver_finance_periods    ← Finance
--
-- Each table:
--   - PK = (enterprise_id, natural_business_id) so the same business
--     entity ID across tenants doesn't collide.
--   - Carries enterprise_id + branch_id + department_id for ABAC §16.4.
--   - RLS K-1 enterprise scope + ABAC dept scope (same pattern as mig 047).
--   - Has indexes on hot read paths used by mig 052 Gold views.
--
-- Build Week reality: Olist seed (Tuần 7 ngày 7) writes raw bronze_rows.
-- The seed script gets a parallel projection pass that fills these
-- Silver tables for the demo (Tuần 8 Step 4.4). Phase 2 replaces the
-- script with a real Bronze→Silver ETL worker.

-- ─── 1. silver_customers ─────────────────────────────────────────────
--
-- Shared by Marketing (LTV / CAC / churn), Sales (customer of deal),
-- CS (ticket attribution). 1 row per (enterprise, customer_external_id).

CREATE TABLE IF NOT EXISTS silver_customers (
    enterprise_id           UUID            NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    customer_external_id    TEXT            NOT NULL,

    -- Org attribution (NULLABLE: a customer might not be locked to a
    -- single dept — Marketing acquires, Sales converts, CS retains).
    branch_id               UUID            REFERENCES branches(branch_id)       ON DELETE SET NULL,
    department_id           UUID            REFERENCES departments(department_id) ON DELETE SET NULL,

    -- Identity (PII — K-5 redaction applies for external LLM calls).
    name                    TEXT,
    email                   TEXT,
    phone                   TEXT,

    -- Marketing / acquisition signals.
    acquired_at             TIMESTAMPTZ,
    acquisition_channel     TEXT,                                         -- 'organic'|'paid_ads'|'referral'|...
    marketing_spend         NUMERIC(14,4),                                -- K-9 money
    segment                 TEXT,                                         -- 'vip'|'regular'|'lapsed'|...

    -- Aggregate signals (Phase 2 ETL refreshes; Build Week pre-computed by seed).
    revenue_total           NUMERIC(14,4),                                -- lifetime revenue
    last_purchase_at        TIMESTAMPTZ,

    -- Provenance — which Bronze ingest produced this row.
    source_id               UUID            REFERENCES data_sources(source_id) ON DELETE SET NULL,
    bronze_run_id           UUID            REFERENCES pipeline_runs(run_id)   ON DELETE SET NULL,

    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    PRIMARY KEY (enterprise_id, customer_external_id)
);

CREATE INDEX IF NOT EXISTS idx_silver_customers_dept
    ON silver_customers (enterprise_id, department_id);
CREATE INDEX IF NOT EXISTS idx_silver_customers_branch
    ON silver_customers (enterprise_id, branch_id);
CREATE INDEX IF NOT EXISTS idx_silver_customers_acquired
    ON silver_customers (enterprise_id, acquired_at DESC);
CREATE INDEX IF NOT EXISTS idx_silver_customers_last_purchase
    ON silver_customers (enterprise_id, last_purchase_at DESC NULLS LAST);

-- ─── 2. silver_orders ────────────────────────────────────────────────
--
-- Sales pipeline + Marketing campaign attribution. 1 row per order/deal.

CREATE TABLE IF NOT EXISTS silver_orders (
    enterprise_id           UUID            NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    order_external_id       TEXT            NOT NULL,                     -- deal_id / order_id

    branch_id               UUID            REFERENCES branches(branch_id)       ON DELETE SET NULL,
    department_id           UUID            REFERENCES departments(department_id) ON DELETE SET NULL,

    -- Link to customer + sales rep (soft — rep may not have an enterprise_user row).
    customer_external_id    TEXT,
    rep_user_id             TEXT,
    lead_external_id        TEXT,

    -- Sales pipeline shape.
    deal_status             VARCHAR(20),                                  -- 'won'|'lost'|'open'|'pending'
    deal_value              NUMERIC(14,4),                                -- K-9 money
    quota_target            NUMERIC(14,4),                                -- rep's quota for the period

    created_at_source       TIMESTAMPTZ,
    closed_at               TIMESTAMPTZ,

    -- Marketing attribution (NULL when not campaign-driven).
    campaign_external_id    TEXT,
    campaign_revenue        NUMERIC(14,4),
    campaign_spend          NUMERIC(14,4),
    campaign_date           TIMESTAMPTZ,

    source_id               UUID            REFERENCES data_sources(source_id) ON DELETE SET NULL,
    bronze_run_id           UUID            REFERENCES pipeline_runs(run_id)   ON DELETE SET NULL,

    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    PRIMARY KEY (enterprise_id, order_external_id),
    CONSTRAINT chk_silver_orders_status CHECK (
        deal_status IS NULL OR deal_status IN ('won', 'lost', 'open', 'pending', 'cancelled')
    )
);

CREATE INDEX IF NOT EXISTS idx_silver_orders_dept_status
    ON silver_orders (enterprise_id, department_id, deal_status);
CREATE INDEX IF NOT EXISTS idx_silver_orders_customer
    ON silver_orders (enterprise_id, customer_external_id);
CREATE INDEX IF NOT EXISTS idx_silver_orders_closed_at
    ON silver_orders (enterprise_id, department_id, closed_at DESC NULLS LAST);

-- ─── 3. silver_tickets ───────────────────────────────────────────────
--
-- Customer Service tickets. 1 row per ticket.

CREATE TABLE IF NOT EXISTS silver_tickets (
    enterprise_id           UUID            NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    ticket_external_id      TEXT            NOT NULL,

    branch_id               UUID            REFERENCES branches(branch_id)       ON DELETE SET NULL,
    department_id           UUID            REFERENCES departments(department_id) ON DELETE SET NULL,

    customer_external_id    TEXT,
    agent_user_id           TEXT,

    -- Satisfaction signals.
    csat_rating             NUMERIC(3,2),                                 -- 1.00 → 5.00 typical
    nps_score               SMALLINT,                                     -- 0-10 typical
    rated_at                TIMESTAMPTZ,

    -- Lifecycle timestamps.
    created_at_source       TIMESTAMPTZ,
    first_response_at       TIMESTAMPTZ,
    resolved_at             TIMESTAMPTZ,

    -- Workflow signals.
    escalated               BOOLEAN         NOT NULL DEFAULT FALSE,
    category                TEXT,                                         -- 'complaint'|'inquiry'|'refund'|'tech'|...
    priority                VARCHAR(20),                                  -- 'low'|'normal'|'high'|'critical'

    source_id               UUID            REFERENCES data_sources(source_id) ON DELETE SET NULL,
    bronze_run_id           UUID            REFERENCES pipeline_runs(run_id)   ON DELETE SET NULL,

    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    PRIMARY KEY (enterprise_id, ticket_external_id),
    CONSTRAINT chk_silver_tickets_priority CHECK (
        priority IS NULL OR priority IN ('low', 'normal', 'high', 'critical')
    )
);

CREATE INDEX IF NOT EXISTS idx_silver_tickets_dept
    ON silver_tickets (enterprise_id, department_id);
CREATE INDEX IF NOT EXISTS idx_silver_tickets_resolved
    ON silver_tickets (enterprise_id, resolved_at DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_silver_tickets_customer
    ON silver_tickets (enterprise_id, customer_external_id);

-- ─── 4. silver_inventory ─────────────────────────────────────────────
--
-- Warehouse inventory snapshot per (SKU, period) + supplier-PO line.
-- Mixed grain Build Week (similar to Phase 1 silver_rows compromise);
-- Phase 2 splits into silver_inventory_snapshots + silver_purchase_orders.

CREATE TABLE IF NOT EXISTS silver_inventory (
    enterprise_id           UUID            NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    -- Composite natural key: SKU + period_date for snapshots; PO line id for orders.
    inventory_key           TEXT            NOT NULL,

    branch_id               UUID            REFERENCES branches(branch_id)       ON DELETE SET NULL,
    department_id           UUID            REFERENCES departments(department_id) ON DELETE SET NULL,

    sku                     TEXT,
    supplier_external_id    TEXT,

    -- Stock economics.
    cogs                    NUMERIC(14,4),
    inventory_value         NUMERIC(14,4),
    period                  DATE,

    -- Stock health.
    stockout_in_period      BOOLEAN         NOT NULL DEFAULT FALSE,
    days_since_last_sale    INTEGER,

    -- Supplier order lifecycle (NULL for snapshot rows).
    ordered_at              TIMESTAMPTZ,
    received_at             TIMESTAMPTZ,
    shipped_at              TIMESTAMPTZ,
    sla_target              TIMESTAMPTZ,

    source_id               UUID            REFERENCES data_sources(source_id) ON DELETE SET NULL,
    bronze_run_id           UUID            REFERENCES pipeline_runs(run_id)   ON DELETE SET NULL,

    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    PRIMARY KEY (enterprise_id, inventory_key)
);

CREATE INDEX IF NOT EXISTS idx_silver_inventory_dept_period
    ON silver_inventory (enterprise_id, department_id, period DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_silver_inventory_sku
    ON silver_inventory (enterprise_id, sku);
CREATE INDEX IF NOT EXISTS idx_silver_inventory_dead_stock
    ON silver_inventory (enterprise_id, department_id, days_since_last_sale DESC NULLS LAST)
    WHERE days_since_last_sale > 180;

-- ─── 5. silver_employees ─────────────────────────────────────────────
--
-- HR employee snapshots. 1 row per (enterprise, employee, period).

CREATE TABLE IF NOT EXISTS silver_employees (
    enterprise_id           UUID            NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    employee_external_id    TEXT            NOT NULL,
    -- Period the snapshot represents (NULL for "current state" rows).
    period                  DATE            NOT NULL DEFAULT CURRENT_DATE,

    branch_id               UUID            REFERENCES branches(branch_id)       ON DELETE SET NULL,
    department_id           UUID            REFERENCES departments(department_id) ON DELETE SET NULL,

    -- Identity (PII — same K-5 rules as silver_customers).
    full_name               TEXT,
    title                   TEXT,

    -- Lifecycle.
    hired_at                TIMESTAMPTZ,
    separated_at            TIMESTAMPTZ,
    separated_in_period     BOOLEAN         NOT NULL DEFAULT FALSE,

    -- Hiring funnel attribution.
    position_opened_at      TIMESTAMPTZ,
    offer_accepted_at       TIMESTAMPTZ,
    recruiting_cost         NUMERIC(14,4),
    hired_employee_id       TEXT,                                         -- set on the "first month" row

    -- Engagement signals.
    recommend_score         SMALLINT,                                     -- eNPS 0-10
    absent_days_unjustified NUMERIC(6,2),                                 -- partial-day allowed
    scheduled_workdays      NUMERIC(6,2),

    -- Period headcount aggregate (denormalised so attrition rate KPI
    -- doesn't need a window query at read time).
    headcount_start_period  INTEGER,

    source_id               UUID            REFERENCES data_sources(source_id) ON DELETE SET NULL,
    bronze_run_id           UUID            REFERENCES pipeline_runs(run_id)   ON DELETE SET NULL,

    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    PRIMARY KEY (enterprise_id, employee_external_id, period)
);

CREATE INDEX IF NOT EXISTS idx_silver_employees_dept_period
    ON silver_employees (enterprise_id, department_id, period DESC);
CREATE INDEX IF NOT EXISTS idx_silver_employees_separated
    ON silver_employees (enterprise_id, separated_at DESC NULLS LAST)
    WHERE separated_in_period = TRUE;

-- ─── 6. silver_finance_periods ───────────────────────────────────────
--
-- Finance per-period state. 1 row per (enterprise, dept, period).

CREATE TABLE IF NOT EXISTS silver_finance_periods (
    enterprise_id           UUID            NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    period                  DATE            NOT NULL,

    branch_id               UUID            REFERENCES branches(branch_id)       ON DELETE SET NULL,
    department_id           UUID            REFERENCES departments(department_id) ON DELETE SET NULL,

    -- P&L.
    revenue                 NUMERIC(14,4),
    cogs                    NUMERIC(14,4),
    operating_expense       NUMERIC(14,4),
    annual_revenue          NUMERIC(14,4),                                -- rolling 12-month, for DSO denominator

    -- Balance sheet.
    ar_balance              NUMERIC(14,4),
    cash_balance            NUMERIC(14,4),
    monthly_burn            NUMERIC(14,4),
    current_assets          NUMERIC(14,4),
    current_liabilities     NUMERIC(14,4),

    source_id               UUID            REFERENCES data_sources(source_id) ON DELETE SET NULL,
    bronze_run_id           UUID            REFERENCES pipeline_runs(run_id)   ON DELETE SET NULL,

    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    PRIMARY KEY (enterprise_id, department_id, period)
);

CREATE INDEX IF NOT EXISTS idx_silver_finance_periods_period
    ON silver_finance_periods (enterprise_id, period DESC);

-- ─── 7. RLS — K-1 + ABAC dept scope (mirrors mig 047 pattern) ────────

DO $$
DECLARE
    tbl TEXT;
BEGIN
    FOREACH tbl IN ARRAY ARRAY[
        'silver_customers', 'silver_orders', 'silver_tickets',
        'silver_inventory', 'silver_employees', 'silver_finance_periods'
    ]
    LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', tbl);

        EXECUTE format('DROP POLICY IF EXISTS isolation_%I ON %I', tbl, tbl);
        EXECUTE format($f$
            CREATE POLICY isolation_%I ON %I
                USING (enterprise_id::text = current_setting('app.current_enterprise_id', true))
                WITH CHECK (enterprise_id::text = current_setting('app.current_enterprise_id', true))
        $f$, tbl, tbl);

        EXECUTE format('DROP POLICY IF EXISTS abac_dept_scope_%I ON %I', tbl, tbl);
        EXECUTE format($f$
            CREATE POLICY abac_dept_scope_%I ON %I
                USING (
                    enterprise_id::text = current_setting('app.current_enterprise_id', true)
                    AND (
                        current_setting('app.current_department_id', true) = ''
                        OR current_setting('app.current_department_id', true) IS NULL
                        OR department_id IS NULL
                        OR department_id::text = current_setting('app.current_department_id', true)
                    )
                )
        $f$, tbl, tbl);
    END LOOP;
END $$;

-- ─── 8. kaori_app grants ─────────────────────────────────────────────

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kaori_app') THEN
        EXECUTE 'GRANT SELECT, INSERT, UPDATE ON silver_customers       TO kaori_app';
        EXECUTE 'GRANT SELECT, INSERT, UPDATE ON silver_orders          TO kaori_app';
        EXECUTE 'GRANT SELECT, INSERT, UPDATE ON silver_tickets         TO kaori_app';
        EXECUTE 'GRANT SELECT, INSERT, UPDATE ON silver_inventory       TO kaori_app';
        EXECUTE 'GRANT SELECT, INSERT, UPDATE ON silver_employees       TO kaori_app';
        EXECUTE 'GRANT SELECT, INSERT, UPDATE ON silver_finance_periods TO kaori_app';
    END IF;
END $$;

-- ─── 9. Comments ─────────────────────────────────────────────────────

COMMENT ON TABLE silver_customers IS
    'P15-S11 mig 051 — Silver per-customer master. Shared by Marketing/Sales/CS. '
    'Bronze→Silver ETL projects bronze_rows JSONB → typed columns; Gold views '
    'aggregate from here. Phase 1 = manual seed; Phase 2 = real ETL worker.';
COMMENT ON TABLE silver_orders IS
    'P15-S11 mig 051 — Silver per-order/deal. Sales pipeline shape with optional '
    'Marketing campaign attribution. 1 row = 1 order. Gold sales_pipeline aggregates.';
COMMENT ON TABLE silver_tickets IS
    'P15-S11 mig 051 — Silver per-ticket. CS satisfaction + lifecycle. Gold '
    'ticket_summary aggregates.';
COMMENT ON TABLE silver_inventory IS
    'P15-S11 mig 051 — Silver inventory state. Mixed grain (snapshots + PO lines) '
    'Build Week; Phase 2 splits.';
COMMENT ON TABLE silver_employees IS
    'P15-S11 mig 051 — Silver per-employee snapshot. 1 row per (employee, period). '
    'HR uses this; Gold payroll_hr aggregates attrition/hiring funnel.';
COMMENT ON TABLE silver_finance_periods IS
    'P15-S11 mig 051 — Silver per-period financial state. 1 row per (dept, period). '
    'Gold kpi_finance aggregates margin/DSO/runway from here.';
