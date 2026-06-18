-- 052_per_dept_gold_views.sql — P15-S11 Tuần 8 Step 4.3b.
--
-- Gold (vàng) views per spec §6.3 + §7, sitting ON TOP of the Silver
-- per-domain tables shipped by mig 051. Per anh's directive 2026-05-15:
--
--   "Cần phải có đầy đủ ba lớp đồng bạc vàng, và có chức năng nhiệm vụ
--   riêng, không để chồng chéo."
--
-- Strict separation guard rails enforced here:
--   - Every view's FROM clause references ONLY silver_* / gold_* tables.
--   - NO `bronze_rows`, NO `silver_rows` (the raw JSONB landing table),
--     NO JSONB extraction operators.
--   - Aggregations + joins + derived metrics only. If a metric needs
--     pre-cleaning or typing, that work belongs in Silver, not Gold.
--
-- Views (matching mig 049 kpi_definitions.target_gold_view):
--
--   gold.customer_360_marketing   ← silver_customers + silver_orders + gold_features
--   gold.sales_pipeline           ← silver_orders (+ silver_customers join)
--   gold.ticket_summary           ← silver_tickets
--   gold.inventory_warehouse      ← silver_inventory
--   gold.payroll_hr               ← silver_employees
--   gold.kpi_finance              ← silver_finance_periods
--
-- ABAC §16.4 / K-1: Postgres views inherit RLS from the underlying
-- tables — silver_* RLS (set up in mig 051) carries through. The
-- `app.current_enterprise_id` GUC set by middleware filters every read.

-- ─── 1. gold schema ──────────────────────────────────────────────────

CREATE SCHEMA IF NOT EXISTS gold;

COMMENT ON SCHEMA gold IS
    'P15-S11 mig 052 — per-department canonical aggregation views. Read-mostly. '
    'Strict rule: views in this schema NEVER touch Bronze (bronze_rows or the '
    'silver_rows JSONB landing) — they aggregate Silver per-domain tables only. '
    'Mig 051 owns the Silver layer.';

-- ─── 2. gold.customer_360_marketing ──────────────────────────────────
--
-- Marketing's customer-centric view. Joins:
--   silver_customers  ← acquisition + marketing_spend + segment + revenue_total
--   silver_orders     ← actual transactions (for revenue rollup + last activity)
--   gold_features     ← Phase 1 aggregator's revenue_at_risk + last_purchase_at
--
-- Each row = one customer. Derived columns enable mig 049 CAC + LTV +
-- churn + ROAS formulas without further joining.

CREATE OR REPLACE VIEW gold.customer_360_marketing AS
SELECT
    sc.enterprise_id,
    sc.department_id,
    sc.branch_id,
    sc.customer_external_id              AS customer_id,
    sc.customer_external_id              AS new_customer_id,
    sc.name,
    sc.acquired_at,
    sc.acquisition_channel,
    sc.marketing_spend,
    sc.segment,
    sc.revenue_total,
    sc.last_purchase_at,
    -- Order-derived aggregates per customer (NULL when customer has no orders).
    (SELECT SUM(so.campaign_revenue)
     FROM silver_orders so
     WHERE so.enterprise_id = sc.enterprise_id
       AND so.customer_external_id = sc.customer_external_id)  AS campaign_revenue,
    (SELECT SUM(so.campaign_spend)
     FROM silver_orders so
     WHERE so.enterprise_id = sc.enterprise_id
       AND so.customer_external_id = sc.customer_external_id)  AS campaign_spend,
    (SELECT MAX(so.campaign_date)
     FROM silver_orders so
     WHERE so.enterprise_id = sc.enterprise_id
       AND so.customer_external_id = sc.customer_external_id)  AS campaign_date,
    -- Phase 1 aggregator signals.
    gf.revenue_at_risk,
    (gf.last_purchase_at IS NULL OR gf.last_purchase_at < NOW() - INTERVAL '30 days')
        AS churned_in_period,
    (gf.last_purchase_at IS NOT NULL
        AND gf.last_purchase_at >= NOW() - INTERVAL '60 days')
        AS active_at_start,
    gf.computed_at                       AS gold_features_computed_at
