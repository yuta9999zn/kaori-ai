package com.kaorisystem.auth.controller;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.kaorisystem.auth.repository.AlertEventRepository.AlertEventRow;
import com.kaorisystem.auth.repository.AlertRuleRepository.AlertRuleRow;
import com.kaorisystem.auth.service.AlertRuleService;
import com.kaorisystem.auth.service.AlertRuleService.AlertRuleNotFoundException;
import com.kaorisystem.auth.service.AlertRuleService.AlertRulePage;
import com.kaorisystem.auth.service.AlertRuleService.CreateRequest;
import com.kaorisystem.auth.service.AlertRuleService.EmptyUpdateException;
import com.kaorisystem.auth.service.AlertRuleService.InvalidAlertRuleException;
import com.kaorisystem.auth.service.AlertRuleService.UpdateRequest;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.math.BigDecimal;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * F-037 — Enterprise Alert Rules CRUD.
 *
 * <pre>
 *   GET    /api/v1/enterprises/alerts              any enterprise role
 *   GET    /api/v1/enterprises/alerts/{ruleId}     any enterprise role
 *   POST   /api/v1/enterprises/alerts              MANAGER only
 *   PATCH  /api/v1/enterprises/alerts/{ruleId}     MANAGER only
 *   DELETE /api/v1/enterprises/alerts/{ruleId}     MANAGER only (soft delete)
 *   GET    /api/v1/enterprises/alerts/events       any enterprise role
 * </pre>
 *
 * <p>tenant_id from gateway-trusted {@code X-Enterprise-ID} header (K-12).
 * Mutations require MANAGER role from {@code X-User-Role} header (matches
 * EnterpriseUserController convention).
 *
 * <p>v0 surface: only the {@code billing_quota_pct} metric is dispatcher-
 * supported. The CRUD accepts the rule but if the metric type isn't
 * wired into a producer the rule will simply never fire (the dispatcher
 * is added per-metric in follow-ups).
 */
@RestController
@RequestMapping("/api/v1/enterprises/alerts")
@RequiredArgsConstructor
@Slf4j
public class EnterpriseAlertController {

    private final AlertRuleService alertService;

    // =========================================================================
    // GET /api/v1/enterprises/alerts
    // =========================================================================
    @GetMapping
    public ResponseEntity<?> list(
            @RequestHeader(value = "X-Enterprise-ID", required = false) String enterpriseHeader,
            @RequestParam(value = "page",  required = false, defaultValue = "1")  int page,
            @RequestParam(value = "limit", required = false, defaultValue = "20") int limit) {

        UUID enterpriseId = parseUuid(enterpriseHeader);
        if (enterpriseId == null) return missingEnterpriseHeader();

        AlertRulePage p = alertService.list(enterpriseId, page, limit);
        Map<String, Object> meta = new LinkedHashMap<>();
        meta.put("total", p.total());
        meta.put("page",  p.page());
        meta.put("limit", p.limit());
        return ResponseEntity.ok(Map.of(
                "data", p.items().stream().map(EnterpriseAlertController::toJson).toList(),
                "meta", meta
        ));
    }

    // =========================================================================
    // GET /api/v1/enterprises/alerts/events  (recent fire history)
    // =========================================================================
    @GetMapping("/events")
    public ResponseEntity<?> events(
            @RequestHeader(value = "X-Enterprise-ID", required = false) String enterpriseHeader,
            @RequestParam(value = "limit", required = false, defaultValue = "50") int limit) {

        UUID enterpriseId = parseUuid(enterpriseHeader);
        if (enterpriseId == null) return missingEnterpriseHeader();

        List<AlertEventRow> events = alertService.recentEvents(enterpriseId, limit);
        return ResponseEntity.ok(Map.of(
                "data", events.stream().map(EnterpriseAlertController::toEventJson).toList()
        ));
    }

