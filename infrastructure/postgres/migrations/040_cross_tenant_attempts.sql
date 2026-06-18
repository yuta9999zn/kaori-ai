-- 040_cross_tenant_attempts.sql
-- P1-S2 (P1-MTNT-001) — Cross-tenant access attempt monitoring.
--
-- When app code under tenant-A GUC tries to INSERT/UPDATE a row whose
-- enterprise_id is tenant-B, the RLS WITH CHECK policy rejects with
-- error 42501 (insufficient privilege). The exception is caught at the
-- application layer (services/*/shared/db.py acquire_for_tenant wrapper)
-- which writes a row into THIS table, then re-raises.
--
-- Also captures intentional admin escapes: a NOBYPASSRLS connection
-- that flips ``app.is_admin = 'true'`` to read across tenants is
-- legitimate (cross-tenant aggregation, cron jobs); the audit row marks
-- ``intent='admin_bypass'`` so reviewers can spot bugs vs designed paths.
--
-- Append-only by convention. Retention 2 years (matches audit_logs).
-- Read by ops dashboards (Grafana panel + Loki alert).

CREATE TABLE IF NOT EXISTS cross_tenant_attempts (
    id              BIGSERIAL       PRIMARY KEY,
    attempted_at    TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    -- enterprise_id from app.enterprise_id GUC (caller's intent / scope)
    guc_tenant      UUID,
    -- enterprise_id of the row that triggered the rejection
    row_tenant      UUID,

    -- INSERT / UPDATE / DELETE / SELECT (rare — only when app code
    -- explicitly checks)
    operation       VARCHAR(16),
    -- Schema-qualified table name, e.g. 'public.gold_features'
    table_name      TEXT,
    -- Optional primary-key value of the offending row, when known
    pk_value        TEXT,

    -- Why the entry was logged: 'rls_reject' (caught from Postgres
    -- 42501), 'app_check' (proactive caller check), 'admin_bypass'
    -- (legitimate admin scope, flagged for review).
    reason          VARCHAR(32)     NOT NULL DEFAULT 'rls_reject',

    -- Free-form context — exception message, traceback excerpt, request
    -- correlation, etc. Limit storage by truncating to 4 KB at write.
    detail          TEXT,

    -- Inbound request IP if available (X-Forwarded-For chain)
    ip_address      INET
);

CREATE INDEX IF NOT EXISTS idx_cta_attempted_at
    ON cross_tenant_attempts(attempted_at DESC);
CREATE INDEX IF NOT EXISTS idx_cta_guc_tenant
    ON cross_tenant_attempts(guc_tenant);
CREATE INDEX IF NOT EXISTS idx_cta_reason
    ON cross_tenant_attempts(reason);

COMMENT ON TABLE cross_tenant_attempts IS
    'P1-MTNT-001 — audit log of cross-tenant access attempts (RLS rejections + admin bypasses). Append-only.';

-- This table is intentionally NOT subject to RLS — ops + platform
-- admins need to read across all tenants to spot abuse patterns. No
-- enterprise_id column either; the distinction is captured in
-- guc_tenant + row_tenant columns. ALL writes come from the app layer
-- under runtime role kaori_app (NOBYPASSRLS), which has INSERT
-- privilege on this table.

GRANT INSERT, SELECT ON cross_tenant_attempts TO kaori_app;
GRANT USAGE, SELECT ON SEQUENCE cross_tenant_attempts_id_seq TO kaori_app;

-- ---------------------------------------------------------------------------
-- log_rls_attempt() — single insertion point for the audit trail.
--
-- Called from the application layer (services/*/shared/db.py) after a
-- caught asyncpg.exceptions.InsufficientPrivilegeError. Wrapping in a
-- function lets us swap the storage layout (e.g. shard by month) later
-- without touching every caller. SECURITY DEFINER so callers don't
-- need explicit INSERT grant on the table — they just need EXECUTE.
--
-- Truncates `detail` to 4 KB defensively. Stack traces / exception
-- messages can balloon in unexpected ways and we don't want a
-- malformed exception to OOM the audit table.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION log_rls_attempt(
    p_guc_tenant   UUID,
    p_row_tenant   UUID,
    p_operation    VARCHAR,
    p_table_name   TEXT,
    p_pk_value     TEXT,
    p_reason       VARCHAR,
    p_detail       TEXT,
    p_ip_address   INET DEFAULT NULL
) RETURNS BIGINT AS $$
DECLARE
    inserted_id BIGINT;
BEGIN
    INSERT INTO cross_tenant_attempts (
        guc_tenant, row_tenant, operation, table_name,
        pk_value, reason, detail, ip_address
    ) VALUES (
        p_guc_tenant, p_row_tenant, p_operation, p_table_name,
        p_pk_value, p_reason,
        LEFT(COALESCE(p_detail, ''), 4096),
        p_ip_address
    )
    RETURNING id INTO inserted_id;

    RETURN inserted_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

GRANT EXECUTE ON FUNCTION log_rls_attempt(
    UUID, UUID, VARCHAR, TEXT, TEXT, VARCHAR, TEXT, INET
) TO kaori_app;

COMMENT ON FUNCTION log_rls_attempt IS
    'P1-MTNT-001 — application calls this from the InsufficientPrivilegeError handler in shared/db.py to record a cross-tenant attempt. Returns the new audit row id.';
