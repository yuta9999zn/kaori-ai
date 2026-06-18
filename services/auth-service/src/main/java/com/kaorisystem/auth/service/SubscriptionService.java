package com.kaorisystem.auth.service;

import com.kaorisystem.auth.model.SubscriptionChangeRequest;
import com.kaorisystem.auth.repository.SubscriptionChangeRequestRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.jdbc.core.namedparam.MapSqlParameterSource;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.time.LocalDate;
import java.time.YearMonth;
import java.time.ZoneId;
import java.util.Optional;
import java.util.UUID;

/**
 * F-030 — Enterprise Subscription & Quota.
 *
 * <p>Two endpoints' worth of business logic:
 * <ul>
 *   <li>{@link #getSubscription(UUID)} — composite read across
 *       {@code enterprises → workspaces → subscription_plans} +
 *       {@code enterprise_monthly_billing} for the current month +
 *       any open upgrade request. Adds a linear EOM forecast and the
 *       80%/95% alert flags from F-031 so the FE can render the banner
 *       and the upgrade-suggestion CTA without a second round-trip.</li>
 *   <li>{@link #requestUpgrade(UUID, String, UUID)} — MANAGER-initiated
 *       upgrade intent. Rejects duplicate-pending and same-plan in
 *       service code so the UI shows a clean 409/400 instead of the
 *       raw DB constraint violation.</li>
 * </ul>
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class SubscriptionService {

    private static final ZoneId VN = ZoneId.of("Asia/Ho_Chi_Minh");

    /** Single round-trip: enterprise → workspace plan → plan defaults → emb row. */
    private static final String STATE_SQL = """
        SELECT  e.enterprise_id,
                e.name                                         AS enterprise_name,
                w.plan_code                                    AS current_plan,
                sp.display_name                                AS plan_display_name,
                sp.monthly_quota                               AS plan_quota,
                sp.price_vnd                                   AS plan_price_vnd,
                COALESCE(b.unique_customers, 0)                AS used,
                COALESCE(b.quota, sp.monthly_quota)            AS effective_quota,
                COALESCE(b.overage_count, 0)                   AS overage_units,
                COALESCE(b.alert_80_fired, FALSE)              AS alert_80_fired,
                COALESCE(b.alert_95_fired, FALSE)              AS alert_95_fired,
                b.last_aggregated_at                           AS last_aggregated_at,
                b.billing_month                                AS billing_month
          FROM enterprises e
          JOIN workspaces w           ON w.workspace_id = e.workspace_id
          JOIN subscription_plans sp  ON sp.plan_code   = w.plan_code
          LEFT JOIN enterprise_monthly_billing b
                 ON b.enterprise_id = e.enterprise_id
                AND b.billing_month = :month
         WHERE e.enterprise_id = :eid
        """;

    /** All known plan codes — drives upgrade validation (no string allow-list to drift). */
    private static final String PLAN_EXISTS_SQL =
            "SELECT plan_code FROM subscription_plans WHERE plan_code = :plan";

    private final NamedParameterJdbcTemplate            jdbc;
    private final SubscriptionChangeRequestRepository   changeRequestRepo;

    // =========================================================================
    // GET /enterprises/me/subscription
    // =========================================================================

    @Transactional(readOnly = true)
    public SubscriptionState getSubscription(UUID enterpriseId) {
        LocalDate today        = LocalDate.now(VN);
        LocalDate monthStart   = today.withDayOfMonth(1);
        int       daysInMonth  = YearMonth.from(today).lengthOfMonth();
        int       daysElapsed  = today.getDayOfMonth();
        int       daysRemaining = daysInMonth - daysElapsed;

        SubscriptionState state = jdbc.query(STATE_SQL,
                new MapSqlParameterSource()
                        .addValue("eid",   enterpriseId)
                        .addValue("month", java.sql.Date.valueOf(monthStart)),
                rs -> {
                    if (!rs.next()) return null;
                    int used  = rs.getInt("used");
                    int quota = rs.getInt("effective_quota");
                    int pct   = quota <= 0 ? 0 : (int) Math.round(used * 100.0 / quota);

                    // Linear projection: extrapolate today's run rate to month end.
                    // Tells a MANAGER "you'll hit X by EOM at this pace."
                    int forecastEom = daysElapsed == 0
                            ? used
                            : (int) Math.round(used * (double) daysInMonth / daysElapsed);

                    return new SubscriptionState(
                            (UUID)   rs.getObject("enterprise_id"),
                            rs.getString("enterprise_name"),
                            rs.getString("current_plan"),
                            rs.getString("plan_display_name"),
                            rs.getInt("plan_quota"),
                            rs.getLong("plan_price_vnd"),
                            used,
                            quota,
                            pct,
                            rs.getInt("overage_units"),
                            forecastEom,
                            rs.getBoolean("alert_80_fired"),
                            rs.getBoolean("alert_95_fired"),
                            monthStart.toString(),
                            daysInMonth,
                            daysRemaining,
                            rs.getTimestamp("last_aggregated_at") == null
                                    ? null
                                    : rs.getTimestamp("last_aggregated_at").toInstant(),
                            null  // pendingUpgrade — filled below
                    );
                });

        if (state == null) {
            throw new EnterpriseNotFoundException("Enterprise not found: " + enterpriseId);
        }

        // Layer the open upgrade request on top, if any. The repo finder is
        // backed by the partial UNIQUE index, so this is at most one row.
        Optional<SubscriptionChangeRequest> pending =
                changeRequestRepo.findFirstByEnterpriseIdAndStatusOrderByRequestedAtDesc(
                        enterpriseId, "PENDING");
        return pending.map(p -> state.withPending(
                p.getRequestId(), p.getRequestedPlan(), p.getRequestedAt())
        ).orElse(state);
    }

    // =========================================================================
    // POST /enterprises/me/subscription/upgrade
    // =========================================================================

    @Transactional
    public SubscriptionChangeRequest requestUpgrade(UUID enterpriseId,
                                                     String targetPlan,
                                                     UUID requestedBy,
                                                     String notes) {
        if (targetPlan == null || targetPlan.isBlank()) {
            throw new InvalidPlanException("target_plan is required");
        }
        targetPlan = targetPlan.trim().toUpperCase();

        // Resolve current plan in the same JOIN chain the read uses.
        SubscriptionState state = getSubscription(enterpriseId);
        if (state.currentPlan().equalsIgnoreCase(targetPlan)) {
            throw new InvalidPlanException("target_plan must differ from current plan");
        }

        // Validate target_plan exists in the catalogue (avoid orphaned FK errors).
        Integer planRowsFound = jdbc.queryForObject(
                "SELECT COUNT(*) FROM subscription_plans WHERE plan_code = :plan",
                new MapSqlParameterSource("plan", targetPlan),
                Integer.class);
        if (planRowsFound == null || planRowsFound == 0) {
            throw new InvalidPlanException("Unknown plan_code: " + targetPlan);
        }

        // Duplicate-pending guard — surface a 409 before the DB unique index fires.
        Optional<SubscriptionChangeRequest> existing =
                changeRequestRepo.findFirstByEnterpriseIdAndStatusOrderByRequestedAtDesc(
                        enterpriseId, "PENDING");
        if (existing.isPresent()) {
            throw new PendingRequestExistsException(
                    "An upgrade request to " + existing.get().getRequestedPlan()
                            + " is already PENDING (request_id="
                            + existing.get().getRequestId() + ")");
        }

        SubscriptionChangeRequest req = new SubscriptionChangeRequest();
        req.setEnterpriseId(enterpriseId);
        req.setCurrentPlan(state.currentPlan());
        req.setRequestedPlan(targetPlan);
        req.setRequestedBy(requestedBy);
        req.setNotes(notes);
        try {
            req = changeRequestRepo.save(req);
        } catch (DataIntegrityViolationException e) {
            // Belt-and-braces: race between the read above and the save (two
            // concurrent MANAGER clicks). Convert to the same 409 surface.
            throw new PendingRequestExistsException(
                    "An upgrade request is already PENDING for this enterprise");
        }
        log.info("subscription.upgrade.requested enterprise_id={} from={} to={} request_id={}",
                enterpriseId, state.currentPlan(), targetPlan, req.getRequestId());
        return req;
    }

    // =========================================================================
    // DTOs + exceptions
    // =========================================================================

    public record SubscriptionState(
            UUID    enterpriseId,
            String  enterpriseName,
            String  currentPlan,
            String  planDisplayName,
            int     planQuota,
            long    planPriceVnd,
            int     usageCount,
            int     quota,
            int     usagePct,
            int     overageUnits,
            int     forecastEom,
            boolean alert80Fired,
            boolean alert95Fired,
            String  billingMonth,
            int     daysInBillingMonth,
            int     daysRemaining,
            Instant lastAggregatedAt,
            PendingUpgrade pendingUpgrade
    ) {
        SubscriptionState withPending(UUID requestId, String requestedPlan, Instant requestedAt) {
            return new SubscriptionState(
                    enterpriseId, enterpriseName, currentPlan, planDisplayName,
                    planQuota, planPriceVnd,
                    usageCount, quota, usagePct, overageUnits, forecastEom,
                    alert80Fired, alert95Fired,
                    billingMonth, daysInBillingMonth, daysRemaining, lastAggregatedAt,
                    new PendingUpgrade(requestId, requestedPlan, requestedAt)
            );
        }
    }

    public record PendingUpgrade(UUID requestId, String requestedPlan, Instant requestedAt) {}

    public static class EnterpriseNotFoundException     extends RuntimeException { public EnterpriseNotFoundException(String m){super(m);} }
    public static class InvalidPlanException            extends RuntimeException { public InvalidPlanException(String m){super(m);} }
    public static class PendingRequestExistsException   extends RuntimeException { public PendingRequestExistsException(String m){super(m);} }
}