    // =========================================================================
    // GET /api/v1/enterprises/alerts/{ruleId}
    // =========================================================================
    @GetMapping("/{ruleId}")
    public ResponseEntity<?> getOne(
            @RequestHeader(value = "X-Enterprise-ID", required = false) String enterpriseHeader,
            @PathVariable("ruleId") String ruleIdStr) {

        UUID enterpriseId = parseUuid(enterpriseHeader);
        if (enterpriseId == null) return missingEnterpriseHeader();

        UUID ruleId = parseUuid(ruleIdStr);
        if (ruleId == null) return invalidUuid("rule_id must be a valid UUID");

        try {
            AlertRuleRow row = alertService.getOrThrow(enterpriseId, ruleId);
            return ResponseEntity.ok(Map.of("data", toJson(row)));
        } catch (AlertRuleNotFoundException e) {
            return notFound(e.getMessage());
        }
    }

    // =========================================================================
    // POST /api/v1/enterprises/alerts
    // =========================================================================
    @PostMapping
    public ResponseEntity<?> create(
            @RequestHeader(value = "X-Enterprise-ID", required = false) String enterpriseHeader,
            @RequestHeader(value = "X-User-Role",     required = false) String actorRole,
            @RequestBody CreateRequestBody body) {

        UUID enterpriseId = parseUuid(enterpriseHeader);
        if (enterpriseId == null) return missingEnterpriseHeader();
        if (!"MANAGER".equalsIgnoreCase(actorRole)) return forbiddenManagerOnly();
        if (body == null) return invalid("request body is required");

        try {
            AlertRuleRow created = alertService.create(enterpriseId, new CreateRequest(
                    body.getName(),
                    body.getDescription(),
                    body.getMetricType(),
                    body.getOperator(),
                    body.getThresholdValue(),
                    body.getChannel() == null ? "email" : body.getChannel(),
                    body.getTargetEmail(),
                    body.getCooldownSeconds(),
                    body.getIsActive()));
            return ResponseEntity.status(HttpStatus.CREATED)
                    .body(Map.of("data", toJson(created)));
        } catch (InvalidAlertRuleException e) {
            return invalid(e.getMessage());
        }
    }

    // =========================================================================
    // PATCH /api/v1/enterprises/alerts/{ruleId}
    // =========================================================================
    @PatchMapping("/{ruleId}")
    public ResponseEntity<?> update(
            @RequestHeader(value = "X-Enterprise-ID", required = false) String enterpriseHeader,
            @RequestHeader(value = "X-User-Role",     required = false) String actorRole,
            @PathVariable("ruleId") String ruleIdStr,
            @RequestBody UpdateRequestBody body) {

        UUID enterpriseId = parseUuid(enterpriseHeader);
        if (enterpriseId == null) return missingEnterpriseHeader();
        if (!"MANAGER".equalsIgnoreCase(actorRole)) return forbiddenManagerOnly();

        UUID ruleId = parseUuid(ruleIdStr);
        if (ruleId == null) return invalidUuid("rule_id must be a valid UUID");
        if (body == null) return invalid("request body is required");

        try {
            AlertRuleRow updated = alertService.update(enterpriseId, ruleId, new UpdateRequest(
                    body.getName(),
                    body.getDescription(),
                    body.getOperator(),
                    body.getThresholdValue(),
                    body.getTargetEmail(),
                    body.getCooldownSeconds(),
                    body.getIsActive()));
            return ResponseEntity.ok(Map.of("data", toJson(updated)));
        } catch (AlertRuleNotFoundException e) {
            return notFound(e.getMessage());
        } catch (InvalidAlertRuleException e) {
            return invalid(e.getMessage());
        } catch (EmptyUpdateException e) {
            return invalid(e.getMessage());
        }
    }

    // =========================================================================
    // DELETE /api/v1/enterprises/alerts/{ruleId}  (soft delete)
    // =========================================================================
    @DeleteMapping("/{ruleId}")
    public ResponseEntity<?> softDelete(
            @RequestHeader(value = "X-Enterprise-ID", required = false) String enterpriseHeader,
            @RequestHeader(value = "X-User-Role",     required = false) String actorRole,
            @PathVariable("ruleId") String ruleIdStr) {

        UUID enterpriseId = parseUuid(enterpriseHeader);
        if (enterpriseId == null) return missingEnterpriseHeader();
        if (!"MANAGER".equalsIgnoreCase(actorRole)) return forbiddenManagerOnly();

        UUID ruleId = parseUuid(ruleIdStr);
        if (ruleId == null) return invalidUuid("rule_id must be a valid UUID");

        try {
            alertService.softDelete(enterpriseId, ruleId);
            return ResponseEntity.ok(Map.of("data", Map.of(
                    "rule_id", ruleId.toString(),
                    "status",  "deleted"
            )));
        } catch (AlertRuleNotFoundException e) {
            return notFound(e.getMessage());
        }
    }

