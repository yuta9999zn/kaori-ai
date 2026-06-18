package com.kaorisystem.auth.controller;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.kaorisystem.auth.model.SubscriptionChangeRequest;
import com.kaorisystem.auth.service.SubscriptionService;
import com.kaorisystem.auth.service.SubscriptionService.EnterpriseNotFoundException;
import com.kaorisystem.auth.service.SubscriptionService.InvalidPlanException;
import com.kaorisystem.auth.service.SubscriptionService.PendingRequestExistsException;
import com.kaorisystem.auth.service.SubscriptionService.SubscriptionState;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

/**
 * F-030 — Enterprise Subscription & Quota.
 *
 * <pre>
 *   GET  /api/v1/enterprises/me/subscription           any enterprise role
 *   POST /api/v1/enterprises/me/subscription/upgrade   MANAGER only
 * </pre>
 *
 * <p>Tenant comes from the gateway-trusted {@code X-Enterprise-ID} header
 * (K-12). Same plural-/me/ shape as F-016 settings + F-015 users — keeps
 * the API surface consistent for the FE.
 *
 * <p>Upgrade endpoint is mounted under the same prefix instead of the
 * PLAN's {@code /api/v1/billing/upgrade} so we don't have to add a new
 * gateway route — {@code /api/v1/enterprises/**} already routes to
 * auth-service, while {@code /api/v1/billing/**} is owned by the
 * orchestrator dashboard route group.
 */
@RestController
@RequestMapping("/api/v1/enterprises/me/subscription")
@RequiredArgsConstructor
@Slf4j
public class EnterpriseSubscriptionController {

    private final SubscriptionService subscriptionService;

    // =========================================================================
    // GET — full subscription state
    // =========================================================================

    @GetMapping
    public ResponseEntity<?> get(
            @RequestHeader(value = "X-Enterprise-ID", required = false) String enterpriseHeader) {

        UUID enterpriseId = parseUuid(enterpriseHeader);
        if (enterpriseId == null) return missingEnterpriseHeader();

        try {
            SubscriptionState s = subscriptionService.getSubscription(enterpriseId);
            return ResponseEntity.ok(Map.of("data", toJson(s)));
        } catch (EnterpriseNotFoundException e) {
            return problem(404, "/docs/errors/enterprise-not-found",
                    "Enterprise not found", e.getMessage());
        }
    }

    // =========================================================================
    // POST /upgrade — MANAGER initiates an upgrade request
    // =========================================================================

    @PostMapping("/upgrade")
    public ResponseEntity<?> upgrade(
            @RequestHeader(value = "X-Enterprise-ID", required = false) String enterpriseHeader,
            @RequestHeader(value = "X-User-ID",       required = false) String userIdHeader,
            @RequestHeader(value = "X-User-Role",     required = false) String role,
            @Valid @RequestBody UpgradeRequest body) {

        UUID enterpriseId = parseUuid(enterpriseHeader);
        if (enterpriseId == null) return missingEnterpriseHeader();
        if (!"MANAGER".equalsIgnoreCase(role)) {
            return problem(403, "/docs/errors/forbidden",
                    "Forbidden",
                    "Only MANAGER can request an upgrade");
        }
        UUID requestedBy = parseUuid(userIdHeader);  // null OK — column is nullable

        try {
            SubscriptionChangeRequest req = subscriptionService.requestUpgrade(
                    enterpriseId, body.getTargetPlan(), requestedBy, body.getNotes());
            return ResponseEntity.status(HttpStatus.CREATED)
                    .body(Map.of("data", toRequestJson(req)));
        } catch (EnterpriseNotFoundException e) {
            return problem(404, "/docs/errors/enterprise-not-found",
                    "Enterprise not found", e.getMessage());
        } catch (InvalidPlanException e) {
            return problem(400, "/docs/errors/invalid-plan",
                    "Invalid plan", e.getMessage());
        } catch (PendingRequestExistsException e) {
            return problem(409, "/docs/errors/upgrade-pending",
                    "Upgrade already pending", e.getMessage());
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

    private static Map<String, Object> toJson(SubscriptionState s) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("enterprise_id",        s.enterpriseId());
        m.put("enterprise_name",      s.enterpriseName());
        m.put("current_plan",         s.currentPlan());
        m.put("plan_display_name",    s.planDisplayName());
        m.put("plan_quota",           s.planQuota());
        m.put("plan_price_vnd",       s.planPriceVnd());
        m.put("usage_count",          s.usageCount());
        m.put("quota",                s.quota());
        m.put("usage_pct",            s.usagePct());
        m.put("overage_units",        s.overageUnits());
        m.put("forecast_eom",         s.forecastEom());
        m.put("alert_80_fired",       s.alert80Fired());
        m.put("alert_95_fired",       s.alert95Fired());
        m.put("billing_month",        s.billingMonth());
        m.put("days_in_billing_month", s.daysInBillingMonth());
        m.put("days_remaining",       s.daysRemaining());
        m.put("last_aggregated_at",   s.lastAggregatedAt() == null ? null : s.lastAggregatedAt().toString());
        if (s.pendingUpgrade() != null) {
            Map<String, Object> p = new LinkedHashMap<>();
            p.put("request_id",     s.pendingUpgrade().requestId());
            p.put("requested_plan", s.pendingUpgrade().requestedPlan());
            p.put("requested_at",   s.pendingUpgrade().requestedAt().toString());
            m.put("pending_upgrade", p);
        } else {
            m.put("pending_upgrade", null);
        }
        return m;
    }

    private static Map<String, Object> toRequestJson(SubscriptionChangeRequest r) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("request_id",     r.getRequestId());
        m.put("enterprise_id",  r.getEnterpriseId());
        m.put("current_plan",   r.getCurrentPlan());
        m.put("requested_plan", r.getRequestedPlan());
        m.put("status",         r.getStatus());
        m.put("requested_by",   r.getRequestedBy());
        m.put("requested_at",   r.getRequestedAt() == null ? null : r.getRequestedAt().toString());
        m.put("notes",          r.getNotes());
        return m;
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

    // =========================================================================
    // Request DTO
    // =========================================================================

    @Data
    public static class UpgradeRequest {
        @NotBlank
        @JsonProperty("target_plan")
        private String targetPlan;

        private String notes;
    }
}
