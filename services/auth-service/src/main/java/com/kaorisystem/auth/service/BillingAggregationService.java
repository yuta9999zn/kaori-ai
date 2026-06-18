package com.kaorisystem.auth.service;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.jdbc.core.namedparam.MapSqlParameterSource;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

import java.sql.Date;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.List;
import java.util.UUID;

/**
 * F-031 — billing aggregation core.
 *
 * <p>Counts {@code DISTINCT customer_external_id} per active enterprise inside
 * the current billing month, upserts {@code enterprise_monthly_billing}, and
 * sets the 80% / 95% threshold flags idempotently. Designed to be safe to
 * call repeatedly: the second pass on the same month never re-fires an
 * already-set alert flag (per K-11 + the F-030 banner contract).
 *
 * <p>Data path:
 *
 * <pre>
 *   silver_rows            — clean_data->>'customer_external_id' is the
 *                            billing unit (K-11). Counted per
 *                            (enterprise_id, billing_month).
 *   subscription_plans     — quota lookup via enterprises → workspaces.plan_code.
 *   enterprise_monthly_billing — upsert target. ON CONFLICT keeps existing
 *                            alert_*_fired (= TRUE-only flip) but bumps
 *                            unique_customers and last_aggregated_at.
 * </pre>
 *
 * <p><b>Phase 1 explicit non-goals</b>:
 * <ul>
 *   <li>No email dispatch — option (a) per PHASE1_CLOSEOUT_PLAN; F-037 wires that.</li>
 *   <li>No platform_admin_audit_log row — that table's {@code admin_id} column
 *       is NOT NULL FK; the cron is a system actor with no admin row to
 *       attribute. Telemetry instead lives on {@code last_aggregated_at}
 *       (per-enterprise) + structured logs (per cron run).</li>
 * </ul>
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class BillingAggregationService {

    /** Same threshold constants as {@link BillingMath} — pinned to avoid drift. */
    private static final int WARN_PCT     = BillingMath.WARN_PCT;     // 80
    private static final int CRITICAL_PCT = BillingMath.CRITICAL_PCT; // 95

    /**
     * Upsert SQL: insert the (enterprise_id, billing_month) row if missing
     * (DEFAULT FALSE for both alert flags), or refresh unique_customers +
     * last_aggregated_at and TRUE-only flip the alerts if they should be set.
     *
     * <p>The flag updates use {@code COALESCE(... OR ...)} via {@code GREATEST}
     * on the boolean cast to int — Postgres lets you OR booleans directly:
     * {@code alert_80_fired OR :crossed80}. We never flip an already-set flag
     * back to FALSE inside the same billing_month, which is how the FE gets
     * a stable banner.
     */
    private static final String UPSERT_SQL = """
        INSERT INTO enterprise_monthly_billing
            (enterprise_id, billing_month, unique_customers, quota,
             alert_80_fired, alert_95_fired, last_aggregated_at)
        VALUES
            (:eid, :month, :used, :quota,
             :crossed80, :crossed95, :now)
        ON CONFLICT (enterprise_id, billing_month) DO UPDATE SET
            unique_customers   = EXCLUDED.unique_customers,
            quota              = EXCLUDED.quota,
            alert_80_fired     = enterprise_monthly_billing.alert_80_fired OR EXCLUDED.alert_80_fired,
            alert_95_fired     = enterprise_monthly_billing.alert_95_fired OR EXCLUDED.alert_95_fired,
            last_aggregated_at = EXCLUDED.last_aggregated_at,
            updated_at         = NOW()
        """;

    /** Resolve quota for a single tenant via the enterprises → workspaces → subscription_plans chain. */
    private static final String QUOTA_LOOKUP_SQL = """
        SELECT sp.monthly_quota
          FROM enterprises e
          JOIN workspaces w           ON w.workspace_id = e.workspace_id
          JOIN subscription_plans sp  ON sp.plan_code   = w.plan_code
         WHERE e.enterprise_id = :eid
        """;

    /** Count distinct customer_external_id rows in silver for the month. */
    private static final String USAGE_LOOKUP_SQL = """
        SELECT COUNT(DISTINCT clean_data->>'customer_external_id') AS c
          FROM silver_rows
         WHERE enterprise_id = :eid
           AND created_at >= :monthStart
           AND created_at <  :nextMonth
           AND clean_data ? 'customer_external_id'
        """;

    /** All active enterprises — the cron iterates this set. */
    private static final String ACTIVE_ENTERPRISES_SQL = """
        SELECT enterprise_id FROM enterprises WHERE status = 'active'
        """;

    /** F-037 — read prior alert flag state BEFORE the upsert so the
     *  dispatcher can tell "first crossing this month" apart from
     *  "already fired earlier today". Returns 0 rows on the first
     *  aggregation of a fresh month, in which case prior flags = false
     *  by convention. */
    private static final String PRIOR_FLAGS_SQL = """
        SELECT alert_80_fired, alert_95_fired
          FROM enterprise_monthly_billing
         WHERE enterprise_id = :eid AND billing_month = :month
        """;

    private final NamedParameterJdbcTemplate jdbc;
    private final BillingAlertService alertService;

    // =========================================================================
    // Public API
    // =========================================================================

    /**
     * Aggregate billing for one enterprise + month. Returns a result struct
     * the cron + trigger endpoint both surface for telemetry.
     *
     * <p>{@link Propagation#REQUIRES_NEW} so a per-enterprise failure inside
     * {@link #aggregateAll(LocalDate)} never poisons the outer transaction —
     * the cron should keep going for the remaining tenants.
     */
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public AggregateResult aggregate(UUID enterpriseId, LocalDate billingMonth) {
        LocalDate monthStart = billingMonth.withDayOfMonth(1);
        LocalDate nextMonth  = monthStart.plusMonths(1);
        Instant   now        = Instant.now();

        // Migration 024 prep — bind the per-tenant RLS GUC so silver_rows
        // SELECT and enterprise_monthly_billing UPSERT below resolve under
        // a future NOBYPASSRLS cutover. set_config(..., is_local=true) is
        // the SQL-level equivalent of SET LOCAL: scoped to this @Transactional
        // method's transaction, clears on commit/rollback.
        // No-op while kaori_app still has BYPASSRLS=true (the policies sit
        // dormant), but load-bearing the moment the cutover migration ships.
        jdbc.queryForObject(
                "SELECT set_config('app.enterprise_id', :eid, true)",
                new MapSqlParameterSource("eid", enterpriseId.toString()),
                String.class);

        Integer quota = jdbc.queryForObject(
                QUOTA_LOOKUP_SQL,
                new MapSqlParameterSource("eid", enterpriseId),
                Integer.class);
        if (quota == null) {
            // Enterprise exists but no plan? Skip — surface for ops.
            log.warn("billing.aggregate.no_quota enterprise_id={}", enterpriseId);
            return AggregateResult.skipped(enterpriseId, "no_quota");
        }

        Long used = jdbc.queryForObject(
                USAGE_LOOKUP_SQL,
                new MapSqlParameterSource()
                        .addValue("eid",        enterpriseId)
                        .addValue("monthStart", java.sql.Date.valueOf(monthStart))
                        .addValue("nextMonth",  java.sql.Date.valueOf(nextMonth)),
                Long.class);
        long usedLong = used == null ? 0L : used;

        int pct = quota <= 0
                ? 0
                : (int) Math.round(usedLong * 100.0 / quota);
        boolean crossed80 = pct >= WARN_PCT;
        boolean crossed95 = pct >= CRITICAL_PCT;

        // F-037 — capture prior alert flags BEFORE the upsert. When the
        // row doesn't exist yet (first aggregation in a new month),
        // both flags default to false. The dispatcher uses these to
        // tell "first crossing" from "already fired this month", which
        // gates the actual email enqueue.
        boolean[] priorFlags = readPriorFlags(enterpriseId, monthStart);

        jdbc.update(UPSERT_SQL, new MapSqlParameterSource()
                .addValue("eid",       enterpriseId)
                .addValue("month",     java.sql.Date.valueOf(monthStart))
                .addValue("used",      (int) Math.min(usedLong, Integer.MAX_VALUE))
                .addValue("quota",     quota)
                .addValue("crossed80", crossed80)
                .addValue("crossed95", crossed95)
                .addValue("now",       java.sql.Timestamp.from(now))
        );

        log.info("billing.aggregate.ok enterprise_id={} month={} used={} quota={} pct={} a80={} a95={}",
                enterpriseId, monthStart, usedLong, quota, pct, crossed80, crossed95);

        AggregateResult result = new AggregateResult(
                enterpriseId, monthStart, (int) Math.min(usedLong, Integer.MAX_VALUE),
                quota, pct, crossed80, crossed95, false, null);

        // F-037 — best-effort dispatch. The alert service catches all of
        // its own failures (no-recipient, outbox down, etc.) and never
        // throws back into the aggregation transaction.
        try {
            alertService.dispatchOnAggregate(result, priorFlags[0], priorFlags[1]);
        } catch (RuntimeException e) {
            // Defensive — should never reach here per the service's own
            // contract. Log and swallow so the aggregator stays green.
            log.error("billing.alert.dispatch_failed enterprise_id={} error={}",
                    enterpriseId, e.getMessage(), e);
        }

        return result;
    }

    private boolean[] readPriorFlags(UUID enterpriseId, LocalDate monthStart) {
        try {
            Boolean[] flags = jdbc.queryForObject(
                    PRIOR_FLAGS_SQL,
                    new MapSqlParameterSource()
                            .addValue("eid",   enterpriseId)
                            .addValue("month", java.sql.Date.valueOf(monthStart)),
                    (rs, n) -> new Boolean[]{
                            rs.getBoolean("alert_80_fired"),
                            rs.getBoolean("alert_95_fired")
                    });
            if (flags == null) return new boolean[]{false, false};
            return new boolean[]{flags[0] != null && flags[0], flags[1] != null && flags[1]};
        } catch (org.springframework.dao.EmptyResultDataAccessException e) {
            // No row yet — first aggregation for this enterprise/month.
            return new boolean[]{false, false};
        }
    }

    /**
     * Run {@link #aggregate} for every active enterprise. Per-enterprise
     * failures are caught + logged so a single bad tenant doesn't abort the
     * whole pass.
     */
    public BatchResult aggregateAll(LocalDate billingMonth) {
        List<UUID> enterpriseIds = jdbc.getJdbcOperations().query(
                ACTIVE_ENTERPRISES_SQL,
                (rs, n) -> (UUID) rs.getObject("enterprise_id"));

        int ok = 0, failed = 0;
        for (UUID eid : enterpriseIds) {
            try {
                aggregate(eid, billingMonth);
                ok++;
            } catch (Exception e) {
                failed++;
                log.error("billing.aggregate.failed enterprise_id={} error={}",
                        eid, e.getMessage());
            }
        }
        log.info("billing.aggregate_all.done month={} total={} ok={} failed={}",
                billingMonth, enterpriseIds.size(), ok, failed);
        return new BatchResult(billingMonth, enterpriseIds.size(), ok, failed);
    }

    /** Convenience: the cron + trigger both want "current ICT month". */
    public BatchResult aggregateCurrentMonth() {
        LocalDate today = LocalDate.now(ZoneId.of("Asia/Ho_Chi_Minh"));
        return aggregateAll(today.withDayOfMonth(1));
    }

    // =========================================================================
    // DTOs
    // =========================================================================

    public record AggregateResult(
            UUID    enterpriseId,
            LocalDate billingMonth,
            int     uniqueCustomers,
            int     quota,
            int     usagePct,
            boolean alert80Fired,
            boolean alert95Fired,
            boolean skipped,
            String  skipReason
    ) {
        static AggregateResult skipped(UUID eid, String reason) {
            return new AggregateResult(eid, null, 0, 0, 0, false, false, true, reason);
        }
    }

    public record BatchResult(
            LocalDate billingMonth,
            int       enterpriseCount,
            int       successCount,
            int       failureCount
    ) {}
}
