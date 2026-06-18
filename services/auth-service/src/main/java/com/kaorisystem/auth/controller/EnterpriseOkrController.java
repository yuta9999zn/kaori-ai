package com.kaorisystem.auth.controller;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.kaorisystem.auth.repository.OkrRepository.KeyResultRow;
import com.kaorisystem.auth.repository.OkrRepository.ObjectiveRow;
import com.kaorisystem.auth.service.OkrService;
import com.kaorisystem.auth.service.OkrService.CreateRequest;
import com.kaorisystem.auth.service.OkrService.EmptyUpdateException;
import com.kaorisystem.auth.service.OkrService.InvalidOkrException;
import com.kaorisystem.auth.service.OkrService.KrUpsert;
import com.kaorisystem.auth.service.OkrService.ObjectiveNotFoundException;
import com.kaorisystem.auth.service.OkrService.ObjectivePage;
import com.kaorisystem.auth.service.OkrService.ObjectiveWithKrs;
import com.kaorisystem.auth.service.OkrService.StatusRollup;
import com.kaorisystem.auth.service.OkrService.UpdateRequest;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.math.BigDecimal;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * F-040 — Enterprise OKR (Strategy Builder) CRUD.
 *
 * <pre>
 *   GET    /api/v1/enterprises/strategy/summary?quarter=         any role
 *   GET    /api/v1/enterprises/strategy/okr?quarter=&page=&limit=  any role
 *   GET    /api/v1/enterprises/strategy/okr/{objectiveId}        any role
 *   POST   /api/v1/enterprises/strategy/okr                      MANAGER
 *   PATCH  /api/v1/enterprises/strategy/okr/{objectiveId}        MANAGER
 *   PATCH  /api/v1/enterprises/strategy/okr/{objectiveId}/kr/{krId}/progress  MANAGER
 *   DELETE /api/v1/enterprises/strategy/okr/{objectiveId}        MANAGER (soft)
 * </pre>
 *
 * <p>Same MANAGER role gate + RFC 7807 error envelope as F-037 alerts
 * + F-039 risks. Tenant from gateway-trusted ``X-Enterprise-ID``.
 */
@RestController
@RequestMapping("/api/v1/enterprises/strategy")
@RequiredArgsConstructor
@Slf4j
public class EnterpriseOkrController {

    private final OkrService okrService;

    // =========================================================================
    // GET /summary
    // =========================================================================
    @GetMapping("/summary")
    public ResponseEntity<?> summary(
            @RequestHeader(value = "X-Enterprise-ID", required = false) String enterpriseHeader,
            @RequestParam(value = "quarter", required = false) String quarter) {

        UUID enterpriseId = parseUuid(enterpriseHeader);
        if (enterpriseId == null) return missingEnterpriseHeader();

        try {
            StatusRollup r = okrService.rollup(enterpriseId, quarter);
            return ResponseEntity.ok(Map.of(
                    "data", Map.of(
                            "by_status", r.byStatus(),
                            "total",     r.total(),
                            "quarter",   r.quarter() == null ? "" : r.quarter()
                    )
            ));
        } catch (InvalidOkrException e) {
            return invalid(e.getMessage());
        }
    }

    // =========================================================================
    // GET /okr
    // =========================================================================
    @GetMapping("/okr")
    public ResponseEntity<?> list(
            @RequestHeader(value = "X-Enterprise-ID", required = false) String enterpriseHeader,
            @RequestParam(value = "quarter", required = false)                String quarter,
            @RequestParam(value = "page",    required = false, defaultValue = "1")  int page,
            @RequestParam(value = "limit",   required = false, defaultValue = "20") int limit) {

        UUID enterpriseId = parseUuid(enterpriseHeader);
        if (enterpriseId == null) return missingEnterpriseHeader();

        try {
            ObjectivePage p = okrService.list(enterpriseId, quarter, page, limit);
            Map<String, Object> meta = new LinkedHashMap<>();
            meta.put("total", p.total());
            meta.put("page",  p.page());
            meta.put("limit", p.limit());
            return ResponseEntity.ok(Map.of(
                    "data", p.items().stream().map(EnterpriseOkrController::toJson).toList(),
                    "meta", meta
            ));
        } catch (InvalidOkrException e) {
            return invalid(e.getMessage());
        }
    }

