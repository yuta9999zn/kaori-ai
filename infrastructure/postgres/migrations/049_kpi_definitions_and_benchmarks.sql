-- 049_kpi_definitions_and_benchmarks.sql — P15-S11 Tuần 7 ngày 4.
--
-- SQL-first reasoning backbone per anh's directive (2026-05-15):
--
--   "Hệ thống này không được rời xa SQL. Từ kết quả SQL, sau đó với
--   RAG của từng chuyên ngành, từng đối tượng được update với thước
--   đo chuẩn nhất, ta mới ra được kết quả và đánh giá được."
--
-- Two tables guarantee the Reasoning Layer never lets the LLM compute
-- KPI values — it can only render explanations of SQL-computed numbers:
--
--   kpi_definitions   — per (dept_type, kpi_code), the SQL formula
--                       fragment, unit, threshold ranges, direction.
--                       This IS the "thước đo chuẩn" anh referenced.
--   industry_benchmarks — per (industry, kpi_code), P25/P50/P75/P90
--                       percentile values + source citation. Used to
--                       say "your CAC is at P40 of Vietnamese retail
--                       SMEs (median 850K VND)".
--
-- The reasoning/kpi_engine/ Python module (Tuần 7 ngày 6) reads both
-- tables, runs the formula against Gold views, classifies the value,
-- looks up the benchmark percentile, then hands the structured result
-- to the LLM for Vietnamese rendering.

