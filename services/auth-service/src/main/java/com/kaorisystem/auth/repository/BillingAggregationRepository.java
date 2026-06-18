package com.kaorisystem.auth.repository;

import lombok.RequiredArgsConstructor;
import org.springframework.jdbc.core.namedparam.MapSqlParameterSource;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.stereotype.Component;

import java.sql.Date;
import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

/**
 * F-011 read-only aggregation queries against
 * {@code enterprise_monthly_billing} + {@code enterprises} +
 * {@code subscription_plans}, primed by status / plan filters.
 *
 * <p>Plain {@link NamedParameterJdbcTemplate} component instead of a Spring
 * Data {@code Repository}: the projection target ({@link EnterpriseBillingProjection})
 * is a DTO interface, not an {@code @Entity}, and Spring Data's repository
 * proxy refuses to bind a non-entity type. Native SQL is the only thing we
 * need anyway — this hands us full control over the {@code COALESCE} +
 * status-classification CASE blocks without Hibernate getting in the way.
 *
 * <p>Status thresholds (80 / 95) are duplicated here from
 * {@link com.kaorisystem.auth.service.BillingMath} because doing the rollup
 * row-by-row in Java would require pulling every enterprise into memory.
 * Both code paths share the same constants conceptually; the {@code BillingMath}
 * unit tests pin the boundary so a drift would break the test build.
 */
@Component
@RequiredArgsConstructor
public class BillingAggregationRepository {

    /** Same SQL fragment shared by /quota list, /quota count, /export. */
    private static final String STATUS_CASE = """
        CASE
            WHEN COALESCE(b.overage_count, 0) > 0                                                 THEN 'overage'
            WHEN COALESCE(b.quota, sp.monthly_quota) <= 0                                          THEN 'normal'
            WHEN ROUND(COALESCE(b.unique_customers,0)::NUMERIC
                       / NULLIF(COALESCE(b.quota, sp.monthly_quota),0) * 100) >= 95                THEN 'critical'
            WHEN ROUND(COALESCE(b.unique_customers,0)::NUMERIC
                       / NULLIF(COALESCE(b.quota, sp.monthly_quota),0) * 100) >= 80                THEN 'warn'
            ELSE 'normal'
        END
        """;

    private final NamedParameterJdbcTemplate jdbc;

    // -------------------------------------------------------------------------
    // /overview — platform-wide rollup over active enterprises only
    // -------------------------------------------------------------------------

    public OverviewRow findOverview(Date billingMonth) {
        // Sprint 7 PR C — also report MAX(last_aggregated_at) and the count
        // of "stale" enterprises (haven't been re-aggregated in the last
        // 25h, i.e. F-031 cron missed them at least one cycle). Lets the
        // SUPER_ADMIN dashboard surface "cron health" without grepping logs.
        String sql = """
            WITH per_ent AS (
                SELECT
                    e.enterprise_id,
                    COALESCE(b.unique_customers, 0) AS used,
                    COALESCE(b.quota, sp.monthly_quota) AS quota,
                    COALESCE(b.overage_count, 0)    AS overage,
                    sp.price_vnd                    AS base_price,
                    b.last_aggregated_at            AS last_aggregated_at,
                    %s AS status
                FROM enterprises e
                JOIN workspaces w           ON w.workspace_id = e.workspace_id
                JOIN subscription_plans sp  ON sp.plan_code   = w.plan_code
                LEFT JOIN enterprise_monthly_billing b
                       ON b.enterprise_id = e.enterprise_id
                      AND b.billing_month = :month
                WHERE e.status = 'active'
            )
            SELECT
                COUNT(*)                                     AS enterprise_count,
                COUNT(*) FILTER (WHERE status = 'normal')    AS normal_count,
                COUNT(*) FILTER (WHERE status = 'warn')      AS warn_count,
                COUNT(*) FILTER (WHERE status = 'critical')  AS critical_count,
                COUNT(*) FILTER (WHERE status = 'overage')   AS overage_count,
                COALESCE(SUM(used),    0)                    AS total_unique_customers,
                COALESCE(SUM(quota),   0)                    AS total_quota,
                COALESCE(SUM(overage), 0)                    AS total_overage_units,
                COALESCE(SUM(base_price), 0)                 AS total_base_amount_vnd,
                MAX(last_aggregated_at)                      AS last_aggregated_at,
                COUNT(*) FILTER (
                    WHERE last_aggregated_at IS NULL
                       OR last_aggregated_at < NOW() - INTERVAL '25 hours'
                )                                            AS stale_count
            FROM per_ent
            """.formatted(STATUS_CASE);

        MapSqlParameterSource params = new MapSqlParameterSource("month", billingMonth);
        return jdbc.queryForObject(sql, params, (rs, n) -> new OverviewRow(
                rs.getLong("enterprise_count"),
                rs.getLong("normal_count"),
                rs.getLong("warn_count"),
                rs.getLong("critical_count"),
                rs.getLong("overage_count"),
                rs.getLong("total_unique_customers"),
                rs.getLong("total_quota"),
                rs.getLong("total_overage_units"),
                rs.getDouble("total_base_amount_vnd"),
                rs.getTimestamp("last_aggregated_at") == null
                        ? null
                        : rs.getTimestamp("last_aggregated_at").toInstant(),
                rs.getLong("stale_count")
        ));
    }

