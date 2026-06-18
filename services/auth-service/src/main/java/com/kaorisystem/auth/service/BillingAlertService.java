package com.kaorisystem.auth.service;

import com.kaorisystem.auth.repository.AlertEventRepository;
import com.kaorisystem.auth.repository.AlertEventRepository.AlertEventRow;
import com.kaorisystem.auth.repository.NotificationOutboxRepository;
import com.kaorisystem.auth.repository.UserRepository;
import com.kaorisystem.auth.model.User;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.namedparam.MapSqlParameterSource;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.time.Duration;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * F-037 — billing quota alert dispatcher.
 *
 * <p>Called by {@link BillingAggregationService#aggregate} after the
 * upsert. When a tenant first crosses the 80% or 95% threshold inside
 * the current billing month, this service:
 * <ol>
 *   <li>Resolves a recipient (tenant target_email override → MANAGER
 *       users → log+skip).</li>
 *   <li>Checks alert_events cooldown (default 300s) for the rule.</li>
 *   <li>If past cooldown: enqueues a {@code quota-alert} row in
 *       notification_outbox and inserts a fire alert_events row with
 *       outbox_id.</li>
 *   <li>If within cooldown: inserts a suppressed=true alert_events row
 *       (no outbox enqueue) so support can see "we would have fired but
 *       cooldown was active".</li>
 * </ol>
 *
 * <p>Implicit-default rule_ids: the billing 80% / 95% defaults don't
 * have a row in {@code alert_rules} (would need per-enterprise seed).
 * Instead we use stable sentinel UUIDs constructed below; cooldown
 * lookup scopes by (rule_id, enterprise_id) so two tenants don't share
 * a cooldown window.
 *
 * <p>Best-effort by design: every code path catches and logs rather
 * than throwing. A failed alert dispatch must NEVER abort the billing
 * aggregation transaction (which already committed the canonical
 * unique_customers count). Telemetry lives on {@code alert.dispatch.*}
 * log lines.
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class BillingAlertService {

    /** Stable sentinel for the implicit billing-80 default rule. */
    public static final UUID BILLING_80_RULE_ID =
            UUID.fromString("00000000-0000-0000-0000-000000000080");

    /** Stable sentinel for the implicit billing-95 default rule. */
    public static final UUID BILLING_95_RULE_ID =
            UUID.fromString("00000000-0000-0000-0000-000000000095");

    /** Default cooldown for implicit billing alerts — 1 fire per billing
     *  month would also be acceptable, but 6 hours catches the case
     *  where the cron is run manually mid-day after a quota reset. */
    private static final Duration IMPLICIT_COOLDOWN = Duration.ofHours(6);

    /** quota-alert template name in notification-service models.py. */
    private static final String TEMPLATE = "quota-alert";

    private final AlertEventRepository alertEvents;
    private final NotificationOutboxRepository outbox;
    private final UserRepository userRepo;
    private final NamedParameterJdbcTemplate jdbc;

    @Value("${kaori.app.frontend-base-url:http://localhost:3000}")
    private String frontendBaseUrl;

    /**
     * Dispatch billing alerts for a single enterprise after the
     * aggregator upsert.
     *
     * @param result        the just-computed aggregate result (used for
     *                      pct, used, quota, plan_code, enterprise_name)
     * @param prior80Fired  state of {@code alert_80_fired} BEFORE the
     *                      upsert (true = already fired in this month,
     *                      no need to fire again unless cooldown is over)
     * @param prior95Fired  state of {@code alert_95_fired} BEFORE the upsert
     */
    public void dispatchOnAggregate(
            BillingAggregationService.AggregateResult result,
            boolean prior80Fired,
            boolean prior95Fired) {

        if (result.skipped()) return;

        UUID eid = result.enterpriseId();

        // Lookup metadata once for both potential dispatches.
        EnterpriseMeta meta = lookupMeta(eid);
        if (meta == null) {
            log.warn("alert.dispatch.no_meta enterprise_id={}", eid);
            return;
        }

        // 95% takes precedence over 80% — if the tenant just crossed
        // both in the same tick (e.g., cron skipped a day), fire the
        // more severe one only. The 80% suppression below records a
        // suppressed event for forensics.
        boolean did95 = false;
        if (result.alert95Fired() && shouldFire95(prior95Fired)) {
            did95 = tryFire(eid, meta, result, BILLING_95_RULE_ID, BigDecimal.valueOf(95));
        }
        if (result.alert80Fired() && shouldFire80(prior80Fired) && !did95) {
            tryFire(eid, meta, result, BILLING_80_RULE_ID, BigDecimal.valueOf(80));
        }
    }

    private boolean shouldFire80(boolean prior80Fired) {
        // Fire on first crossing within the month.
        return !prior80Fired;
    }

    private boolean shouldFire95(boolean prior95Fired) {
        return !prior95Fired;
    }

    /**
     * Resolve recipient + cooldown + enqueue. Returns true if the alert
     * was actually dispatched (false = suppressed by cooldown OR no
     * recipient available).
     */
    private boolean tryFire(UUID eid, EnterpriseMeta meta,
                            BillingAggregationService.AggregateResult result,
                            UUID ruleId, BigDecimal threshold) {

        // Cooldown check — implicit defaults use IMPLICIT_COOLDOWN; custom
        // rules will look up their own cooldown_seconds in a follow-up.
        Instant lastFire = alertEvents.latestNonSuppressedFiredAt(ruleId, eid);
        if (lastFire != null
                && Duration.between(lastFire, Instant.now()).compareTo(IMPLICIT_COOLDOWN) < 0) {
            // Suppressed event — record for forensics, no outbox.
            alertEvents.record(suppressedEvent(eid, ruleId, result, threshold, "cooldown"));
            log.info("alert.dispatch.suppressed reason=cooldown enterprise_id={} rule_id={} pct={}",
                    eid, ruleId, result.usagePct());
            return false;
        }

        // Resolve recipient.
        String recipient = resolveRecipient(eid);
        if (recipient == null) {
            alertEvents.record(suppressedEvent(eid, ruleId, result, threshold, "no_recipient"));
            log.warn("alert.dispatch.no_recipient enterprise_id={} rule_id={}", eid, ruleId);
            return false;
        }

        // Build template context.
        Map<String, Object> context = buildContext(meta, result, threshold);

        // Enqueue + record.
        UUID outboxId = outbox.enqueue(eid, TEMPLATE, recipient, context, "alert:" + ruleId);
        AlertEventRow row = new AlertEventRow(
                null, eid, ruleId,
                "billing_quota_pct",
                BigDecimal.valueOf(result.usagePct()),
                threshold,
                "gte",
                context,
                outboxId,
                false,
                null);
        UUID eventId = alertEvents.record(row);

        log.info("alert.dispatch.ok enterprise_id={} rule_id={} pct={} outbox_id={} event_id={}",
                eid, ruleId, result.usagePct(), outboxId, eventId);
        return true;
    }

    private AlertEventRow suppressedEvent(UUID eid, UUID ruleId,
                                          BillingAggregationService.AggregateResult result,
                                          BigDecimal threshold,
                                          String reason) {
        Map<String, Object> ctx = new LinkedHashMap<>();
        ctx.put("usage_pct",       result.usagePct());
        ctx.put("used",            result.uniqueCustomers());
        ctx.put("quota_limit",     result.quota());
        ctx.put("suppress_reason", reason);
        return new AlertEventRow(
                null, eid, ruleId,
                "billing_quota_pct",
                BigDecimal.valueOf(result.usagePct()),
                threshold,
                "gte",
                ctx,
                null,
                true,
                null);
    }

    /**
     * Recipient priority:
     * <ol>
     *   <li>Active MANAGER users (one row per dispatch — the first MANAGER
     *       in created_at order). We pick a single recipient rather than
     *       broadcasting because notification_outbox is one row per send;
     *       broadcasting would multiply outbox rows by team size and
     *       complicate cooldown semantics.</li>
     *   <li>If no MANAGER → null (caller logs + suppresses).</li>
     * </ol>
     *
     * <p>Future: read tenant_settings.notification_email opt-in + a
     * dedicated alerts_email column (deferred). For pilot, MANAGER role
     * is the canonical billing contact.
     */
    private String resolveRecipient(UUID enterpriseId) {
        List<User> managers = userRepo.findByEnterpriseFiltered(
                enterpriseId, "MANAGER", "active", 1, 0);
        if (managers.isEmpty()) return null;
        return managers.get(0).getEmail();
    }

    private Map<String, Object> buildContext(EnterpriseMeta meta,
                                             BillingAggregationService.AggregateResult result,
                                             BigDecimal threshold) {
        Map<String, Object> ctx = new LinkedHashMap<>();
        ctx.put("enterprise_name", meta.enterpriseName());
        ctx.put("usage_pct",       result.usagePct());
        ctx.put("quota_limit",     result.quota());
        ctx.put("used",            result.uniqueCustomers());
        ctx.put("plan",            meta.planCode());
        ctx.put("plan_label",      planLabel(meta.planCode()));
        ctx.put("threshold",       threshold.intValue());
        ctx.put("upgrade_url",     frontendBaseUrl + "/subscription?tab=upgrade");
        return ctx;
    }

    /**
     * Pretty plan name for the email body. Pilot tier set comes from
     * CLAUDE.md §10. Anything unknown falls back to the code itself —
     * the template renders that without crashing.
     */
    static String planLabel(String code) {
        if (code == null) return "—";
        return switch (code.toUpperCase()) {
            case "PILOT"     -> "Pilot";
            case "ENT_BASIC" -> "Enterprise Basic";
            case "ENT_MID"   -> "Enterprise Mid";
            case "ENT_MAX"   -> "Enterprise Max";
            case "ENT_ROI"   -> "Enterprise ROI";
            case "TRIAL"     -> "Trial";
            default          -> code;
        };
    }

    // -------------------------------------------------------------------------
    // Enterprise metadata lookup (name + plan_code) — single query, JDBC
    // -------------------------------------------------------------------------
    private EnterpriseMeta lookupMeta(UUID enterpriseId) {
        String sql = """
            SELECT e.name AS enterprise_name, w.plan_code
              FROM enterprises e
              JOIN workspaces w ON w.workspace_id = e.workspace_id
             WHERE e.enterprise_id = :eid
            """;
        try {
            return jdbc.queryForObject(sql,
                    new MapSqlParameterSource("eid", enterpriseId),
                    (rs, n) -> new EnterpriseMeta(
                            rs.getString("enterprise_name"),
                            rs.getString("plan_code")));
        } catch (org.springframework.dao.EmptyResultDataAccessException e) {
            return null;
        }
    }

    private record EnterpriseMeta(String enterpriseName, String planCode) {}
}
