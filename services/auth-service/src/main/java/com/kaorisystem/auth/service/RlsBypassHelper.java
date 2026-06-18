package com.kaorisystem.auth.service;

import lombok.RequiredArgsConstructor;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

/**
 * Migration 025 cutover helper — set {@code app.is_admin = 'true'} for
 * the current transaction so cross-tenant aggregation queries (platform
 * admin dashboards, billing rollups, workspace billing summary) can read
 * every tenant's rows under {@code NOBYPASSRLS}.
 *
 * <h3>Why this mechanism</h3>
 *
 * Postgres' {@code row_security = off} GUC isn't a bypass — it raises an
 * error on any query that would be affected by an RLS policy. The only
 * legitimate ways to read across tenants are (a) a role with
 * {@code BYPASSRLS} (defeats the cutover) or (b) a permissive RLS
 * policy that evaluates to true for the caller. We use (b): every
 * tenant table has an {@code admin_bypass_*} policy that returns true
 * when {@code app.is_admin = 'true'} is set on the session (see
 * 025_rls_nobypassrls_cutover.sql). Postgres applies multiple permissive
 * policies as OR, so a row is visible when EITHER
 * {@code enterprise_id = app.enterprise_id} (per-tenant) OR
 * {@code app.is_admin = 'true'} (cross-tenant aggregation).
 *
 * <h3>Caller contract</h3>
 *
 * Must be called from inside a {@code @Transactional} method. The
 * {@code SET LOCAL} expires automatically at commit / rollback time, so
 * the connection returns to the pool with no lingering session state.
 * Calling outside a transaction is a programmer error — Spring will
 * throw a runtime exception about no-active-transaction.
 *
 * <h3>Use sparingly</h3>
 *
 * Only on documented cross-tenant aggregation paths. The PR #7
 * {@code scripts/check-tenant-filter.py} lint allow-list pins which
 * files are permitted to skip {@code WHERE enterprise_id} filters; the
 * same files are the ones that should call this method.
 */
@Component
@RequiredArgsConstructor
public class RlsBypassHelper {

    private final JdbcTemplate jdbc;

    /**
     * Authorise the current transaction to bypass RLS via the
     * {@code admin_bypass_*} policies installed in migration 025.
     * Tx-LOCAL — expires on commit / rollback.
     */
    public void disableForTx() {
        jdbc.execute("SET LOCAL app.is_admin = 'true'");
    }
}