    // =========================================================================
    // GET /okr/{objectiveId}
    // =========================================================================
    @GetMapping("/okr/{objectiveId}")
    public ResponseEntity<?> getOne(
            @RequestHeader(value = "X-Enterprise-ID", required = false) String enterpriseHeader,
            @PathVariable("objectiveId") String objectiveIdStr) {

        UUID enterpriseId = parseUuid(enterpriseHeader);
        if (enterpriseId == null) return missingEnterpriseHeader();

        UUID objectiveId = parseUuid(objectiveIdStr);
        if (objectiveId == null) return invalidUuid("objective_id must be a valid UUID");

        try {
            ObjectiveWithKrs o = okrService.getOrThrow(enterpriseId, objectiveId);
            return ResponseEntity.ok(Map.of("data", toJson(o)));
        } catch (ObjectiveNotFoundException e) {
            return notFound(e.getMessage());
        }
    }

    // =========================================================================
    // POST /okr
    // =========================================================================
    @PostMapping("/okr")
    public ResponseEntity<?> create(
            @RequestHeader(value = "X-Enterprise-ID", required = false) String enterpriseHeader,
            @RequestHeader(value = "X-User-Role",     required = false) String actorRole,
            @RequestHeader(value = "X-User-ID",       required = false) String actorIdStr,
            @RequestBody CreateRequestBody body) {

        UUID enterpriseId = parseUuid(enterpriseHeader);
        if (enterpriseId == null) return missingEnterpriseHeader();
        if (!"MANAGER".equalsIgnoreCase(actorRole)) return forbiddenManagerOnly();
        if (body == null) return invalid("request body is required");

        UUID actorId = parseUuid(actorIdStr);

        try {
            ObjectiveWithKrs created = okrService.create(enterpriseId, actorId, new CreateRequest(
                    body.getQuarter(),
                    body.getTitle(),
                    parseUuid(body.getOwnerUserId()),
                    body.getKeyResults() == null ? List.of()
                            : body.getKeyResults().stream().map(KrBody::toUpsert).toList()));
            return ResponseEntity.status(HttpStatus.CREATED)
                    .body(Map.of("data", toJson(created)));
        } catch (InvalidOkrException e) {
            return invalid(e.getMessage());
        }
    }

    // =========================================================================
    // PATCH /okr/{objectiveId}
    // =========================================================================
    @PatchMapping("/okr/{objectiveId}")
    public ResponseEntity<?> update(
            @RequestHeader(value = "X-Enterprise-ID", required = false) String enterpriseHeader,
            @RequestHeader(value = "X-User-Role",     required = false) String actorRole,
            @PathVariable("objectiveId") String objectiveIdStr,
            @RequestBody UpdateRequestBody body) {

        UUID enterpriseId = parseUuid(enterpriseHeader);
        if (enterpriseId == null) return missingEnterpriseHeader();
        if (!"MANAGER".equalsIgnoreCase(actorRole)) return forbiddenManagerOnly();

        UUID objectiveId = parseUuid(objectiveIdStr);
        if (objectiveId == null) return invalidUuid("objective_id must be a valid UUID");
        if (body == null) return invalid("request body is required");

        try {
            ObjectiveWithKrs updated = okrService.update(enterpriseId, objectiveId, new UpdateRequest(
                    body.getQuarter(),
                    body.getTitle(),
                    parseUuid(body.getOwnerUserId()),
                    body.getStatus(),
                    body.getKeyResults() == null ? null
                            : body.getKeyResults().stream().map(KrBody::toUpsert).toList()));
            return ResponseEntity.ok(Map.of("data", toJson(updated)));
        } catch (ObjectiveNotFoundException e) {
            return notFound(e.getMessage());
        } catch (InvalidOkrException e) {
            return invalid(e.getMessage());
        } catch (EmptyUpdateException e) {
            return invalid(e.getMessage());
        }
    }

