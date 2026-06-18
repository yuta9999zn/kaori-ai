package com.kaorisystem.auth.service;

import com.kaorisystem.auth.repository.AlertEventRepository;
import com.kaorisystem.auth.repository.AlertEventRepository.AlertEventRow;
import com.kaorisystem.auth.repository.AlertRuleRepository;
import com.kaorisystem.auth.repository.AlertRuleRepository.AlertRulePatch;
import com.kaorisystem.auth.repository.AlertRuleRepository.AlertRuleRow;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.util.List;
import java.util.Set;
import java.util.UUID;

/**
 * F-037 alert_rules CRUD service — per-tenant business validation +
 * MANAGER-only enforcement is at the controller layer (matches
 * EnterpriseUserService convention).
 *
 * <p>v0 supported metric types / operators / channels are intentionally
 * narrow — see {@link #ALLOWED_METRICS}, {@link #ALLOWED_OPERATORS},
 * {@link #ALLOWED_CHANNELS}. Adding a new metric_type means:
 * <ol>
 *   <li>Extend the CHECK constraint in migration 028 (additive).</li>
 *   <li>Add a producer in {@code BillingAlertService} or wherever the
 *       metric originates.</li>
 *   <li>Add the value to {@link #ALLOWED_METRICS}.</li>
 * </ol>
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class AlertRuleService {

    /** v0 supported metric types — must match the CHECK in migration 028. */
    public static final Set<String> ALLOWED_METRICS = Set.of("billing_quota_pct");

    /** v0 supported operators — must match the CHECK in migration 028. */
    public static final Set<String> ALLOWED_OPERATORS = Set.of("gt", "gte", "lt", "lte", "eq");

    /** v0 supported channels — must match the CHECK in migration 028. */
    public static final Set<String> ALLOWED_CHANNELS = Set.of("email");

    private final AlertRuleRepository ruleRepo;
    private final AlertEventRepository eventRepo;

    // -------------------------------------------------------------------------
    // Public API
    // -------------------------------------------------------------------------

    public AlertRulePage list(UUID enterpriseId, int page, int limit) {
        int safePage = Math.max(1, page);
        int safeLimit = Math.max(1, Math.min(limit, 100));
        int offset = (safePage - 1) * safeLimit;
        long total = ruleRepo.countByEnterprise(enterpriseId);
        List<AlertRuleRow> items = ruleRepo.findByEnterprise(enterpriseId, safeLimit, offset);
        return new AlertRulePage(items, total, safePage, safeLimit);
    }

    public AlertRuleRow getOrThrow(UUID enterpriseId, UUID ruleId) {
        return ruleRepo.findByIdAndEnterprise(ruleId, enterpriseId)
                .orElseThrow(() -> new AlertRuleNotFoundException(
                        "alert rule not found: " + ruleId));
    }

    public AlertRuleRow create(UUID enterpriseId, CreateRequest req) {
        validateName(req.name());
        validateMetric(req.metricType());
        validateOperator(req.operator());
        validateChannel(req.channel());
        validateThreshold(req.thresholdValue());
        validateCooldown(req.cooldownSeconds());
        // target_email is optional — null means "fall back to MANAGER".

        AlertRuleRow row = new AlertRuleRow(
                null,
                enterpriseId,
                req.name().trim(),
                req.description() == null ? null : req.description().trim(),
                req.metricType(),
                req.operator(),
                req.thresholdValue(),
                req.channel(),
                req.targetEmail() == null || req.targetEmail().isBlank() ? null : req.targetEmail().trim(),
                req.cooldownSeconds() == null ? 300 : req.cooldownSeconds(),
                req.isActive() == null ? true : req.isActive(),
                null,
                null);
        UUID ruleId = ruleRepo.insert(row);
        log.info("alert_rule.create enterprise_id={} rule_id={} metric={}",
                enterpriseId, ruleId, req.metricType());
        return ruleRepo.findByIdAndEnterprise(ruleId, enterpriseId)
                .orElseThrow(() -> new IllegalStateException("rule not found after insert: " + ruleId));
    }

    public AlertRuleRow update(UUID enterpriseId, UUID ruleId, UpdateRequest req) {
        // Existence check first — produces a clean 404 instead of "0 rows
        // updated" silently succeeding.
        getOrThrow(enterpriseId, ruleId);

        if (req.isEmpty()) {
            throw new EmptyUpdateException("at least one field must be provided");
        }
        if (req.operator() != null) validateOperator(req.operator());
        if (req.thresholdValue() != null) validateThreshold(req.thresholdValue());
        if (req.cooldownSeconds() != null) validateCooldown(req.cooldownSeconds());
        if (req.name() != null) validateName(req.name());

        int rows = ruleRepo.update(ruleId, enterpriseId,
                new AlertRulePatch(
                        req.name(),
                        req.description(),
                        req.operator(),
                        req.thresholdValue(),
                        req.targetEmail(),
                        req.cooldownSeconds(),
                        req.isActive()));
        if (rows == 0) {
            // Should be unreachable — getOrThrow above caught the 404.
            throw new AlertRuleNotFoundException("alert rule not found: " + ruleId);
        }
        log.info("alert_rule.update enterprise_id={} rule_id={}", enterpriseId, ruleId);
        return ruleRepo.findByIdAndEnterprise(ruleId, enterpriseId)
                .orElseThrow(() -> new IllegalStateException("rule not found after update: " + ruleId));
    }

    public void softDelete(UUID enterpriseId, UUID ruleId) {
        getOrThrow(enterpriseId, ruleId);
        int rows = ruleRepo.softDelete(ruleId, enterpriseId);
        if (rows == 0) {
            throw new AlertRuleNotFoundException("alert rule not found: " + ruleId);
        }
        log.info("alert_rule.soft_delete enterprise_id={} rule_id={}", enterpriseId, ruleId);
    }

    public List<AlertEventRow> recentEvents(UUID enterpriseId, int limit) {
        return eventRepo.findByEnterprise(enterpriseId, limit);
    }

    // -------------------------------------------------------------------------
    // Validation
    // -------------------------------------------------------------------------

    private static void validateName(String name) {
        if (name == null || name.isBlank()) {
            throw new InvalidAlertRuleException("name is required");
        }
        if (name.length() > 120) {
            throw new InvalidAlertRuleException("name must be ≤ 120 characters");
        }
    }

    private static void validateMetric(String metric) {
        if (metric == null || !ALLOWED_METRICS.contains(metric)) {
            throw new InvalidAlertRuleException(
                    "metric_type must be one of " + ALLOWED_METRICS);
        }
    }

    private static void validateOperator(String op) {
        if (op == null || !ALLOWED_OPERATORS.contains(op)) {
            throw new InvalidAlertRuleException(
                    "operator must be one of " + ALLOWED_OPERATORS);
        }
    }

    private static void validateChannel(String channel) {
        if (channel == null || !ALLOWED_CHANNELS.contains(channel)) {
            throw new InvalidAlertRuleException(
                    "channel must be one of " + ALLOWED_CHANNELS);
        }
    }

    private static void validateThreshold(BigDecimal v) {
        if (v == null) {
            throw new InvalidAlertRuleException("threshold_value is required");
        }
        // Percentages stored as 0–100; we don't reject other ranges
        // because future metrics may exceed 100 (e.g., "rows_processed").
        // Just reject obviously wrong negatives for the v0 metric set.
        if (v.signum() < 0) {
            throw new InvalidAlertRuleException("threshold_value must be ≥ 0");
        }
    }

    private static void validateCooldown(Integer secs) {
        if (secs == null) return; // optional, repo defaults to 300
        if (secs < 0) {
            throw new InvalidAlertRuleException("cooldown_seconds must be ≥ 0");
        }
        if (secs > 86400) {
            throw new InvalidAlertRuleException("cooldown_seconds must be ≤ 86400 (24h)");
        }
    }

    // -------------------------------------------------------------------------
    // DTOs
    // -------------------------------------------------------------------------

    public record CreateRequest(
            String     name,
            String     description,
            String     metricType,
            String     operator,
            BigDecimal thresholdValue,
            String     channel,
            String     targetEmail,
            Integer    cooldownSeconds,
            Boolean    isActive
    ) {}

    public record UpdateRequest(
            String     name,
            String     description,
            String     operator,
            BigDecimal thresholdValue,
            String     targetEmail,
            Integer    cooldownSeconds,
            Boolean    isActive
    ) {
        boolean isEmpty() {
            return name == null && description == null && operator == null
                && thresholdValue == null && targetEmail == null
                && cooldownSeconds == null && isActive == null;
        }
    }

    public record AlertRulePage(List<AlertRuleRow> items, long total, int page, int limit) {}

    public static class AlertRuleNotFoundException extends RuntimeException {
        public AlertRuleNotFoundException(String m) { super(m); }
    }
    public static class InvalidAlertRuleException extends RuntimeException {
        public InvalidAlertRuleException(String m) { super(m); }
    }
    public static class EmptyUpdateException extends RuntimeException {
        public EmptyUpdateException(String m) { super(m); }
    }
}
