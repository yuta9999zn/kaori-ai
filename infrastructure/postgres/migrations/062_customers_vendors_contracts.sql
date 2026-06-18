-- =====================================================================
-- 062_customers_vendors_contracts.sql
--
-- P15-S11 — Persist customer + vendor + contract data per anh's
-- clarification 2026-05-16:
--   "khách hàng là riêng, vendor là riêng nhé, vendor thì cũng cần có
--    thông tin của vendor, ngoài ra cũng cần có các hợp đồng của khách
--    hàng và vendor nhé"
--
-- Tables
-- ------
--   1. customers              — clients Kaori serves (KH-…). Rich profile
--                                fields: type, industry, capability, titles.
--   2. vendors                — suppliers Kaori uses (NCC-…). Same shape
--                                spirit, with vendor_type instead of
--                                customer_type.
--   3. customer_contracts     — license/MSA/pilot/addon/custom between
--                                Kaori and a customer.
--   4. vendor_contracts       — MSA/SOW/SaaS/consulting between Kaori
--                                and a vendor.
--
-- Schema mirrors the 4 CSVs at `data/sample/{customers-profile,
-- vendors-profile, customer-contracts, vendor-contracts}.csv` so the
-- seed migration (063) can project the CSV content directly into typed
-- rows without remapping fields.
--
-- K-1 / K-19 / RLS
-- ----------------
-- All four tables are tenant-scoped via `enterprise_id` (= the Kaori
-- enterprise that owns the relationship, not the customer/vendor's own
-- enterprise). RLS policies enforce read/write only within the
-- caller's `app.current_enterprise_id` GUC, same pattern as bronze_rows
-- and the workflow tables.
--
-- K-9 numeric precision
-- ---------------------
-- `value_vnd` and `annual_revenue_vnd` use NUMERIC(20,0) — pilot deals
-- run up to 250000000000000 VND (Vingroup). Keep precision >= 14.
-- =====================================================================


-- =====================================================================
-- 1. customers
-- =====================================================================

CREATE TABLE IF NOT EXISTS customers (
    customer_id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id            UUID         NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,

    -- Short code visible in CRM, invoices, contract titles. Per-enterprise
    -- unique so two Kaori workspaces don't collide.
    code                     VARCHAR(50)  NOT NULL,

    -- Basic info
    customer_name            TEXT         NOT NULL,
    contact_person           TEXT,
    phone                    VARCHAR(50),
    email                    VARCHAR(254),
    tax_code                 VARCHAR(50),
    id_card_number           VARCHAR(50),       -- individual customers only
    address                  TEXT,
    city                     TEXT,
    country                  VARCHAR(10)  NOT NULL DEFAULT 'VN',

    -- Classification
    customer_type            VARCHAR(20)  NOT NULL,
    industry                 TEXT,

    -- Experience + capability
    years_in_business        INT,
    employees_count          INT,
    annual_revenue_vnd       NUMERIC(20, 0),
    credit_rating            VARCHAR(10),
    titles_awards            TEXT,
    certifications           TEXT,
    experience_summary       TEXT,

    -- Relationship
    relationship_tier        VARCHAR(20),
    first_contact_date       DATE,
    assigned_account_manager VARCHAR(254),
    note                     TEXT,

    -- Lifecycle
    status                   VARCHAR(20)  NOT NULL DEFAULT 'active',
    created_at               TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at               TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_customer_code_per_enterprise UNIQUE (enterprise_id, code),
    CONSTRAINT chk_customer_type CHECK (customer_type IN
        ('individual', 'SMB', 'enterprise', 'strategic')),
    CONSTRAINT chk_customer_status CHECK (status IN
        ('active', 'inactive', 'archived', 'blacklisted')),
    CONSTRAINT chk_customer_relationship_tier CHECK (
        relationship_tier IS NULL OR relationship_tier IN
        ('platinum', 'gold', 'silver', 'bronze')
    )
);

CREATE INDEX IF NOT EXISTS idx_customers_enterprise_status
    ON customers (enterprise_id, status);
CREATE INDEX IF NOT EXISTS idx_customers_type
    ON customers (enterprise_id, customer_type);
CREATE INDEX IF NOT EXISTS idx_customers_tier
    ON customers (enterprise_id, relationship_tier);


-- =====================================================================
-- 2. vendors
-- =====================================================================

