package com.kaorisystem.auth.controller;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.kaorisystem.auth.repository.RiskItemRepository.RiskItemRow;
import com.kaorisystem.auth.repository.RiskItemRepository.SeverityCount;
import com.kaorisystem.auth.service.RiskItemService;
import com.kaorisystem.auth.service.RiskItemService.CreateRequest;
import com.kaorisystem.auth.service.RiskItemService.EmptyUpdateException;
import com.kaorisystem.auth.service.RiskItemService.InvalidRiskItemException;
import com.kaorisystem.auth.service.RiskItemService.RiskItemNotFoundException;
import com.kaorisystem.auth.service.RiskItemService.RiskItemPage;
import com.kaorisystem.auth.service.RiskItemService.UpdateRequest;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

/**
 * F-039 — Enterprise Risk Register CRUD.
 *
 * <pre>
 *   GET    /api/v1/enterprises/risks?page=&limit=&status=&severity=&category=  any role
 *   GET    /api/v1/enterprises/risks/severity-rollup                 any role (heat map header tile)
 *   GET    /api/v1/enterprises/risks/{riskId}                        any role
 *   POST   /api/v1/enterprises/risks                                 MANAGER only
 *   PATCH  /api/v1/enterprises/risks/{riskId}                        MANAGER only
 *   DELETE /api/v1/enterprises/risks/{riskId}                        MANAGER only (soft delete)
 * </pre>
 *
 * <p>tenant_id from gateway-trusted ``X-Enterprise-ID`` header (K-12).
 * Mutations require MANAGER role from ``X-User-Role`` header (matches
 * EnterpriseUserController + EnterpriseAlertController convention).
 *
 * <p>v0 = manual CRUD only. Auto-detection from data (anomaly /
 * threshold breach) is a v1 follow-up needing an analysis layer.
 */
@RestController
@RequestMapping("/api/v1/enterprises/risks")
@RequiredArgsConstructor
@Slf4j
public class EnterpriseRiskController {

    private final RiskItemService riskService;

    // =========================================================================
    // GET /
    // =========================================================================
    @GetMapping
    public ResponseEntity<?> list(
            @RequestHeader(value = "X-Enterprise-ID", required = false) String enterpriseHeader,
            @RequestParam(value = "page",     required = false, defaultValue = "1")  int page,
            @RequestParam(value = "limit",    required = false, defaultValue = "20") int limit,
            @RequestParam(value = "status",   required = false) String status,
            @RequestParam(value = "severity", required = false) String severity,
            @RequestParam(value = "category", required = false) String category) {

        UUID enterpriseId = parseUuid(enterpriseHeader);
        if (enterpriseId == null) return missingEnterpriseHeader();

        try {
            RiskItemPage p = riskService.list(enterpriseId, status, severity, category, page, limit);
            Map<String, Object> meta = new LinkedHashMap<>();
            meta.put("total", p.total());
            meta.put("page",  p.page());
            meta.put("limit", p.limit());
            return ResponseEntity.ok(Map.of(
                    "data", p.items().stream().map(EnterpriseRiskController::toJson).toList(),
                    "meta", meta
            ));
        } catch (InvalidRiskItemException e) {
            return invalid(e.getMessage());
        }
    }

    // =========================================================================
    // GET /severity-rollup  (heat map header tile)
    // =========================================================================
    @GetMapping("/severity-rollup")
    public ResponseEntity<?> rollup(
            @RequestHeader(value = "X-Enterprise-ID", required = false) String enterpriseHeader) {

        UUID enterpriseId = parseUuid(enterpriseHeader);
        if (enterpriseId == null) return missingEnterpriseHeader();

        // Initialise all 4 buckets with 0 so the FE doesn't have to
        // null-check missing severities. Service returns only the
        // present ones; we backfill the rest.
        Map<String, Long> counts = new LinkedHashMap<>();
        counts.put("critical", 0L);
        counts.put("high",     0L);
        counts.put("medium",   0L);
        counts.put("low",      0L);
        for (SeverityCount sc : riskService.severityRollup(enterpriseId)) {
            counts.put(sc.severity(), sc.count());
        }
        long openTotal = counts.values().stream().mapToLong(Long::longValue).sum();
        return ResponseEntity.ok(Map.of(
                "data", Map.of(
                        "by_severity", counts,
                        "open_total",  openTotal
                )
        ));
    }

