-- =============================================================
-- Kaori — NB/RJ Data Pipeline Schema
-- ELT Pattern: Bronze (raw) → Silver (clean) → Gold (business)
-- Single PostgreSQL database, single customer
-- =============================================================

-- =============================================================
-- BRONZE LAYER — raw data, exactly as it came from source
-- Never modified after insert. Append-only.
-- Columns: all text to accept dirty data without errors.
-- =============================================================

CREATE TABLE IF NOT EXISTS bronze_daily_revenue (
    id              SERIAL PRIMARY KEY,
    source_file     TEXT NOT NULL,          -- original filename
    loaded_at       TIMESTAMP DEFAULT NOW(),
    store_raw       TEXT,                   -- exactly as found in file
    date_raw        TEXT,
    cash_raw        TEXT,
    transfer_raw    TEXT,
    card_raw        TEXT,
    customer_count_raw TEXT,
    notes_raw       TEXT
);

CREATE TABLE IF NOT EXISTS bronze_nb_customer_sessions (
    id              SERIAL PRIMARY KEY,
    source_file     TEXT NOT NULL,
    loaded_at       TIMESTAMP DEFAULT NOW(),
    customer_name_raw  TEXT,
    phone_raw          TEXT,
    visit_date_raw     TEXT,
    service_raw        TEXT,
    body_area_raw      TEXT,
    amount_raw         TEXT,
    staff_raw          TEXT,
    notes_raw          TEXT
);

CREATE TABLE IF NOT EXISTS bronze_bank_transactions (
    id              SERIAL PRIMARY KEY,
    source_file     TEXT NOT NULL,
    loaded_at       TIMESTAMP DEFAULT NOW(),
    txn_date_raw    TEXT,
    amount_raw      TEXT,
    direction_raw   TEXT,                   -- 'CREDIT' / 'DEBIT' / 'PS NO' / etc.
    description_raw TEXT,
    balance_raw     TEXT,
    ref_raw         TEXT
);

CREATE TABLE IF NOT EXISTS bronze_monthly_pnl (
    id              SERIAL PRIMARY KEY,
    source_file     TEXT NOT NULL,
    loaded_at       TIMESTAMP DEFAULT NOW(),
    store_raw       TEXT,
    year_month_raw  TEXT,
    revenue_raw     TEXT,
    cost_goods_raw  TEXT,
    cost_salary_raw TEXT,
    cost_rent_raw   TEXT,
    cost_other_raw  TEXT,
    net_profit_raw  TEXT,
    bep_target_raw  TEXT
);

CREATE TABLE IF NOT EXISTS bronze_staff_shifts (
    id              SERIAL PRIMARY KEY,
    source_file     TEXT NOT NULL,
    loaded_at       TIMESTAMP DEFAULT NOW(),
    store_raw       TEXT,
    staff_name_raw  TEXT,
    shift_date_raw  TEXT,
    hours_raw       TEXT,
    role_raw        TEXT
);

CREATE TABLE IF NOT EXISTS bronze_rj_revenue (
    id              SERIAL PRIMARY KEY,
    source_file     TEXT NOT NULL,
    loaded_at       TIMESTAMP DEFAULT NOW(),
    store_raw       TEXT,
    date_raw        TEXT,
    revenue_raw     TEXT,
    cast_name_raw   TEXT,
    customer_type_raw TEXT,  -- 'fixed' / 'new' / etc.
    notes_raw       TEXT
);

-- =============================================================
-- SILVER LAYER — cleaned, typed, validated, deduplicated
-- Source of truth for all downstream analytics
-- =============================================================

CREATE TABLE IF NOT EXISTS silver_daily_revenue (
    id              SERIAL PRIMARY KEY,
    store           VARCHAR(30) NOT NULL,   -- 'NB_MAIN', 'NB_FC_1', 'RJ_BAR', 'BAR_MINI'
    date            DATE NOT NULL,
    cash            NUMERIC(14,0) NOT NULL DEFAULT 0,
    transfer        NUMERIC(14,0) NOT NULL DEFAULT 0,
    card            NUMERIC(14,0) NOT NULL DEFAULT 0,
    total           NUMERIC(14,0) GENERATED ALWAYS AS (cash + transfer + card) STORED,
    customer_count  INTEGER,
    source_file     TEXT,
    updated_at      TIMESTAMP DEFAULT NOW(),
    UNIQUE(store, date)
);