CREATE TABLE IF NOT EXISTS vendors (
    vendor_id                UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id            UUID         NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,

    code                     VARCHAR(50)  NOT NULL,

    -- Basic
    vendor_name              TEXT         NOT NULL,
    contact_person           TEXT,
    phone                    VARCHAR(50),
    email                    VARCHAR(254),
    tax_code                 VARCHAR(50),
    address                  TEXT,
    city                     TEXT,
    country                  VARCHAR(10)  NOT NULL DEFAULT 'VN',

    -- Classification
    vendor_type              VARCHAR(20)  NOT NULL,
    services_offered         TEXT,
    industries_served        TEXT,

    -- Experience + capability
    years_in_business        INT,
    employees_count          INT,
    annual_revenue_vnd       NUMERIC(20, 0),
    credit_rating            VARCHAR(10),
    certifications           TEXT,
    titles_awards            TEXT,
    experience_summary       TEXT,

    -- Relationship
    reliability_tier         VARCHAR(20),
    first_contract_date      DATE,
    managed_by               VARCHAR(254),
    note                     TEXT,

    status                   VARCHAR(20)  NOT NULL DEFAULT 'active',
    created_at               TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at               TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_vendor_code_per_enterprise UNIQUE (enterprise_id, code),
    CONSTRAINT chk_vendor_type CHECK (vendor_type IN
        ('supplier', 'platform', 'consultant', 'agency', 'contractor')),
    CONSTRAINT chk_vendor_status CHECK (status IN
        ('active', 'inactive', 'archived', 'blacklisted')),
    CONSTRAINT chk_vendor_reliability_tier CHECK (
        reliability_tier IS NULL OR reliability_tier IN
        ('platinum', 'gold', 'silver', 'bronze')
    )
);

CREATE INDEX IF NOT EXISTS idx_vendors_enterprise_status
    ON vendors (enterprise_id, status);
CREATE INDEX IF NOT EXISTS idx_vendors_type
    ON vendors (enterprise_id, vendor_type);


-- =====================================================================
-- 3. customer_contracts
-- =====================================================================

CREATE TABLE IF NOT EXISTS customer_contracts (
    contract_id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id            UUID         NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    customer_id              UUID         NOT NULL REFERENCES customers(customer_id) ON DELETE RESTRICT,

    contract_no              VARCHAR(100) NOT NULL,
    contract_type            VARCHAR(40)  NOT NULL,
    description              TEXT,

    -- Dates
    signed_at                DATE,
    start_at                 DATE,
    end_at                   DATE,

    -- Money
    value_vnd                NUMERIC(20, 0),
    currency                 VARCHAR(10)  NOT NULL DEFAULT 'VND',
    payment_terms_days       INT,
    payment_schedule         VARCHAR(40),

    -- Status + signers
    status                   VARCHAR(20)  NOT NULL DEFAULT 'draft',
    signed_by_customer       TEXT,
    customer_signer_title    TEXT,
    signed_by_us             TEXT,
    us_signer_title          TEXT,

    attachment_uri           TEXT,
    renewal_type             VARCHAR(20),
    note                     TEXT,

    created_at               TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at               TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_customer_contract_no UNIQUE (enterprise_id, contract_no),
    CONSTRAINT chk_customer_contract_type CHECK (contract_type IN (
        'license_enterprise', 'license_pilot', 'framework_msa',
        'addon_module', 'custom_solution', 'consulting', 'one_off'
    )),
    CONSTRAINT chk_customer_contract_status CHECK (status IN (
        'draft', 'under_review', 'active', 'expired', 'closed', 'terminated'
    )),
    CONSTRAINT chk_customer_contract_renewal CHECK (
        renewal_type IS NULL OR renewal_type IN ('manual', 'auto_renew', 'one_off')
    )
);

CREATE INDEX IF NOT EXISTS idx_customer_contracts_customer
    ON customer_contracts (customer_id, status);
CREATE INDEX IF NOT EXISTS idx_customer_contracts_status
    ON customer_contracts (enterprise_id, status);
CREATE INDEX IF NOT EXISTS idx_customer_contracts_end_date
    ON customer_contracts (enterprise_id, end_at)
    WHERE status IN ('active', 'under_review');


-- =====================================================================
-- 4. vendor_contracts
-- =====================================================================