    // =========================================================================
    // PATCH /okr/{objectiveId}/kr/{krId}/progress
    // =========================================================================
    @PatchMapping("/okr/{objectiveId}/kr/{krId}/progress")
    public ResponseEntity<?> updateKrProgress(
            @RequestHeader(value = "X-Enterprise-ID", required = false) String enterpriseHeader,
            @RequestHeader(value = "X-User-Role",     required = false) String actorRole,
            @PathVariable("objectiveId") String objectiveIdStr,
            @PathVariable("krId")        String krIdStr,
            @RequestBody KrProgressBody body) {

        UUID enterpriseId = parseUuid(enterpriseHeader);
        if (enterpriseId == null) return missingEnterpriseHeader();
        if (!"MANAGER".equalsIgnoreCase(actorRole)) return forbiddenManagerOnly();

        UUID objectiveId = parseUuid(objectiveIdStr);
        if (objectiveId == null) return invalidUuid("objective_id must be a valid UUID");
        UUID krId = parseUuid(krIdStr);
        if (krId == null) return invalidUuid("kr_id must be a valid UUID");
        if (body == null || body.getCurrentValue() == null) {
            return invalid("current_value is required");
        }

        try {
            ObjectiveWithKrs updated = okrService.updateKeyResultProgress(
                    enterpriseId, objectiveId, krId, body.getCurrentValue());
            return ResponseEntity.ok(Map.of("data", toJson(updated)));
        } catch (ObjectiveNotFoundException e) {
            return notFound(e.getMessage());
        } catch (InvalidOkrException e) {
            return invalid(e.getMessage());
        }
    }

    // =========================================================================
    // DELETE /okr/{objectiveId}
    // =========================================================================
    @DeleteMapping("/okr/{objectiveId}")
    public ResponseEntity<?> softDelete(
            @RequestHeader(value = "X-Enterprise-ID", required = false) String enterpriseHeader,
            @RequestHeader(value = "X-User-Role",     required = false) String actorRole,
            @PathVariable("objectiveId") String objectiveIdStr) {

        UUID enterpriseId = parseUuid(enterpriseHeader);
        if (enterpriseId == null) return missingEnterpriseHeader();
        if (!"MANAGER".equalsIgnoreCase(actorRole)) return forbiddenManagerOnly();

        UUID objectiveId = parseUuid(objectiveIdStr);
        if (objectiveId == null) return invalidUuid("objective_id must be a valid UUID");

        try {
            okrService.softDelete(enterpriseId, objectiveId);
            return ResponseEntity.ok(Map.of("data", Map.of(
                    "objective_id", objectiveId.toString(),
                    "status",       "deleted"
            )));
        } catch (ObjectiveNotFoundException e) {
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
                "Only MANAGER can manage OKR objectives");
    }

    private static ResponseEntity<Map<String, Object>> invalid(String msg) {
        return problem(400, "/docs/errors/invalid-request", "Invalid request", msg);
    }

    private static ResponseEntity<Map<String, Object>> invalidUuid(String msg) {
        return problem(400, "/docs/errors/invalid-id", "Invalid id", msg);
    }

    private static ResponseEntity<Map<String, Object>> notFound(String msg) {
        return problem(404, "/docs/errors/objective-not-found", "Objective not found", msg);
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

    private static Map<String, Object> toJson(ObjectiveWithKrs o) {
        Map<String, Object> m = new LinkedHashMap<>();
        ObjectiveRow obj = o.objective();
        m.put("objective_id",    obj.objectiveId());
        m.put("quarter",         obj.quarter());
        m.put("title",           obj.title());
        m.put("owner_user_id",   obj.ownerUserId());
        m.put("status",          obj.status());
        m.put("created_by_user", obj.createdByUser());
        m.put("created_at",      obj.createdAt());
        m.put("updated_at",      obj.updatedAt());
        m.put("key_results",     o.keyResults().stream()
                .map(EnterpriseOkrController::toJson).toList());
        return m;
    }

    private static Map<String, Object> toJson(KeyResultRow k) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("kr_id",         k.krId());
        m.put("title",         k.title());
        m.put("unit",          k.unit());
        m.put("target",        k.target());
        m.put("current_value", k.currentValue());
        m.put("display_order", k.displayOrder());
        return m;
    }

    // =========================================================================
    // Request DTOs (Jackson snake_case)
    // =========================================================================

    @Data
    public static class CreateRequestBody {
        private String  quarter;
        private String  title;
        @JsonProperty("owner_user_id")
        private String  ownerUserId;
        @JsonProperty("key_results")
        private List<KrBody> keyResults;
    }

    @Data
    public static class UpdateRequestBody {
        private String  quarter;
        private String  title;
        @JsonProperty("owner_user_id")
        private String  ownerUserId;
        private String  status;
        @JsonProperty("key_results")
        private List<KrBody> keyResults;
    }

    @Data
    public static class KrBody {
        private String     title;
        private String     unit;
        private BigDecimal target;
        @JsonProperty("current_value")
        private BigDecimal currentValue;

        KrUpsert toUpsert() {
            return new KrUpsert(title, unit, target, currentValue);
        }
    }

    @Data
    public static class KrProgressBody {
        @JsonProperty("current_value")
        private BigDecimal currentValue;
    }
}