CREATE TABLE IF NOT EXISTS silver_nb_customers (
    customer_id     VARCHAR(50) PRIMARY KEY,    -- generated: phone or hash
    phone           VARCHAR(20),
    name            VARCHAR(200),
    first_visit     DATE,
    last_visit      DATE,
    total_visits    INTEGER DEFAULT 0,
    total_spent     NUMERIC(14,0) DEFAULT 0,
    main_service    VARCHAR(100),               -- most frequent service
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS silver_nb_customer_sessions (
    id              SERIAL PRIMARY KEY,
    customer_id     VARCHAR(50) REFERENCES silver_nb_customers(customer_id),
    visit_date      DATE NOT NULL,
    service         VARCHAR(200),
    body_area       VARCHAR(100),
    amount          NUMERIC(14,0),
    staff           VARCHAR(100),
    source_file     TEXT,
    UNIQUE(customer_id, visit_date, service)    -- prevent duplicate session loads
);

CREATE TABLE IF NOT EXISTS silver_bank_transactions (
    id              SERIAL PRIMARY KEY,
    txn_date        DATE NOT NULL,
    amount          NUMERIC(14,0) NOT NULL,
    direction       VARCHAR(6) NOT NULL CHECK (direction IN ('IN', 'OUT')),
    description     TEXT,
    category        VARCHAR(30) NOT NULL DEFAULT 'OTHER',
    -- CUSTOMER_PAYMENT | PAYROLL | OPERATING_COST | TAX | BANK_FEE | OTHER
    is_manual_override BOOLEAN DEFAULT FALSE,
    ref             TEXT,
    source_file     TEXT,
    loaded_at       TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS silver_monthly_pnl (
    id              SERIAL PRIMARY KEY,
    store           VARCHAR(30) NOT NULL,
    year_month      CHAR(7) NOT NULL,           -- '2026-04'
    revenue         NUMERIC(14,0),
    cost_goods      NUMERIC(14,0),
    cost_salary     NUMERIC(14,0),
    cost_rent       NUMERIC(14,0),
    cost_other      NUMERIC(14,0),
    net_profit      NUMERIC(14,0),
    bep_target      NUMERIC(14,0),
    source_file     TEXT,
    updated_at      TIMESTAMP DEFAULT NOW(),
    UNIQUE(store, year_month)
);

CREATE TABLE IF NOT EXISTS silver_staff_shifts (
    id              SERIAL PRIMARY KEY,
    store           VARCHAR(30) NOT NULL,
    staff_name      VARCHAR(100) NOT NULL,
    shift_date      DATE NOT NULL,
    hours_worked    NUMERIC(4,1),
    role            VARCHAR(50),
    source_file     TEXT,
    UNIQUE(store, staff_name, shift_date)
);

CREATE TABLE IF NOT EXISTS silver_inventory_daily (
    id              SERIAL PRIMARY KEY,
    store           VARCHAR(30) NOT NULL,
    date            DATE NOT NULL,
    product_name    TEXT NOT NULL,
    metric_type     VARCHAR(30) NOT NULL,
    -- inventory | usage | remaining | quantity | amount
    value           NUMERIC(14,2),
    source_file     TEXT,
    loaded_at       TIMESTAMP DEFAULT NOW(),
    UNIQUE(store, date, product_name, metric_type)
);

-- Bronze companion for wide-format inventory sheets.
-- Holds one pivoted row per (source_row, product) — raw text, never modified.
CREATE TABLE IF NOT EXISTS bronze_inventory_raw (
    id              SERIAL PRIMARY KEY,
    source_file     TEXT NOT NULL,
    loaded_at       TIMESTAMP DEFAULT NOW(),
    sheet_name_raw  TEXT,
    date_raw        TEXT,   -- raw day value from sheet (e.g. "1", "2", "3")
    product_name    TEXT,
    inventory_raw   TEXT,   -- 在庫 / zaiko
    usage_raw       TEXT,   -- 使う / tsukau
    remaining_raw   TEXT,   -- nokoru / remaining
    quantity_raw    TEXT,   -- Get / received
    amount_raw      TEXT    -- total
);

-- =============================================================
-- GOLD LAYER — business-ready views for dashboard & reports
-- Read-only. Rebuilt from silver on demand.
-- =============================================================

-- Daily KPI view — main dashboard source
CREATE OR REPLACE VIEW gold_daily_kpi AS
SELECT
    r.store,
    r.date,
    r.cash,
    r.transfer,
    r.card,
    r.total,
    r.customer_count,
    -- BEP gap (requires bep_target from silver_monthly_pnl)
    p.bep_target / 30 AS bep_daily_target,
    r.total - (p.bep_target / 30) AS bep_gap,
    CASE WHEN r.total >= (p.bep_target / 30) THEN true ELSE false END AS bep_achieved,
    -- 4-week rolling average for anomaly detection
    AVG(r.total) OVER (
        PARTITION BY r.store
        ORDER BY r.date
        ROWS BETWEEN 27 PRECEDING AND 1 PRECEDING
    ) AS rolling_avg_28d,
    -- WoW comparison
    LAG(r.total, 7) OVER (PARTITION BY r.store ORDER BY r.date) AS total_same_day_last_week
FROM silver_daily_revenue r
LEFT JOIN silver_monthly_pnl p
    ON p.store = r.store
    AND p.year_month = TO_CHAR(r.date, 'YYYY-MM');

-- Customer return rate — for NB dashboard
CREATE OR REPLACE VIEW gold_nb_customer_stats AS
SELECT
    DATE_TRUNC('month', s.visit_date) AS month,
    COUNT(DISTINCT s.customer_id) AS unique_customers,
    COUNT(DISTINCT CASE
        WHEN c.total_visits > 1 THEN s.customer_id
    END) AS returning_customers,
    COUNT(DISTINCT CASE
        WHEN c.total_visits = 1 THEN s.customer_id
    END) AS new_customers,
    ROUND(
        COUNT(DISTINCT CASE WHEN c.total_visits > 1 THEN s.customer_id END)::NUMERIC
        / NULLIF(COUNT(DISTINCT s.customer_id), 0) * 100, 1
    ) AS return_rate_pct,
    SUM(s.amount) AS total_revenue
FROM silver_nb_customer_sessions s
JOIN silver_nb_customers c ON c.customer_id = s.customer_id
GROUP BY DATE_TRUNC('month', s.visit_date);

-- Bank monthly summary — cashflow overview
CREATE OR REPLACE VIEW gold_bank_monthly_summary AS
SELECT
    DATE_TRUNC('month', txn_date) AS month,
    SUM(CASE WHEN direction = 'IN' THEN amount ELSE 0 END) AS total_in,
    SUM(CASE WHEN direction = 'OUT' THEN amount ELSE 0 END) AS total_out,
    SUM(CASE WHEN direction = 'IN' THEN amount ELSE -amount END) AS net_cashflow,
    SUM(CASE WHEN category = 'CUSTOMER_PAYMENT' AND direction = 'IN' THEN amount ELSE 0 END) AS customer_payments,
    SUM(CASE WHEN category = 'PAYROLL' THEN amount ELSE 0 END) AS payroll_out,
    SUM(CASE WHEN category = 'OPERATING_COST' THEN amount ELSE 0 END) AS operating_cost_out,
    SUM(CASE WHEN category = 'TAX' THEN amount ELSE 0 END) AS tax_out,
    SUM(CASE WHEN category = 'OTHER' THEN amount ELSE 0 END) AS unclassified,
    COUNT(CASE WHEN category = 'OTHER' THEN 1 END) AS unclassified_count
FROM silver_bank_transactions
GROUP BY DATE_TRUNC('month', txn_date)
ORDER BY month DESC;

-- Morning report source — exactly what the report script queries
CREATE OR REPLACE VIEW gold_morning_report AS
WITH yesterday AS (
    SELECT
        store,
        date,
        total,
        customer_count,
        bep_daily_target,
        bep_gap,
        bep_achieved,
        total_same_day_last_week,
        ROUND(
            (total - total_same_day_last_week)::NUMERIC
            / NULLIF(total_same_day_last_week, 0) * 100, 1
        ) AS wow_change_pct
    FROM gold_daily_kpi
    WHERE date = CURRENT_DATE - 1
)
SELECT * FROM yesterday;

-- =============================================================
-- SYSTEM TABLES — operational metadata
-- =============================================================

CREATE TABLE IF NOT EXISTS etl_run_log (
    id              SERIAL PRIMARY KEY,
    run_at          TIMESTAMP DEFAULT NOW(),
    script          VARCHAR(100) NOT NULL,
    source_file     TEXT,
    rows_read       INTEGER,
    rows_inserted   INTEGER,
    rows_skipped    INTEGER,
    status          VARCHAR(20) DEFAULT 'SUCCESS',  -- SUCCESS | ERROR | WARNING
    error_message   TEXT
);

-- Read-only user for Looker Studio (run separately as superuser)
-- CREATE USER kaori_readonly WITH PASSWORD 'readonly_password';
-- GRANT CONNECT ON DATABASE kaori TO kaori_readonly;
-- GRANT USAGE ON SCHEMA public TO kaori_readonly;
-- GRANT SELECT ON ALL TABLES IN SCHEMA public TO kaori_readonly;
-- GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO kaori_readonly;
-- ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO kaori_readonly;