CREATE TABLE IF NOT EXISTS vendor_contracts (
    contract_id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id            UUID         NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    vendor_id                UUID         NOT NULL REFERENCES vendors(vendor_id) ON DELETE RESTRICT,

    contract_no              VARCHAR(100) NOT NULL,
    contract_type            VARCHAR(40)  NOT NULL,
    description              TEXT,

    signed_at                DATE,
    start_at                 DATE,
    end_at                   DATE,

    value_vnd                NUMERIC(20, 0),
    currency                 VARCHAR(10)  NOT NULL DEFAULT 'VND',
    payment_terms_days       INT,
    payment_schedule         VARCHAR(40),

    status                   VARCHAR(20)  NOT NULL DEFAULT 'draft',
    signed_by_vendor         TEXT,
    vendor_signer_title      TEXT,
    signed_by_us             TEXT,
    us_signer_title          TEXT,

    attachment_uri           TEXT,
    renewal_type             VARCHAR(20),
    note                     TEXT,

    created_at               TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at               TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_vendor_contract_no UNIQUE (enterprise_id, contract_no),
    CONSTRAINT chk_vendor_contract_type CHECK (contract_type IN (
        'framework_msa', 'sow_under_msa', 'saas_subscription',
        'api_subscription', 'consulting', 'outsourcing',
        'banking_services', 'one_off_project', 'recurring_po'
    )),
    CONSTRAINT chk_vendor_contract_status CHECK (status IN (
        'draft', 'under_review', 'active', 'expired', 'closed', 'terminated'
    )),
    CONSTRAINT chk_vendor_contract_renewal CHECK (
        renewal_type IS NULL OR renewal_type IN ('manual', 'auto_renew', 'one_off')
    )
);

CREATE INDEX IF NOT EXISTS idx_vendor_contracts_vendor
    ON vendor_contracts (vendor_id, status);
CREATE INDEX IF NOT EXISTS idx_vendor_contracts_status
    ON vendor_contracts (enterprise_id, status);
CREATE INDEX IF NOT EXISTS idx_vendor_contracts_end_date
    ON vendor_contracts (enterprise_id, end_at)
    WHERE status IN ('active', 'under_review');


-- =====================================================================
-- RLS — same pattern as bronze_rows / workflows
-- =====================================================================

ALTER TABLE customers          ENABLE ROW LEVEL SECURITY;
ALTER TABLE vendors            ENABLE ROW LEVEL SECURITY;
ALTER TABLE customer_contracts ENABLE ROW LEVEL SECURITY;
ALTER TABLE vendor_contracts   ENABLE ROW LEVEL SECURITY;

ALTER TABLE customers          FORCE ROW LEVEL SECURITY;
ALTER TABLE vendors            FORCE ROW LEVEL SECURITY;
ALTER TABLE customer_contracts FORCE ROW LEVEL SECURITY;
ALTER TABLE vendor_contracts   FORCE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies
                   WHERE tablename = 'customers' AND policyname = 'tenant_customers') THEN
        CREATE POLICY tenant_customers ON customers
            USING (enterprise_id = current_setting('app.current_enterprise_id', TRUE)::UUID);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies
                   WHERE tablename = 'vendors' AND policyname = 'tenant_vendors') THEN
        CREATE POLICY tenant_vendors ON vendors
            USING (enterprise_id = current_setting('app.current_enterprise_id', TRUE)::UUID);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies
                   WHERE tablename = 'customer_contracts' AND policyname = 'tenant_customer_contracts') THEN
        CREATE POLICY tenant_customer_contracts ON customer_contracts
            USING (enterprise_id = current_setting('app.current_enterprise_id', TRUE)::UUID);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies
                   WHERE tablename = 'vendor_contracts' AND policyname = 'tenant_vendor_contracts') THEN
        CREATE POLICY tenant_vendor_contracts ON vendor_contracts
            USING (enterprise_id = current_setting('app.current_enterprise_id', TRUE)::UUID);
    END IF;
END $$;


-- =====================================================================
-- Documentation
-- =====================================================================

COMMENT ON TABLE customers IS
    'P15-S11 — Customers (KH-) Kaori serves. Rich profile per anh 2026-05-16. Seed from data/sample/customers-profile.csv via mig 063.';
COMMENT ON TABLE vendors IS
    'P15-S11 — Vendors (NCC-) Kaori uses. Same profile shape as customers, different type vocab. Seed via mig 063.';
COMMENT ON TABLE customer_contracts IS
    'P15-S11 — Contracts between Kaori and customers. Parent MSA + child SOWs supported via contract_type discriminator.';
COMMENT ON TABLE vendor_contracts IS
    'P15-S11 — Contracts between Kaori and vendors. Parent MSA + child SOWs supported (e.g., FPT MSA-2018-001 + SOW-2026-007).';
