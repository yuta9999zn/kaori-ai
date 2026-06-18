-- =====================================================================
-- 124_contracts.sql — Tier-3 Phase 3 (ADR-0037): business contracts + e-sign
--
-- A GENERIC contract entity produced by a workflow run (HĐ tín dụng, HĐ dịch
-- vụ…), DISTINCT from customer_contracts (062 = Kaori's own sales). Multi-party
-- signing reuses the Phase-2 chain semantics (sign_order = sequential vs
-- parallel; sign_mode all/threshold). Signatures are append-only (K-2) carrying
-- a doc SHA-256 for non-repudiation. v1 e-sign = internal click; external
-- providers (VNPT/DocuSign) land later via the `method` field + an adapter.
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS contracts (
    contract_id      UUID          PRIMARY KEY DEFAULT gen_uuid_v7(),
    enterprise_id    UUID          NOT NULL,
    department_id    UUID          NOT NULL,
    workflow_run_id  UUID,                               -- source run (nullable: ad-hoc)
    contract_no      VARCHAR(40)   NOT NULL,             -- HD-YYYY-NNN (app-generated)
    title            VARCHAR(240)  NOT NULL,
    contract_type    VARCHAR(60),
    status           VARCHAR(16)   NOT NULL DEFAULT 'nhap',
    value_vnd        NUMERIC(20,0),                      -- K-9 money precision
    currency         VARCHAR(8)    NOT NULL DEFAULT 'VND',
    effective_at     TIMESTAMPTZ,
    expires_at       TIMESTAMPTZ,
    template_file_id UUID          REFERENCES bronze_files(file_id) ON DELETE SET NULL,
    signed_file_id   UUID          REFERENCES bronze_files(file_id) ON DELETE SET NULL,
    renewal_type     VARCHAR(16)   NOT NULL DEFAULT 'manual',
    sign_mode        VARCHAR(16)   NOT NULL DEFAULT 'all',   -- all | threshold
    required_signatures INTEGER,                             -- for threshold mode
    created_by       UUID,
    created_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_contract_status CHECK (status IN
        ('nhap','cho_ky','hieu_luc','het_han','thanh_ly','tu_choi')),
    CONSTRAINT chk_contract_signmode CHECK (sign_mode IN ('all','threshold')),
    CONSTRAINT chk_contract_renewal CHECK (renewal_type IN ('manual','auto_renew','one_off')),
    CONSTRAINT uq_contract_no UNIQUE (enterprise_id, contract_no)
);

CREATE TABLE IF NOT EXISTS contract_parties (
    party_id        UUID         PRIMARY KEY DEFAULT gen_uuid_v7(),
    contract_id     UUID         NOT NULL REFERENCES contracts(contract_id) ON DELETE CASCADE,
    enterprise_id   UUID         NOT NULL,
    party_role      VARCHAR(80)  NOT NULL,               -- "Bên A", "Bên B", role label
    internal_user_id UUID,                               -- internal signer (NULL = external)
    external_name   VARCHAR(200),
    external_email  VARCHAR(200),
    sign_order      INTEGER      NOT NULL DEFAULT 1,     -- same order = parallel; ascending = sequential
    has_signed      BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_party_who CHECK (internal_user_id IS NOT NULL OR external_name IS NOT NULL)
);

-- Append-only (K-2 spirit): the proof of who signed. No UPDATE/DELETE granted.
CREATE TABLE IF NOT EXISTS contract_signatures (
    signature_id    UUID         PRIMARY KEY DEFAULT gen_uuid_v7(),
    contract_id     UUID         NOT NULL REFERENCES contracts(contract_id) ON DELETE CASCADE,
    party_id        UUID         NOT NULL REFERENCES contract_parties(party_id) ON DELETE CASCADE,
    enterprise_id   UUID         NOT NULL,
    signed_by_user_id UUID,                              -- internal signer (NULL = external)
    signer_label    VARCHAR(200) NOT NULL,               -- display name of the signer
    signer_ip       VARCHAR(64),
    document_sha256 VARCHAR(64),                         -- doc hash at signing (non-repudiation)
    method          VARCHAR(20)  NOT NULL DEFAULT 'internal_click',
    signed_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_sig_method CHECK (method IN ('internal_click','vnpt','docusign'))
);

CREATE INDEX IF NOT EXISTS idx_contracts_dept     ON contracts(enterprise_id, department_id, status);
CREATE INDEX IF NOT EXISTS idx_contracts_expiry   ON contracts(enterprise_id, expires_at) WHERE status = 'hieu_luc';
CREATE INDEX IF NOT EXISTS idx_contracts_run      ON contracts(workflow_run_id);
CREATE INDEX IF NOT EXISTS idx_contract_parties   ON contract_parties(contract_id, sign_order);
CREATE INDEX IF NOT EXISTS idx_contract_sigs      ON contract_signatures(contract_id);

-- ─── RLS K-1 + ABAC dept (contracts) + grants ────────────────────────
ALTER TABLE contracts           ENABLE ROW LEVEL SECURITY;
ALTER TABLE contract_parties    ENABLE ROW LEVEL SECURITY;
ALTER TABLE contract_signatures ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS isolation_contracts ON contracts;
CREATE POLICY isolation_contracts ON contracts
    USING      (enterprise_id::text = current_setting('app.current_enterprise_id', true))
    WITH CHECK (enterprise_id::text = current_setting('app.current_enterprise_id', true));
DROP POLICY IF EXISTS abac_dept_scope_contracts ON contracts;
CREATE POLICY abac_dept_scope_contracts ON contracts
    USING (
        enterprise_id::text = current_setting('app.current_enterprise_id', true)
        AND (
            current_setting('app.current_department_id', true) = ''
            OR current_setting('app.current_department_id', true) IS NULL
            OR department_id::text = current_setting('app.current_department_id', true)
        )
    );
DROP POLICY IF EXISTS isolation_contract_parties ON contract_parties;
CREATE POLICY isolation_contract_parties ON contract_parties
    USING      (enterprise_id::text = current_setting('app.current_enterprise_id', true))
    WITH CHECK (enterprise_id::text = current_setting('app.current_enterprise_id', true));
DROP POLICY IF EXISTS isolation_contract_signatures ON contract_signatures;
CREATE POLICY isolation_contract_signatures ON contract_signatures
    USING      (enterprise_id::text = current_setting('app.current_enterprise_id', true))
    WITH CHECK (enterprise_id::text = current_setting('app.current_enterprise_id', true));

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kaori_app') THEN
        EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON contracts        TO kaori_app';
        EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON contract_parties TO kaori_app';
        -- Signatures append-only: INSERT + SELECT only (no UPDATE/DELETE), K-2 non-repudiation.
        EXECUTE 'GRANT SELECT, INSERT                  ON contract_signatures TO kaori_app';
    END IF;
END $$;

COMMENT ON TABLE contracts IS
    'ADR-0037 Phase 3 — generic business contract from a workflow run (distinct '
    'from customer_contracts 062). Multi-party signing reuses Phase-2 chain '
    'semantics; signatures append-only for non-repudiation.';

COMMIT;