FROM silver_customers sc
LEFT JOIN gold_features gf
       ON gf.enterprise_id        = sc.enterprise_id
      AND gf.customer_external_id = sc.customer_external_id;

COMMENT ON VIEW gold.customer_360_marketing IS
    'Marketing per-customer view = silver_customers ⊕ silver_orders ⊕ '
    'gold_features. Each row = 1 customer with derived campaign + churn '
    'signals. Mig 049 CAC/LTV/churn/ROAS formulas read here.';

-- ─── 3. gold.sales_pipeline ──────────────────────────────────────────
--
-- Sales's deal-centric view. Built from silver_orders; optionally joined
-- to silver_customers for customer-context display columns.

CREATE OR REPLACE VIEW gold.sales_pipeline AS
SELECT
    so.enterprise_id,
    so.department_id,
    so.branch_id,
    so.order_external_id                 AS deal_id,
    so.lead_external_id                  AS lead_id,
    so.customer_external_id              AS customer_id,
    sc.name                              AS customer_name,
    sc.segment                           AS customer_segment,
    so.rep_user_id,
    so.deal_status,
    so.deal_value,
    so.quota_target,
    so.created_at_source                 AS created_at,
    so.closed_at,
    -- Derived: deal cycle in days (NULL while open).
    CASE
        WHEN so.closed_at IS NOT NULL AND so.created_at_source IS NOT NULL
            THEN EXTRACT(EPOCH FROM (so.closed_at - so.created_at_source)) / 86400.0
        ELSE NULL
    END                                  AS cycle_days
FROM silver_orders so
LEFT JOIN silver_customers sc
       ON sc.enterprise_id        = so.enterprise_id
      AND sc.customer_external_id = so.customer_external_id;

COMMENT ON VIEW gold.sales_pipeline IS
    'Sales deal-centric view = silver_orders ⊕ silver_customers (display). '
    'Each row = 1 deal with derived cycle_days. Mig 049 conversion/velocity/'
    'win-rate/deal-size/quota formulas read here.';

-- ─── 4. gold.ticket_summary ──────────────────────────────────────────
--
-- Customer Service ticket view. Pure projection from silver_tickets
-- because the schema already has resolution timestamps + satisfaction.

CREATE OR REPLACE VIEW gold.ticket_summary AS
SELECT
    st.enterprise_id,
    st.department_id,
    st.branch_id,
    st.ticket_external_id                AS ticket_id,
    st.customer_external_id              AS customer_id,
    sc.name                              AS customer_name,
    st.agent_user_id,
    st.csat_rating,
    st.nps_score,
    st.created_at_source                 AS created_at,
    st.first_response_at,
    st.resolved_at,
    st.rated_at,
    st.escalated,
    st.category,
    st.priority,
    -- Derived: response time in minutes, resolution time in hours.
    CASE
        WHEN st.first_response_at IS NOT NULL AND st.created_at_source IS NOT NULL
            THEN EXTRACT(EPOCH FROM (st.first_response_at - st.created_at_source)) / 60.0
        ELSE NULL
    END                                  AS first_response_minutes,
    CASE
        WHEN st.resolved_at IS NOT NULL AND st.created_at_source IS NOT NULL
            THEN EXTRACT(EPOCH FROM (st.resolved_at - st.created_at_source)) / 3600.0
        ELSE NULL
    END                                  AS resolution_hours
FROM silver_tickets st
LEFT JOIN silver_customers sc
       ON sc.enterprise_id        = st.enterprise_id
      AND sc.customer_external_id = st.customer_external_id;

COMMENT ON VIEW gold.ticket_summary IS
    'CS ticket view = silver_tickets ⊕ silver_customers (display). Each row '
    '= 1 ticket with derived first_response_minutes + resolution_hours. '
    'Mig 049 CSAT/NPS/response/resolution/escalation formulas read here.';

-- ─── 5. gold.inventory_warehouse ─────────────────────────────────────
--
-- Warehouse inventory view. Projects silver_inventory; mixed grain
-- (snapshots + PO lines) inherited from the underlying table.