    // =========================================================================
    // Helpers
    // =========================================================================

    private static UUID parseUuid(String s) {
        if (s == null || s.isBlank()) return null;
        try { return UUID.fromString(s.trim()); }
        catch (IllegalArgumentException e) { return null; }
    }

    private static ResponseEntity<Map<String, Object>> missingEnterpriseHeader() {
        return problem(401, "/docs/errors/missing-enterprise-id",
                "Missing tenant context",
                "X-Enterprise-ID header is required for enterprise endpoints");
    }

    private static ResponseEntity<Map<String, Object>> forbiddenManagerOnly() {
        return problem(403, "/docs/errors/forbidden", "Forbidden",
                "Only MANAGER can manage alert rules");
    }

    private static ResponseEntity<Map<String, Object>> invalid(String msg) {
        return problem(400, "/docs/errors/invalid-request", "Invalid request", msg);
    }

    private static ResponseEntity<Map<String, Object>> invalidUuid(String msg) {
        return problem(400, "/docs/errors/invalid-id", "Invalid id", msg);
    }

    private static ResponseEntity<Map<String, Object>> notFound(String msg) {
        return problem(404, "/docs/errors/alert-rule-not-found", "Alert rule not found", msg);
    }

    private static ResponseEntity<Map<String, Object>> problem(
            int status, String type, String title, String detail) {
        return ResponseEntity.status(status)
                .header("Content-Type", "application/problem+json")
                .body(Map.of(
                        "type",   type,
                        "title",  title,
                        "status", status,
                        "detail", detail
                ));
    }

    private static Map<String, Object> toJson(AlertRuleRow r) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("rule_id",          r.ruleId());
        m.put("name",             r.name());
        m.put("description",      r.description());
        m.put("metric_type",      r.metricType());
        m.put("operator",         r.operator());
        m.put("threshold_value",  r.thresholdValue());
        m.put("channel",          r.channel());
        m.put("target_email",     r.targetEmail());
        m.put("cooldown_seconds", r.cooldownSeconds());
        m.put("is_active",        r.isActive());
        m.put("created_at",       r.createdAt());
        m.put("updated_at",       r.updatedAt());
        return m;
    }

    private static Map<String, Object> toEventJson(AlertEventRow e) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("event_id",        e.eventId());
        m.put("rule_id",         e.ruleId());
        m.put("metric_type",     e.metricType());
        m.put("metric_value",    e.metricValue());
        m.put("threshold_value", e.thresholdValue());
        m.put("operator",        e.operator());
        m.put("context",         e.context());
        m.put("outbox_id",       e.outboxId());
        m.put("suppressed",      e.suppressed());
        m.put("fired_at",        e.firedAt());
        return m;
    }

    // =========================================================================
    // Request DTOs (Jackson snake_case)
    // =========================================================================

    @Data
    public static class CreateRequestBody {
        private String name;
        private String description;
        @JsonProperty("metric_type")
        private String metricType;
        private String operator;
        @JsonProperty("threshold_value")
        private BigDecimal thresholdValue;
        private String channel;
        @JsonProperty("target_email")
        private String targetEmail;
        @JsonProperty("cooldown_seconds")
        private Integer cooldownSeconds;
        @JsonProperty("is_active")
        private Boolean isActive;
    }

    @Data
    public static class UpdateRequestBody {
        private String name;
        private String description;
        private String operator;
        @JsonProperty("threshold_value")
        private BigDecimal thresholdValue;
        @JsonProperty("target_email")
        private String targetEmail;
        @JsonProperty("cooldown_seconds")
        private Integer cooldownSeconds;
        @JsonProperty("is_active")
        private Boolean isActive;
    }
}