    // -------------------------------------------------------------------------
    // /enterprises/{id}
    // -------------------------------------------------------------------------

    public Optional<EnterpriseBillingProjection> findOne(UUID enterpriseId, Date billingMonth) {
        String sql = """
            SELECT
                e.enterprise_id, e.name AS enterprise_name, e.workspace_id,
                w.plan_code,
                COALESCE(b.unique_customers, 0)            AS unique_customers,
                COALESCE(b.quota, sp.monthly_quota)        AS quota,
                COALESCE(b.overage_count, 0)               AS overage_units,
                sp.price_vnd                               AS base_price_vnd,
                e.created_at
            FROM enterprises e
            JOIN workspaces w           ON w.workspace_id = e.workspace_id
            JOIN subscription_plans sp  ON sp.plan_code   = w.plan_code
            LEFT JOIN enterprise_monthly_billing b
                   ON b.enterprise_id = e.enterprise_id
                  AND b.billing_month = :month
            WHERE e.enterprise_id = :eid
            """;
        MapSqlParameterSource params = new MapSqlParameterSource()
                .addValue("eid", enterpriseId)
                .addValue("month", billingMonth);
        List<EnterpriseBillingProjection> rows =
                jdbc.query(sql, params, BillingAggregationRepository::mapRow);
        return rows.isEmpty() ? Optional.empty() : Optional.of(rows.get(0));
    }

    // -------------------------------------------------------------------------
    // /quota — paginated, filterable list
    // -------------------------------------------------------------------------

    public List<EnterpriseBillingProjection> findPage(
            Date billingMonth, String planCode, String status,
            Instant cursorTs, UUID cursorId, int limit) {

        // Postgres requires explicit casts for parameters that may be null
        // and only appear inside IS NULL checks — otherwise it reports
        // "could not determine data type of parameter $N".
        String sql = """
            SELECT
                e.enterprise_id, e.name AS enterprise_name, e.workspace_id,
                w.plan_code,
                COALESCE(b.unique_customers, 0)            AS unique_customers,
                COALESCE(b.quota, sp.monthly_quota)        AS quota,
                COALESCE(b.overage_count, 0)               AS overage_units,
                sp.price_vnd                               AS base_price_vnd,
                e.created_at
            FROM enterprises e
            JOIN workspaces w           ON w.workspace_id = e.workspace_id
            JOIN subscription_plans sp  ON sp.plan_code   = w.plan_code
            LEFT JOIN enterprise_monthly_billing b
                   ON b.enterprise_id = e.enterprise_id
                  AND b.billing_month = :month
            WHERE (CAST(:plan AS TEXT) IS NULL OR w.plan_code = CAST(:plan AS TEXT))
              AND (CAST(:status AS TEXT) IS NULL OR (%s) = CAST(:status AS TEXT))
              AND (
                  CAST(:cursorTs AS TIMESTAMPTZ) IS NULL
                  OR (e.created_at, e.enterprise_id)
                       < (CAST(:cursorTs AS TIMESTAMPTZ), CAST(:cursorId AS UUID))
              )
            ORDER BY e.created_at DESC, e.enterprise_id DESC
            LIMIT :lim
            """.formatted(STATUS_CASE);

        MapSqlParameterSource params = new MapSqlParameterSource()
                .addValue("month",    billingMonth)
                .addValue("plan",     planCode)
                .addValue("status",   status)
                .addValue("cursorTs", cursorTs == null ? null : java.sql.Timestamp.from(cursorTs))
                .addValue("cursorId", cursorId == null ? null : cursorId.toString())
                .addValue("lim",      limit);
        return jdbc.query(sql, params, BillingAggregationRepository::mapRow);
    }