CREATE OR REPLACE VIEW gold.inventory_warehouse AS
SELECT
    si.enterprise_id,
    si.department_id,
    si.branch_id,
    si.inventory_key,
    si.sku,
    si.supplier_external_id              AS supplier_id,
    si.cogs,
    si.inventory_value,
    si.period,
    si.stockout_in_period,
    si.days_since_last_sale,
    si.ordered_at,
    si.received_at,
    si.shipped_at,
    si.sla_target
FROM silver_inventory si;

COMMENT ON VIEW gold.inventory_warehouse IS
    'Warehouse view = silver_inventory pass-through (no joins yet — Phase 2 '
    'adds silver_purchase_orders join for richer supplier context). Mig 049 '
    'turnover/stockout/dead-stock/lead-time/fulfillment formulas read here.';

-- ─── 6. gold.payroll_hr ──────────────────────────────────────────────
--
-- HR view. Projects silver_employees with derived hiring-funnel days.

CREATE OR REPLACE VIEW gold.payroll_hr AS
SELECT
    se.enterprise_id,
    se.department_id,
    se.branch_id,
    se.employee_external_id              AS employee_id,
    se.period,
    se.title,
    se.hired_at,
    se.separated_at,
    se.separated_in_period,
    se.position_opened_at,
    se.offer_accepted_at,
    se.recruiting_cost,
    se.hired_employee_id,
    se.recommend_score,
    se.absent_days_unjustified,
    se.scheduled_workdays,
    se.headcount_start_period,
    -- Derived: time-to-hire in days (NULL until offer accepted).
    CASE
        WHEN se.offer_accepted_at IS NOT NULL AND se.position_opened_at IS NOT NULL
            THEN EXTRACT(EPOCH FROM (se.offer_accepted_at - se.position_opened_at)) / 86400.0
        ELSE NULL
    END                                  AS time_to_hire_days
FROM silver_employees se;

COMMENT ON VIEW gold.payroll_hr IS
    'HR per-employee view = silver_employees with derived time_to_hire_days. '
    'Mig 049 attrition/time-to-hire/cost/eNPS/absenteeism formulas read here.';

-- ─── 7. gold.kpi_finance ─────────────────────────────────────────────
--
-- Finance view. Projects silver_finance_periods with derived margin %.

CREATE OR REPLACE VIEW gold.kpi_finance AS
SELECT
    sfp.enterprise_id,
    sfp.department_id,
    sfp.branch_id,
    sfp.period,
    sfp.revenue,
    sfp.cogs,
    sfp.operating_expense,
    sfp.annual_revenue,
    sfp.ar_balance,
    sfp.cash_balance,
    sfp.monthly_burn,
    sfp.current_assets,
    sfp.current_liabilities,
    -- Derived: gross margin % (NULL when revenue is zero).
    CASE
        WHEN sfp.revenue IS NOT NULL AND sfp.revenue > 0 AND sfp.cogs IS NOT NULL
            THEN (sfp.revenue - sfp.cogs) * 100.0 / sfp.revenue
        ELSE NULL
    END                                  AS gross_margin_pct,
    -- Derived: cash runway months (cash + AR / monthly burn).
    CASE
        WHEN sfp.monthly_burn IS NOT NULL AND sfp.monthly_burn > 0
            THEN (COALESCE(sfp.cash_balance, 0) + COALESCE(sfp.ar_balance, 0))
                / sfp.monthly_burn
        ELSE NULL
    END                                  AS cash_runway_months
FROM silver_finance_periods sfp;

COMMENT ON VIEW gold.kpi_finance IS
    'Finance per-period view = silver_finance_periods with derived '
    'gross_margin_pct + cash_runway_months. Mig 049 margin/DSO/runway/growth/'
    'working-capital formulas read here.';

-- ─── 8. Grants — kaori_app reads ─────────────────────────────────────

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kaori_app') THEN
        EXECUTE 'GRANT USAGE ON SCHEMA gold TO kaori_app';
        EXECUTE 'GRANT SELECT ON ALL TABLES IN SCHEMA gold TO kaori_app';
        EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA gold GRANT SELECT ON TABLES TO kaori_app';
    END IF;
END $$;