    // =========================================================================
    // GET /{riskId}
    // =========================================================================
    @GetMapping("/{riskId}")
    public ResponseEntity<?> getOne(
            @RequestHeader(value = "X-Enterprise-ID", required = false) String enterpriseHeader,
            @PathVariable("riskId") String riskIdStr) {

        UUID enterpriseId = parseUuid(enterpriseHeader);
        if (enterpriseId == null) return missingEnterpriseHeader();

        UUID riskId = parseUuid(riskIdStr);
        if (riskId == null) return invalidUuid("risk_id must be a valid UUID");

        try {
            RiskItemRow row = riskService.getOrThrow(enterpriseId, riskId);
            return ResponseEntity.ok(Map.of("data", toJson(row)));
        } catch (RiskItemNotFoundException e) {
            return notFound(e.getMessage());
        }
    }

    // =========================================================================
    // POST /
    // =========================================================================
    @PostMapping
    public ResponseEntity<?> create(
            @RequestHeader(value = "X-Enterprise-ID", required = false) String enterpriseHeader,
            @RequestHeader(value = "X-User-Role",     required = false) String actorRole,
            @RequestHeader(value = "X-User-ID",       required = false) String actorIdStr,
            @RequestBody CreateRequestBody body) {

        UUID enterpriseId = parseUuid(enterpriseHeader);
        if (enterpriseId == null) return missingEnterpriseHeader();
        if (!"MANAGER".equalsIgnoreCase(actorRole)) return forbiddenManagerOnly();
        if (body == null) return invalid("request body is required");

        UUID actorId = parseUuid(actorIdStr);  // best-effort; null is fine

        try {
            RiskItemRow created = riskService.create(enterpriseId, actorId, new CreateRequest(
                    body.getTitle(),
                    body.getDescription(),
                    body.getCategory(),
                    body.getLikelihood(),
                    body.getImpact(),
                    body.getStatus(),
                    body.getMitigationPlan(),
                    body.getMitigationProgress(),
                    parseUuid(body.getOwnerUserId()),
                    parseDate(body.getDueDate())));
            return ResponseEntity.status(HttpStatus.CREATED)
                    .body(Map.of("data", toJson(created)));
        } catch (InvalidRiskItemException e) {
            return invalid(e.getMessage());
        }
    }

    // =========================================================================
    // PATCH /{riskId}
    // =========================================================================
    @PatchMapping("/{riskId}")
    public ResponseEntity<?> update(
            @RequestHeader(value = "X-Enterprise-ID", required = false) String enterpriseHeader,
            @RequestHeader(value = "X-User-Role",     required = false) String actorRole,
            @PathVariable("riskId") String riskIdStr,
            @RequestBody UpdateRequestBody body) {

        UUID enterpriseId = parseUuid(enterpriseHeader);
        if (enterpriseId == null) return missingEnterpriseHeader();
        if (!"MANAGER".equalsIgnoreCase(actorRole)) return forbiddenManagerOnly();

        UUID riskId = parseUuid(riskIdStr);
        if (riskId == null) return invalidUuid("risk_id must be a valid UUID");
        if (body == null) return invalid("request body is required");

        try {
            RiskItemRow updated = riskService.update(enterpriseId, riskId, new UpdateRequest(
                    body.getTitle(),
                    body.getDescription(),
                    body.getCategory(),
                    body.getLikelihood(),
                    body.getImpact(),
                    body.getStatus(),
                    body.getMitigationPlan(),
                    body.getMitigationProgress(),
                    parseUuid(body.getOwnerUserId()),
                    parseDate(body.getDueDate())));
            return ResponseEntity.ok(Map.of("data", toJson(updated)));
        } catch (RiskItemNotFoundException e) {
            return notFound(e.getMessage());
        } catch (InvalidRiskItemException e) {
            return invalid(e.getMessage());
        } catch (EmptyUpdateException e) {
            return invalid(e.getMessage());
        }
    }