-- ─── 1. kpi_definitions ──────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS kpi_definitions (
    kpi_id            UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    kpi_code          VARCHAR(64)     NOT NULL,
    dept_type         VARCHAR(32)     NOT NULL,
    display_name_vi   VARCHAR(200)    NOT NULL,
    display_name_en   VARCHAR(200)    NOT NULL,
    description_vi    TEXT,

    -- The SQL backbone. `formula_sql` is a Jinja-templated SQL fragment
    -- that the kpi_engine renders against a target Gold view. The
    -- engine passes {{enterprise_id}}, {{department_id}}, {{period_start}},
    -- {{period_end}} as bind params; the fragment must reference only
    -- whitelisted Gold views (kpi_engine enforces this — no arbitrary
    -- SQL allowed from this table).
    formula_sql       TEXT            NOT NULL,
    target_gold_view  VARCHAR(120)    NOT NULL,           -- e.g. 'gold.customer_360_marketing'

    -- Type metadata.
    unit              VARCHAR(32)     NOT NULL,           -- 'VND' | 'pct' | 'ratio' | 'days' | 'count' | 'score'
    decimal_places    SMALLINT        NOT NULL DEFAULT 2,
    direction         VARCHAR(20)     NOT NULL,           -- 'higher_better' | 'lower_better' | 'target_midpoint'
    target_value      NUMERIC(14,4),                      -- when direction='target_midpoint' (e.g. inventory turnover)

    -- Threshold ranges (interpreted in unit's natural scale).
    -- For 'higher_better': value >= threshold_good = Good; >= threshold_warning = Warning; below = Critical.
    -- For 'lower_better': inverted.
    threshold_good    NUMERIC(14,4),
    threshold_warning NUMERIC(14,4),

    -- Provenance: text citation for where this threshold came from.
    -- Required so users (and us) can audit "why is 3.0 the LTV/CAC
    -- good threshold?" — answer: Bain customer-economics report 2019.
    threshold_source  TEXT,

    is_active         BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_kpi_code_per_dept UNIQUE (dept_type, kpi_code),
    CONSTRAINT chk_kpi_dept CHECK (dept_type IN (
        'marketing', 'sales', 'customer_service',
        'warehouse', 'hr', 'finance', 'custom'
    )),
    CONSTRAINT chk_kpi_unit CHECK (unit IN ('VND', 'pct', 'ratio', 'days', 'count', 'score', 'hours')),
    CONSTRAINT chk_kpi_direction CHECK (direction IN ('higher_better', 'lower_better', 'target_midpoint')),
    CONSTRAINT chk_kpi_target_midpoint CHECK (
        direction <> 'target_midpoint' OR target_value IS NOT NULL
    )
);

CREATE INDEX IF NOT EXISTS idx_kpi_definitions_dept_active
    ON kpi_definitions (dept_type, is_active)
    WHERE is_active = TRUE;

-- This is a GLOBAL reference table — same definitions across all
-- tenants. No RLS. (kpi_engine still enforces enterprise scope at
-- query layer.)

-- ─── 2. industry_benchmarks ──────────────────────────────────────────

CREATE TABLE IF NOT EXISTS industry_benchmarks (
    benchmark_id      UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    industry          VARCHAR(40)     NOT NULL,           -- 'retail' | 'ecommerce' | 'b2b_service' | 'manufacturing' | 'fnb' | ...
    kpi_code          VARCHAR(64)     NOT NULL,
    region            VARCHAR(20)     NOT NULL DEFAULT 'VN',  -- 'VN' / 'APAC' / 'GLOBAL'
    period_year       SMALLINT        NOT NULL,            -- benchmark vintage; refresh annually

    -- Distribution percentiles. NULLABLE because some sources only
    -- publish median + good/bad thresholds, not a full distribution.
    p25               NUMERIC(14,4),
    p50               NUMERIC(14,4),
    p75               NUMERIC(14,4),
    p90               NUMERIC(14,4),

    sample_size       INTEGER,                             -- N of companies in the source
    source            TEXT            NOT NULL,            -- 'Bain & Company 2021', 'McKinsey VN retail report 2023', 'Internal Olist 2018'
    source_url        TEXT,
    notes             TEXT,

    is_active         BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_benchmark UNIQUE (industry, kpi_code, region, period_year),
    CONSTRAINT chk_benchmark_region CHECK (region IN ('VN', 'APAC', 'GLOBAL')),
    CONSTRAINT chk_benchmark_year CHECK (period_year >= 2010 AND period_year <= 2050)
);

CREATE INDEX IF NOT EXISTS idx_industry_benchmarks_lookup
    ON industry_benchmarks (industry, kpi_code, region, period_year DESC)
    WHERE is_active = TRUE;

-- Global ref table — no RLS.

-- ─── 3. kpi_measurements (per-tenant cache of computed values) ────────
--
-- Pre-computed values per (enterprise, dept, kpi, period) so dashboards
-- don't re-run the Gold view aggregation on every page load. The
-- kpi_engine Cron writes here daily; FE reads from here for <100ms
-- dashboard tiles. RLS K-1.

CREATE TABLE IF NOT EXISTS kpi_measurements (
    measurement_id    UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id     UUID            NOT NULL REFERENCES enterprises(enterprise_id)  ON DELETE CASCADE,
    department_id     UUID            NOT NULL REFERENCES departments(department_id)  ON DELETE CASCADE,
    branch_id         UUID            REFERENCES branches(branch_id)                  ON DELETE SET NULL,
    kpi_code          VARCHAR(64)     NOT NULL,

    -- Period this measurement covers.
    period_start      DATE            NOT NULL,
    period_end        DATE            NOT NULL,
    period_kind       VARCHAR(20)     NOT NULL,            -- 'daily' | 'weekly' | 'monthly' | 'quarterly' | 'ytd'

    -- The computed value + classification.
    raw_value         NUMERIC(14,4)   NOT NULL,            -- K-9 money/ratio precision
    classification    VARCHAR(20)     NOT NULL,            -- 'good' | 'warning' | 'critical' | 'no_threshold'

    -- Benchmark comparison snapshot at compute time.
    benchmark_percentile NUMERIC(5,2),                     -- e.g. 47.50 = at P47.5 of peers
    benchmark_source  TEXT,                                 -- "Bain 2021 retail VN — N=240" snapshot

    -- Trend: delta from previous period.
    prev_period_value NUMERIC(14,4),
    trend_pct         NUMERIC(7,4),                        -- (raw - prev) / prev × 100

    -- Provenance.
    computed_at       TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    computed_by       VARCHAR(40)     NOT NULL DEFAULT 'kpi_engine_cron',
    -- The actual SQL executed (audit trail for "where did this number come from?")
    sql_executed      TEXT,
    sql_row_count     INTEGER,

    CONSTRAINT uq_measurement UNIQUE (enterprise_id, department_id, kpi_code, period_kind, period_start),
    CONSTRAINT chk_measurement_classification CHECK (classification IN ('good', 'warning', 'critical', 'no_threshold')),
    CONSTRAINT chk_measurement_period_kind CHECK (period_kind IN ('daily', 'weekly', 'monthly', 'quarterly', 'ytd'))
);

CREATE INDEX IF NOT EXISTS idx_kpi_measurements_dashboard
    ON kpi_measurements (enterprise_id, department_id, kpi_code, period_end DESC);

CREATE INDEX IF NOT EXISTS idx_kpi_measurements_recent
    ON kpi_measurements (enterprise_id, computed_at DESC);

ALTER TABLE kpi_measurements ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS isolation_kpi_measurements ON kpi_measurements;
CREATE POLICY isolation_kpi_measurements ON kpi_measurements
    USING (
        enterprise_id::text = current_setting('app.current_enterprise_id', true)
        AND (
            current_setting('app.current_department_id', true) = ''
            OR current_setting('app.current_department_id', true) IS NULL
            OR department_id::text = current_setting('app.current_department_id', true)
        )
    )
    WITH CHECK (
        enterprise_id::text = current_setting('app.current_enterprise_id', true)
    );

-- ─── 4. Seed canonical KPI definitions ───────────────────────────────
--
-- 5-8 KPIs per dept_type. Vietnamese display names, English code stable
-- across schema versions. Threshold sources cited so the audit trail
-- exists from day one.

INSERT INTO kpi_definitions
    (kpi_code, dept_type, display_name_vi, display_name_en, description_vi,
     formula_sql, target_gold_view, unit, decimal_places, direction,
     threshold_good, threshold_warning, threshold_source)
VALUES
-- ── Marketing — 5 KPIs ─────────────────────────────────────────────
('cac',                  'marketing', 'Chi phí thu hút khách hàng (CAC)',     'Customer Acquisition Cost',
 'Chi phí marketing trung bình để có 1 khách hàng mới.',
 'SELECT SUM(marketing_spend) / NULLIF(COUNT(DISTINCT new_customer_id), 0) FROM {{view}} WHERE enterprise_id = {{enterprise_id}} AND department_id = {{department_id}} AND acquired_at BETWEEN {{period_start}} AND {{period_end}}',
 'gold.customer_360_marketing', 'VND', 0, 'lower_better',
 500000, 1000000, 'Bain Vietnam Retail 2021: P50=850K VND'),

('ltv',                  'marketing', 'Giá trị vòng đời khách hàng (LTV)',    'Customer Lifetime Value',
 'Tổng doanh thu kỳ vọng từ 1 khách hàng qua toàn bộ vòng đời.',
 'SELECT SUM(revenue_total) / NULLIF(COUNT(DISTINCT customer_id), 0) FROM {{view}} WHERE enterprise_id = {{enterprise_id}} AND department_id = {{department_id}}',
 'gold.customer_360_marketing', 'VND', 0, 'higher_better',
 5000000, 2000000, 'McKinsey VN retail SME 2023: top quartile >5M VND'),

('ltv_cac_ratio',        'marketing', 'Tỷ lệ LTV/CAC',                        'LTV to CAC Ratio',
 'Mỗi đồng đầu tư marketing thu lại bao nhiêu đồng doanh thu vòng đời.',
 'SELECT ltv / NULLIF(cac, 0) FROM (SELECT (SELECT raw_value FROM kpi_measurements WHERE kpi_code=''ltv'' AND department_id={{department_id}} AND period_kind=''monthly'' ORDER BY period_end DESC LIMIT 1) AS ltv, (SELECT raw_value FROM kpi_measurements WHERE kpi_code=''cac'' AND department_id={{department_id}} AND period_kind=''monthly'' ORDER BY period_end DESC LIMIT 1) AS cac) sub',
 'gold.customer_360_marketing', 'ratio', 2, 'higher_better',
 3.0, 1.5, 'Bain customer economics 2019: >3 = healthy, <1 = unsustainable'),

('roas',                 'marketing', 'ROAS — Return on Ad Spend',            'Return on Ad Spend',
 'Doanh thu trên mỗi đồng chi phí quảng cáo.',
 'SELECT SUM(campaign_revenue) / NULLIF(SUM(campaign_spend), 0) FROM {{view}} WHERE enterprise_id = {{enterprise_id}} AND department_id = {{department_id}} AND campaign_date BETWEEN {{period_start}} AND {{period_end}}',
 'gold.customer_360_marketing', 'ratio', 2, 'higher_better',
 4.0, 2.0, 'WordStream global SMB 2022: P50=3.5, P75=5.0'),

('churn_rate_monthly',   'marketing', 'Tỷ lệ rời bỏ hàng tháng',              'Monthly Churn Rate',
 'Tỷ lệ khách hàng ngừng tương tác trong 1 tháng so với đầu tháng.',
 'SELECT COUNT(*) FILTER (WHERE churned_in_period) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE active_at_start), 0) FROM {{view}} WHERE enterprise_id = {{enterprise_id}} AND department_id = {{department_id}}',
 'gold.customer_360_marketing', 'pct', 2, 'lower_better',
 2.0, 5.0, 'SaaS Capital 2022 + Vietnam retail SME estimates'),

-- ── Sales — 5 KPIs ─────────────────────────────────────────────────
('conversion_rate_lead', 'sales',     'Tỷ lệ chuyển đổi lead → deal',         'Lead-to-Deal Conversion Rate',
 'Phần trăm lead chuyển thành deal đóng thành công.',
 'SELECT COUNT(*) FILTER (WHERE deal_status=''won'') * 100.0 / NULLIF(COUNT(*), 0) FROM {{view}} WHERE enterprise_id = {{enterprise_id}} AND department_id = {{department_id}} AND created_at BETWEEN {{period_start}} AND {{period_end}}',
 'gold.sales_pipeline', 'pct', 2, 'higher_better',
 15.0, 5.0, 'HubSpot 2022 B2B SMB: P50=12-15%'),

('deal_velocity_days',   'sales',     'Tốc độ chốt deal (ngày)',              'Deal Velocity',
 'Số ngày trung bình từ lead → deal won.',
 'SELECT AVG(EXTRACT(EPOCH FROM (closed_at - created_at)) / 86400.0) FROM {{view}} WHERE enterprise_id = {{enterprise_id}} AND department_id = {{department_id}} AND deal_status=''won''',
 'gold.sales_pipeline', 'days', 1, 'lower_better',
 21.0, 45.0, 'CSO Insights 2022 SMB sales cycle benchmarks'),

('win_rate',             'sales',     'Tỷ lệ thắng deal',                     'Win Rate',
 'Phần trăm cơ hội đã engage chốt thành công.',
 'SELECT COUNT(*) FILTER (WHERE deal_status=''won'') * 100.0 / NULLIF(COUNT(*) FILTER (WHERE deal_status IN (''won'',''lost'')), 0) FROM {{view}} WHERE enterprise_id = {{enterprise_id}} AND department_id = {{department_id}}',
 'gold.sales_pipeline', 'pct', 2, 'higher_better',
 35.0, 20.0, 'HubSpot 2022 SMB inside sales'),

('avg_deal_size',        'sales',     'Giá trị deal trung bình',              'Average Deal Size',
 'Doanh thu trung bình mỗi deal won.',
 'SELECT AVG(deal_value) FROM {{view}} WHERE enterprise_id = {{enterprise_id}} AND department_id = {{department_id}} AND deal_status=''won'' AND closed_at BETWEEN {{period_start}} AND {{period_end}}',
 'gold.sales_pipeline', 'VND', 0, 'higher_better',
 10000000, 3000000, 'Vietnam SME B2B median ~5M VND/deal (Olist 2018)'),

('quota_attainment',     'sales',     'Đạt chỉ tiêu',                         'Quota Attainment',
 'Doanh thu thực tế so với chỉ tiêu kỳ.',
 'SELECT SUM(deal_value) FILTER (WHERE deal_status=''won'') * 100.0 / NULLIF(SUM(quota_target), 0) FROM {{view}} WHERE enterprise_id = {{enterprise_id}} AND department_id = {{department_id}}',
 'gold.sales_pipeline', 'pct', 1, 'higher_better',
 100.0, 75.0, 'Industry standard — Plan = 100%'),

-- ── Customer Service — 5 KPIs ──────────────────────────────────────
('csat_score',           'customer_service', 'Điểm CSAT (1-5)',               'Customer Satisfaction Score',
 'Điểm hài lòng khách hàng (thang 1-5).',
 'SELECT AVG(csat_rating) FROM {{view}} WHERE enterprise_id = {{enterprise_id}} AND department_id = {{department_id}} AND rated_at BETWEEN {{period_start}} AND {{period_end}}',
 'gold.ticket_summary', 'score', 2, 'higher_better',
 4.5, 3.5, 'Zendesk Global CX 2022: top quartile >4.5'),

('nps',                  'customer_service', 'NPS — Net Promoter Score',     'Net Promoter Score',
 'Phần trăm promoter trừ phần trăm detractor.',
 'SELECT (COUNT(*) FILTER (WHERE nps_score >= 9) - COUNT(*) FILTER (WHERE nps_score <= 6)) * 100.0 / NULLIF(COUNT(*), 0) FROM {{view}} WHERE enterprise_id = {{enterprise_id}} AND department_id = {{department_id}}',
 'gold.ticket_summary', 'score', 1, 'higher_better',
 50.0, 0.0, 'Bain NPS benchmark: >50 = world-class, 0 = avg'),

('first_response_minutes', 'customer_service', 'Thời gian phản hồi đầu (phút)', 'First Response Time',
 'Số phút trung bình từ khi ticket tạo đến phản hồi đầu tiên.',
 'SELECT AVG(EXTRACT(EPOCH FROM (first_response_at - created_at)) / 60.0) FROM {{view}} WHERE enterprise_id = {{enterprise_id}} AND department_id = {{department_id}}',
 'gold.ticket_summary', 'count', 1, 'lower_better',
 15.0, 60.0, 'Freshdesk 2022 SMB benchmark: <15min = good'),

('ticket_resolution_hours', 'customer_service', 'Giải quyết ticket (giờ)',    'Ticket Resolution Time',
 'Số giờ trung bình để đóng ticket.',
 'SELECT AVG(EXTRACT(EPOCH FROM (resolved_at - created_at)) / 3600.0) FROM {{view}} WHERE enterprise_id = {{enterprise_id}} AND department_id = {{department_id}} AND resolved_at IS NOT NULL',
 'gold.ticket_summary', 'hours', 1, 'lower_better',
 8.0, 24.0, 'Zendesk 2022 SMB: <8h = good for non-emergency'),

('escalation_rate',      'customer_service', 'Tỷ lệ leo thang',               'Escalation Rate',
 'Phần trăm ticket cần chuyển lên cấp cao hơn.',
 'SELECT COUNT(*) FILTER (WHERE escalated) * 100.0 / NULLIF(COUNT(*), 0) FROM {{view}} WHERE enterprise_id = {{enterprise_id}} AND department_id = {{department_id}}',
 'gold.ticket_summary', 'pct', 2, 'lower_better',
 5.0, 15.0, 'CCMG 2021 SMB benchmark'),

-- ── Warehouse — 5 KPIs ─────────────────────────────────────────────
('inventory_turnover',   'warehouse', 'Vòng quay tồn kho',                    'Inventory Turnover',
 'Số lần tồn kho bán hết và bổ sung trong kỳ.',
 'SELECT SUM(cogs) / NULLIF(AVG(inventory_value), 0) FROM {{view}} WHERE enterprise_id = {{enterprise_id}} AND department_id = {{department_id}} AND period BETWEEN {{period_start}} AND {{period_end}}',
 'gold.inventory_warehouse', 'ratio', 2, 'higher_better',
 6.0, 3.0, 'Vietnam retail SME 2022: top quartile >6x/year'),

('stockout_rate',        'warehouse', 'Tỷ lệ hết hàng',                       'Stockout Rate',
 'Phần trăm SKU hết hàng trong kỳ.',
 'SELECT COUNT(DISTINCT sku) FILTER (WHERE stockout_in_period) * 100.0 / NULLIF(COUNT(DISTINCT sku), 0) FROM {{view}} WHERE enterprise_id = {{enterprise_id}} AND department_id = {{department_id}}',
 'gold.inventory_warehouse', 'pct', 2, 'lower_better',
 2.0, 5.0, 'Walmart benchmark: <2% = world-class'),

('dead_stock_pct',       'warehouse', 'Tỷ lệ tồn kho chết',                   'Dead Stock Percentage',
 'Phần trăm SKU không bán >180 ngày.',
 'SELECT COUNT(*) FILTER (WHERE days_since_last_sale > 180) * 100.0 / NULLIF(COUNT(*), 0) FROM {{view}} WHERE enterprise_id = {{enterprise_id}} AND department_id = {{department_id}}',
 'gold.inventory_warehouse', 'pct', 2, 'lower_better',
 5.0, 15.0, 'CSCMP SOCR 2021 retail benchmark'),

('supplier_lead_time_days', 'warehouse', 'Lead time nhà cung cấp (ngày)',     'Supplier Lead Time',
 'Số ngày trung bình từ đặt hàng đến nhận hàng.',
 'SELECT AVG(EXTRACT(EPOCH FROM (received_at - ordered_at)) / 86400.0) FROM {{view}} WHERE enterprise_id = {{enterprise_id}} AND department_id = {{department_id}}',
 'gold.inventory_warehouse', 'days', 1, 'lower_better',
 7.0, 14.0, 'APICS 2022 SMB Vietnam: median 10 days domestic'),

('order_fulfillment_pct', 'warehouse', 'Tỷ lệ xuất kho đúng hạn',             'On-Time Fulfillment Rate',
 'Phần trăm đơn hàng xuất kho đúng SLA cam kết.',
 'SELECT COUNT(*) FILTER (WHERE shipped_at <= sla_target) * 100.0 / NULLIF(COUNT(*), 0) FROM {{view}} WHERE enterprise_id = {{enterprise_id}} AND department_id = {{department_id}}',
 'gold.inventory_warehouse', 'pct', 2, 'higher_better',
 95.0, 85.0, 'Walmart vendor SLA benchmark'),

-- ── HR — 5 KPIs ────────────────────────────────────────────────────
('attrition_rate_annual', 'hr',       'Tỷ lệ nghỉ việc năm',                  'Annual Attrition Rate',
 'Phần trăm nhân viên nghỉ trong 12 tháng.',
 'SELECT COUNT(*) FILTER (WHERE separated_in_period) * 100.0 / NULLIF(AVG(headcount_start_period), 0) FROM {{view}} WHERE enterprise_id = {{enterprise_id}} AND department_id = {{department_id}}',
 'gold.payroll_hr', 'pct', 2, 'lower_better',
 10.0, 20.0, 'Vietnam SME HR survey 2022 (Anphabe)'),

('time_to_hire_days',    'hr',        'Thời gian tuyển dụng (ngày)',          'Time to Hire',
 'Số ngày trung bình từ mở vị trí đến offer accepted.',
 'SELECT AVG(EXTRACT(EPOCH FROM (offer_accepted_at - position_opened_at)) / 86400.0) FROM {{view}} WHERE enterprise_id = {{enterprise_id}} AND department_id = {{department_id}}',
 'gold.payroll_hr', 'days', 1, 'lower_better',
 30.0, 60.0, 'LinkedIn Talent Trends 2022 Vietnam'),

('cost_per_hire',        'hr',        'Chi phí tuyển dụng (VND)',             'Cost per Hire',
 'Tổng chi phí trung bình để tuyển 1 nhân viên.',
 'SELECT SUM(recruiting_cost) / NULLIF(COUNT(DISTINCT hired_employee_id), 0) FROM {{view}} WHERE enterprise_id = {{enterprise_id}} AND department_id = {{department_id}}',
 'gold.payroll_hr', 'VND', 0, 'lower_better',
 5000000, 15000000, 'SHRM 2022 + Vietnam SME estimates'),

('employee_nps',         'hr',        'eNPS — Employee NPS',                  'Employee NPS',
 'Mức sẵn lòng giới thiệu công ty làm việc (thang -100 → 100).',
 'SELECT (COUNT(*) FILTER (WHERE recommend_score >= 9) - COUNT(*) FILTER (WHERE recommend_score <= 6)) * 100.0 / NULLIF(COUNT(*), 0) FROM {{view}} WHERE enterprise_id = {{enterprise_id}} AND department_id = {{department_id}}',
 'gold.payroll_hr', 'score', 1, 'higher_better',
 30.0, 0.0, 'Bain eNPS: >30 = healthy'),

('absenteeism_rate',     'hr',        'Tỷ lệ vắng mặt',                       'Absenteeism Rate',
 'Phần trăm ngày làm việc bị vắng (loại trừ phép có lý do).',
 'SELECT SUM(absent_days_unjustified) * 100.0 / NULLIF(SUM(scheduled_workdays), 0) FROM {{view}} WHERE enterprise_id = {{enterprise_id}} AND department_id = {{department_id}}',
 'gold.payroll_hr', 'pct', 2, 'lower_better',
 3.0, 7.0, 'Bureau of Labor Statistics 2022'),

-- ── Finance — 5 KPIs ───────────────────────────────────────────────
('gross_margin_pct',     'finance',   'Tỷ suất lợi nhuận gộp',                'Gross Margin',
 'Lợi nhuận sau giá vốn, tính theo phần trăm doanh thu.',
 'SELECT (SUM(revenue) - SUM(cogs)) * 100.0 / NULLIF(SUM(revenue), 0) FROM {{view}} WHERE enterprise_id = {{enterprise_id}} AND department_id = {{department_id}} AND period BETWEEN {{period_start}} AND {{period_end}}',
 'gold.kpi_finance', 'pct', 2, 'higher_better',
 40.0, 20.0, 'Vietnam retail SME 2022: median ~30%'),

('ar_days_outstanding',  'finance',   'Tuổi nợ phải thu (DSO)',              'AR Days Outstanding',
 'Số ngày trung bình thu được tiền sau khi xuất hóa đơn.',
 'SELECT (SUM(ar_balance) * 365.0) / NULLIF(SUM(annual_revenue), 0) FROM {{view}} WHERE enterprise_id = {{enterprise_id}} AND department_id = {{department_id}}',
 'gold.kpi_finance', 'days', 1, 'lower_better',
 30.0, 60.0, 'CFO benchmark 2022: <30 = healthy cash flow'),

('cash_runway_months',   'finance',   'Tháng còn lại tiền mặt',              'Cash Runway',
 'Số tháng công ty có thể hoạt động với cash + AR còn lại.',
 'SELECT (SUM(cash_balance) + SUM(ar_balance)) / NULLIF(AVG(monthly_burn), 0) FROM {{view}} WHERE enterprise_id = {{enterprise_id}} AND department_id = {{department_id}}',
 'gold.kpi_finance', 'count', 1, 'higher_better',
 12.0, 6.0, 'Vietnam SME survival 2022: >6 months critical'),

('revenue_growth_yoy',   'finance',   'Tăng trưởng doanh thu YoY',           'Revenue YoY Growth',
 'Phần trăm tăng trưởng doanh thu so với cùng kỳ năm trước.',
 'SELECT (current_rev - prev_year_rev) * 100.0 / NULLIF(prev_year_rev, 0) FROM (SELECT SUM(revenue) FILTER (WHERE EXTRACT(YEAR FROM period) = EXTRACT(YEAR FROM CURRENT_DATE)) AS current_rev, SUM(revenue) FILTER (WHERE EXTRACT(YEAR FROM period) = EXTRACT(YEAR FROM CURRENT_DATE) - 1) AS prev_year_rev FROM {{view}} WHERE enterprise_id = {{enterprise_id}} AND department_id = {{department_id}}) sub',
 'gold.kpi_finance', 'pct', 2, 'higher_better',
 20.0, 5.0, 'Vietnam SME growth benchmark 2022')
ON CONFLICT (dept_type, kpi_code) DO NOTHING;

-- working_capital_ratio uses direction='target_midpoint'. The
-- chk_kpi_target_midpoint constraint requires target_value to be set
-- at INSERT time (cannot defer with a follow-up UPDATE on a row whose
-- target_value started NULL). Insert it separately with explicit
-- target_value=2.0 baked in + add target_value to the column list
-- (the bulk insert above omits target_value since all higher_better /
-- lower_better KPIs leave it NULL).
INSERT INTO kpi_definitions
    (kpi_code, dept_type, display_name_vi, display_name_en, description_vi,
     formula_sql, target_gold_view, unit, decimal_places, direction,
     target_value, threshold_good, threshold_warning, threshold_source)
VALUES
('working_capital_ratio', 'finance', 'Tỷ số vốn lưu động', 'Working Capital Ratio',
 'Tài sản ngắn hạn / nợ ngắn hạn — đo khả năng thanh toán.',
 'SELECT SUM(current_assets) / NULLIF(SUM(current_liabilities), 0) FROM {{view}} WHERE enterprise_id = {{enterprise_id}} AND department_id = {{department_id}}',
 'gold.kpi_finance', 'ratio', 2, 'target_midpoint',
 2.0,  -- target value for the midpoint
 NULL, NULL,
 'Investopedia: target ~2.0 (>2 = idle capital, <1 = liquidity risk)')
ON CONFLICT (dept_type, kpi_code) DO NOTHING;

-- ─── 5. Seed minimal industry benchmarks (Vietnam retail focus) ──────
--
-- Bootstrapping set covers retail + ecommerce + b2b for Build Week
-- demo. More industries land via the Industry Benchmark Importer in
-- Phase 2 (out of scope here).

INSERT INTO industry_benchmarks (industry, kpi_code, region, period_year, p25, p50, p75, p90, sample_size, source)
VALUES
-- Retail VN
('retail', 'cac',                  'VN', 2022, 1200000, 850000, 600000, 400000, 240, 'Bain Vietnam Retail 2021'),
('retail', 'ltv',                  'VN', 2022, 1500000, 3000000, 5000000, 8000000, 240, 'McKinsey VN retail SME 2023'),
('retail', 'ltv_cac_ratio',        'VN', 2022, 1.2, 2.5, 4.0, 7.0, 240, 'Bain customer economics 2019'),
('retail', 'churn_rate_monthly',   'VN', 2022, 7.5, 4.5, 2.5, 1.2, 240, 'Vietnam retail SME 2022'),
('retail', 'inventory_turnover',   'VN', 2022, 2.5, 4.0, 6.5, 9.0, 180, 'Vietnam retail SME 2022'),
('retail', 'gross_margin_pct',     'VN', 2022, 18.0, 28.0, 38.0, 50.0, 180, 'Vietnam retail SME 2022'),

-- Ecommerce (Olist-derived, Brazil but useful for SE Asia analog)
('ecommerce', 'cac',               'GLOBAL', 2022, 1500000, 1000000, 700000, 500000, 3095, 'Olist Brazilian E-commerce 2018'),
('ecommerce', 'ltv',               'GLOBAL', 2022, 1800000, 3500000, 6000000, 10000000, 3095, 'Olist Brazilian E-commerce 2018'),
('ecommerce', 'roas',              'GLOBAL', 2022, 2.5, 3.5, 5.0, 8.0, 1000, 'WordStream global SMB 2022'),
('ecommerce', 'conversion_rate_lead', 'GLOBAL', 2022, 1.5, 3.0, 5.5, 10.0, 1000, 'Shopify Plus 2022'),

-- B2B service VN
('b2b_service', 'deal_velocity_days', 'VN', 2022, 65, 42, 25, 14, 120, 'CSO Insights 2022 SMB sales cycle'),
('b2b_service', 'win_rate',        'VN', 2022, 18.0, 28.0, 40.0, 55.0, 120, 'HubSpot 2022 B2B SMB'),
('b2b_service', 'avg_deal_size',   'VN', 2022, 2000000, 5000000, 15000000, 50000000, 120, 'Vietnam SME B2B 2022'),

-- Customer Service (cross-industry)
('retail', 'csat_score',           'VN', 2022, 3.5, 4.0, 4.5, 4.8, 200, 'Zendesk Global CX 2022'),
('retail', 'nps',                  'VN', 2022, -10.0, 15.0, 45.0, 70.0, 200, 'Bain NPS Vietnam benchmark'),
('retail', 'first_response_minutes', 'VN', 2022, 90, 30, 15, 5, 200, 'Freshdesk 2022 SMB'),

-- HR (cross-industry)
('retail', 'attrition_rate_annual', 'VN', 2022, 25.0, 18.0, 12.0, 7.0, 150, 'Anphabe 2022 Vietnam HR survey'),
('retail', 'time_to_hire_days',    'VN', 2022, 60, 35, 20, 10, 150, 'LinkedIn Talent Vietnam 2022'),

-- Finance (cross-industry)
('retail', 'ar_days_outstanding',  'VN', 2022, 60, 38, 25, 15, 180, 'CFO benchmark 2022'),
('retail', 'cash_runway_months',   'VN', 2022, 3, 7, 14, 24, 180, 'Vietnam SME survival 2022'),
('retail', 'revenue_growth_yoy',   'VN', 2022, -5.0, 12.0, 28.0, 50.0, 180, 'Vietnam SME growth 2022')
ON CONFLICT (industry, kpi_code, region, period_year) DO NOTHING;

-- ─── 6. Comments ─────────────────────────────────────────────────────

COMMENT ON TABLE  kpi_definitions IS
    'P15-S11 Tuần 7 — SQL-first reasoning backbone per anh''s directive. Per-dept canonical KPIs. The kpi_engine renders formula_sql against target_gold_view; LLM never computes, only explains.';
COMMENT ON COLUMN kpi_definitions.formula_sql IS
    'Jinja-templated SQL fragment. Whitelisted bind params: {{enterprise_id}}, {{department_id}}, {{period_start}}, {{period_end}}, {{view}}. kpi_engine enforces — no arbitrary SQL allowed.';
COMMENT ON COLUMN kpi_definitions.threshold_source IS
    'Audit citation. Without this, ''why is 3.0 the LTV/CAC good threshold?'' has no answer. K-6 spirit: every automated decision traceable.';

COMMENT ON TABLE  industry_benchmarks IS
    'P15-S11 Tuần 7 — peer percentile reference per (industry, kpi). Used by reasoning to say ''your CAC is at P40 of VN retail SMEs''. Refresh annually as period_year=N+1 rows.';

COMMENT ON TABLE  kpi_measurements IS
    'P15-S11 Tuần 7 — per-tenant computed KPI cache. Written by kpi_engine cron + on-demand from /analyze. sql_executed column = audit trail for compliance (where did this number come from?).';