    public long countMatching(Date billingMonth, String planCode, String status) {
        String sql = """
            SELECT COUNT(*)
            FROM enterprises e
            JOIN workspaces w           ON w.workspace_id = e.workspace_id
            JOIN subscription_plans sp  ON sp.plan_code   = w.plan_code
            LEFT JOIN enterprise_monthly_billing b
                   ON b.enterprise_id = e.enterprise_id
                  AND b.billing_month = :month
            WHERE (CAST(:plan AS TEXT) IS NULL OR w.plan_code = CAST(:plan AS TEXT))
              AND (CAST(:status AS TEXT) IS NULL OR (%s) = CAST(:status AS TEXT))
            """.formatted(STATUS_CASE);
        MapSqlParameterSource params = new MapSqlParameterSource()
                .addValue("month",  billingMonth)
                .addValue("plan",   planCode)
                .addValue("status", status);
        Long c = jdbc.queryForObject(sql, params, Long.class);
        return c == null ? 0L : c;
    }

    // -------------------------------------------------------------------------
    // Row mapper — produces the EnterpriseBillingProjection interface impl
    // (anonymous record-style instance keeps callers stable even if the
    // projection later moves back to a Spring Data interface).
    // -------------------------------------------------------------------------

    private static EnterpriseBillingProjection mapRow(java.sql.ResultSet rs, int rowNum) throws java.sql.SQLException {
        UUID    eid       = rs.getObject("enterprise_id", UUID.class);
        String  ename     = rs.getString("enterprise_name");
        UUID    wid       = rs.getObject("workspace_id", UUID.class);
        String  plan      = rs.getString("plan_code");
        Integer used      = rs.getInt("unique_customers");        // COALESCE(...,0) so never null
        Integer quota     = rs.getInt("quota");
        Integer overage   = rs.getInt("overage_units");
        // price_vnd is NUMERIC(14,4) — JDBC returns BigDecimal, not Double.
        Double  price     = rs.getDouble("base_price_vnd");
        Instant created   = rs.getTimestamp("created_at").toInstant();

        return new EnterpriseBillingProjection() {
            @Override public UUID    getEnterpriseId()    { return eid; }
            @Override public String  getEnterpriseName()  { return ename; }
            @Override public UUID    getWorkspaceId()     { return wid; }
            @Override public String  getPlanCode()        { return plan; }
            @Override public Integer getUniqueCustomers() { return used; }
            @Override public Integer getQuota()           { return quota; }
            @Override public Integer getOverageUnits()    { return overage; }
            @Override public Double  getBasePriceVnd()    { return price; }
            @Override public Instant getCreatedAt()       { return created; }
        };
    }

    /** Row record returned by {@link #findOverview}. Sprint 7 PR C added
     * {@code lastAggregatedAt} (latest cron tick across active enterprises)
     * and {@code staleCount} (enterprises whose last aggregation is null
     * or > 25h ago — F-031 cron likely missed them). */
    public record OverviewRow(
            long   enterpriseCount,
            long   normalCount,
            long   warnCount,
            long   criticalCount,
            long   overageCount,
            long   totalUniqueCustomers,
            long   totalQuota,
            long   totalOverageUnits,
            double totalBaseAmountVnd,
            java.time.Instant lastAggregatedAt,
            long   staleCount
    ) {}
}