    // =========================================================================
    // DELETE /{riskId}  (soft delete)
    // =========================================================================
    @DeleteMapping("/{riskId}")
    public ResponseEntity<?> softDelete(
            @RequestHeader(value = "X-Enterprise-ID", required = false) String enterpriseHeader,
            @RequestHeader(value = "X-User-Role",     required = false) String actorRole,
            @PathVariable("riskId") String riskIdStr) {

        UUID enterpriseId = parseUuid(enterpriseHeader);
        if (enterpriseId == null) return missingEnterpriseHeader();
        if (!"MANAGER".equalsIgnoreCase(actorRole)) return forbiddenManagerOnly();

        UUID riskId = parseUuid(riskIdStr);
        if (riskId == null) return invalidUuid("risk_id must be a valid UUID");

        try {
            riskService.softDelete(enterpriseId, riskId);
            return ResponseEntity.ok(Map.of("data", Map.of(
                    "risk_id", riskId.toString(),
                    "status",  "deleted"
            )));
        } catch (RiskItemNotFoundException e) {
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

    private static LocalDate parseDate(String s) {
        if (s == null || s.isBlank()) return null;
        try { return LocalDate.parse(s.trim()); }
        catch (Exception e) { return null; }
    }

    private static ResponseEntity<Map<String, Object>> missingEnterpriseHeader() {
        return problem(401, "/docs/errors/missing-enterprise-id",
                "Missing tenant context",
                "X-Enterprise-ID header is required for enterprise endpoints");
    }

    private static ResponseEntity<Map<String, Object>> forbiddenManagerOnly() {
        return problem(403, "/docs/errors/forbidden", "Forbidden",
                "Only MANAGER can manage risk items");
    }

    private static ResponseEntity<Map<String, Object>> invalid(String msg) {
        return problem(400, "/docs/errors/invalid-request", "Invalid request", msg);
    }

    private static ResponseEntity<Map<String, Object>> invalidUuid(String msg) {
        return problem(400, "/docs/errors/invalid-id", "Invalid id", msg);
    }

    private static ResponseEntity<Map<String, Object>> notFound(String msg) {
        return problem(404, "/docs/errors/risk-item-not-found", "Risk item not found", msg);
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

    private static Map<String, Object> toJson(RiskItemRow r) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("risk_id",             r.riskId());
        m.put("title",               r.title());
        m.put("description",         r.description());
        m.put("category",            r.category());
        m.put("likelihood",          r.likelihood());
        m.put("impact",              r.impact());
        m.put("score",               r.score());
        m.put("severity",            r.severity());
        m.put("status",              r.status());
        m.put("mitigation_plan",     r.mitigationPlan());
        m.put("mitigation_progress", r.mitigationProgress());
        m.put("owner_user_id",       r.ownerUserId());
        m.put("due_date",            r.dueDate());
        m.put("source",              r.source());
        m.put("created_by_user",     r.createdByUser());
        m.put("created_at",          r.createdAt());
        m.put("updated_at",          r.updatedAt());
        return m;
    }

    // =========================================================================
    // Request DTOs (Jackson snake_case)
    // =========================================================================

    @Data
    public static class CreateRequestBody {
        private String  title;
        private String  description;
        private String  category;
        private Integer likelihood;
        private Integer impact;
        private String  status;
        @JsonProperty("mitigation_plan")
        private String  mitigationPlan;
        @JsonProperty("mitigation_progress")
        private Integer mitigationProgress;
        @JsonProperty("owner_user_id")
        private String  ownerUserId;
        @JsonProperty("due_date")
        private String  dueDate;
    }

    @Data
    public static class UpdateRequestBody {
        private String  title;
        private String  description;
        private String  category;
        private Integer likelihood;
        private Integer impact;
        private String  status;
        @JsonProperty("mitigation_plan")
        private String  mitigationPlan;
        @JsonProperty("mitigation_progress")
        private Integer mitigationProgress;
        @JsonProperty("owner_user_id")
        private String  ownerUserId;
        @JsonProperty("due_date")
        private String  dueDate;
    }
}
