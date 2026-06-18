package com.kaorisystem.auth.controller;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.kaorisystem.auth.model.WorkspaceKey;
import com.kaorisystem.auth.service.PlatformKeyService.GeneratedKey;
import com.kaorisystem.auth.service.PlatformKeyService.KeyNotFoundException;
import com.kaorisystem.auth.service.PlatformKeyService.RateLimitException;
import com.kaorisystem.auth.service.WorkspaceKeyService;
import com.kaorisystem.auth.service.WorkspaceKeyService.RevokedKey;
import com.kaorisystem.auth.service.WorkspaceMemberService;
import com.kaorisystem.auth.service.WorkspaceMemberService.InvalidEmailException;
import com.kaorisystem.auth.service.WorkspaceMemberService.InvalidRoleException;
import com.kaorisystem.auth.service.WorkspaceMemberService.LastManagerException;
import com.kaorisystem.auth.service.WorkspaceMemberService.MemberAlreadyExistsException;
import com.kaorisystem.auth.service.WorkspaceMemberService.MemberNotFoundException;
import com.kaorisystem.auth.service.WorkspaceMemberService.MemberView;
import com.kaorisystem.auth.service.WorkspaceService;
import com.kaorisystem.auth.service.WorkspaceService.AuditPage;
import com.kaorisystem.auth.service.WorkspaceService.AuditView;
import com.kaorisystem.auth.service.WorkspaceService.BillingSummary;
import com.kaorisystem.auth.service.WorkspaceService.EnterpriseNotProvisionedException;
import com.kaorisystem.auth.service.WorkspaceService.InvalidCursorException;
import com.kaorisystem.auth.service.WorkspaceService.InvalidPlanCodeException;
import com.kaorisystem.auth.service.WorkspaceService.WorkspaceNotFoundException;
import com.kaorisystem.auth.service.WorkspaceService.WorkspacePage;
import com.kaorisystem.auth.service.WorkspaceService.WorkspaceView;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * F-008 — Workspace Management CRUD (Platform portal P1).
 *
 * Security: SUPER_ADMIN / ADMIN only. Enforced at api-gateway JWT filter
 * before the request reaches this service (consistent with PlatformController).
 *
 * API contract (per phase_1_execution.md):
 *   GET    /api/v1/platform/workspaces?cursor=&limit=
 *   POST   /api/v1/platform/workspaces
 *   PATCH  /api/v1/platform/workspaces/{id}
 *   DELETE /api/v1/platform/workspaces/{id}   (soft delete → status='inactive')
 *
 * Envelope: { data, meta } on success; RFC 7807 Problem Details on error (K-14).
 */
@RestController
@RequestMapping("/api/v1/platform/workspaces")
@RequiredArgsConstructor
@Slf4j
public class WorkspaceController {

    private static final int DEFAULT_LIMIT = 50;
    private static final int MAX_LIMIT     = 500;

    private final WorkspaceService       workspaceService;
    private final WorkspaceMemberService memberService;
    private final WorkspaceKeyService    keyService;

    // =========================================================================
    // GET /api/v1/platform/workspaces?cursor=&limit=
    // =========================================================================
    @GetMapping
    public ResponseEntity<?> list(
            @RequestParam(value = "cursor", required = false) String cursor,
            @RequestParam(value = "limit",  required = false) Integer limit) {

        int effectiveLimit = (limit == null) ? DEFAULT_LIMIT : limit;
        if (effectiveLimit < 1 || effectiveLimit > MAX_LIMIT) {
            return problem(400, "/docs/errors/invalid-request", "Invalid limit",
                    "limit must be between 1 and " + MAX_LIMIT);
        }

        WorkspacePage page;
        try {
            page = workspaceService.list(cursor, effectiveLimit);
        } catch (InvalidCursorException e) {
            return problem(400, "/docs/errors/invalid-cursor", "Invalid cursor", e.getMessage());
        }

        Map<String, Object> meta = new LinkedHashMap<>();
        meta.put("cursor", page.nextCursor());
        meta.put("total",  page.total());

        return ResponseEntity.ok(Map.of(
                "data", page.items().stream().map(WorkspaceController::toJson).toList(),
                "meta", meta
        ));
    }

    // =========================================================================
    // GET /api/v1/platform/workspaces/{id}
    // =========================================================================
    @GetMapping("/{id}")
    public ResponseEntity<?> get(@PathVariable("id") String idStr) {
        UUID id = parseUuidOrThrow(idStr);
        try {
            return ResponseEntity.ok(Map.of("data", toJson(workspaceService.get(id))));
        } catch (WorkspaceNotFoundException e) {
            return problem(404, "/docs/errors/workspace-not-found", "Workspace not found", e.getMessage());
        }
    }

    // =========================================================================
    // POST /api/v1/platform/workspaces
    // =========================================================================
    @PostMapping
    public ResponseEntity<?> create(@Valid @RequestBody CreateWorkspaceRequest req) {
        WorkspaceView created;
        try {
            created = workspaceService.create(
                    req.getName().trim(),
                    req.getPlanCode().trim().toUpperCase(),
                    req.getIndustry() == null ? null : req.getIndustry().trim()
            );
        } catch (InvalidPlanCodeException e) {
            return problem(400, "/docs/errors/invalid-plan-code", "Invalid plan_code", e.getMessage());
        }

        log.info("platform.workspace.created workspace_id={} plan={}",
                created.workspaceId(), created.planCode());

        return ResponseEntity.status(HttpStatus.CREATED).body(Map.of("data", toJson(created)));
    }

    // =========================================================================
    // PATCH /api/v1/platform/workspaces/{id}
    // =========================================================================
    @PatchMapping("/{id}")
    public ResponseEntity<?> update(
            @PathVariable("id") String idStr,
            @Valid @RequestBody UpdateWorkspaceRequest req) {

        UUID id;
        try {
            id = UUID.fromString(idStr);
        } catch (IllegalArgumentException e) {
            return problem(400, "/docs/errors/invalid-id", "Invalid workspace ID",
                    "workspace_id must be a valid UUID");
        }

        if (req.isEmpty()) {
            return problem(400, "/docs/errors/invalid-request", "Empty update",
                    "At least one of name, plan_code, or status must be provided");
        }

        try {
            WorkspaceView updated = workspaceService.update(
                    id,
                    req.getName()     == null ? null : req.getName().trim(),
                    req.getPlanCode() == null ? null : req.getPlanCode().trim().toUpperCase(),
                    req.getStatus()   == null ? null : req.getStatus().trim().toLowerCase()
            );
            log.info("platform.workspace.updated workspace_id={}", id);
            return ResponseEntity.ok(Map.of("data", toJson(updated)));
        } catch (WorkspaceNotFoundException e) {
            return problem(404, "/docs/errors/workspace-not-found", "Workspace not found", e.getMessage());
        } catch (InvalidPlanCodeException e) {
            return problem(400, "/docs/errors/invalid-plan-code", "Invalid plan_code", e.getMessage());
        }
    }

    // =========================================================================
    // DELETE /api/v1/platform/workspaces/{id}   (soft delete → status='inactive')
    // =========================================================================
    @DeleteMapping("/{id}")
    public ResponseEntity<?> softDelete(@PathVariable("id") String idStr) {
        UUID id;
        try {
            id = UUID.fromString(idStr);
        } catch (IllegalArgumentException e) {
            return problem(400, "/docs/errors/invalid-id", "Invalid workspace ID",
                    "workspace_id must be a valid UUID");
        }

        try {
            WorkspaceView deactivated = workspaceService.softDelete(id);
            log.info("platform.workspace.deactivated workspace_id={}", id);
            return ResponseEntity.ok(Map.of("data", Map.of(
                    "workspace_id", deactivated.workspaceId(),
                    "status",       deactivated.status()
            )));
        } catch (WorkspaceNotFoundException e) {
            return problem(404, "/docs/errors/workspace-not-found", "Workspace not found", e.getMessage());
        }
    }

    // =========================================================================
    // Members — F-008 expansion
    //   GET    /workspaces/{id}/members
    //   POST   /workspaces/{id}/members              { email, role }
    //   PATCH  /workspaces/{id}/members/{userId}    { role }
    //   DELETE /workspaces/{id}/members/{userId}
    // =========================================================================

    @GetMapping("/{id}/members")
    public ResponseEntity<?> listMembers(@PathVariable("id") String idStr) {
        UUID id = parseUuidOrThrow(idStr);
        try {
            List<MemberView> members = memberService.list(id);
            return ResponseEntity.ok(Map.of(
                    "data", members.stream().map(WorkspaceController::toMemberJson).toList()
            ));
        } catch (WorkspaceNotFoundException e) {
            return problem(404, "/docs/errors/workspace-not-found", "Workspace not found", e.getMessage());
        }
    }

    @PostMapping("/{id}/members")
    public ResponseEntity<?> inviteMember(
            @PathVariable("id") String idStr,
            @Valid @RequestBody InviteMemberRequest req,
            HttpServletRequest http) {

        UUID id = parseUuidOrThrow(idStr);
        try {
            MemberView m = memberService.invite(
                    id, req.getEmail(), req.getRole(),
                    actorEmail(http), actorRole(http), clientIp(http));
            return ResponseEntity.status(HttpStatus.CREATED).body(Map.of("data", toMemberJson(m)));
        } catch (WorkspaceNotFoundException e) {
            return problem(404, "/docs/errors/workspace-not-found", "Workspace not found", e.getMessage());
        } catch (EnterpriseNotProvisionedException e) {
            return problem(409, "/docs/errors/enterprise-not-provisioned",
                    "Enterprise not provisioned", e.getMessage());
        } catch (MemberAlreadyExistsException e) {
            return problem(409, "/docs/errors/member-already-exists",
                    "Member already exists", e.getMessage());
        } catch (InvalidRoleException | InvalidEmailException e) {
            return problem(400, "/docs/errors/invalid-request", "Invalid request", e.getMessage());
        }
    }

    @PatchMapping("/{id}/members/{userId}")
    public ResponseEntity<?> updateMember(
            @PathVariable("id")     String idStr,
            @PathVariable("userId") String userIdStr,
            @Valid @RequestBody UpdateMemberRequest req,
            HttpServletRequest http) {

        UUID id     = parseUuidOrThrow(idStr);
        UUID userId = parseUuidOrThrow(userIdStr);
        try {
            MemberView m = memberService.updateRole(
                    id, userId, req.getRole(),
                    actorEmail(http), actorRole(http), clientIp(http));
            return ResponseEntity.ok(Map.of("data", toMemberJson(m)));
        } catch (MemberNotFoundException e) {
            return problem(404, "/docs/errors/member-not-found", "Member not found", e.getMessage());
        } catch (LastManagerException e) {
            return problem(409, "/docs/errors/last-manager",
                    "Cannot demote last manager", e.getMessage());
        } catch (InvalidRoleException e) {
            return problem(400, "/docs/errors/invalid-request", "Invalid request", e.getMessage());
        } catch (EnterpriseNotProvisionedException e) {
            return problem(409, "/docs/errors/enterprise-not-provisioned",
                    "Enterprise not provisioned", e.getMessage());
        }
    }

    @DeleteMapping("/{id}/members/{userId}")
    public ResponseEntity<?> removeMember(
            @PathVariable("id")     String idStr,
            @PathVariable("userId") String userIdStr,
            HttpServletRequest http) {

        UUID id     = parseUuidOrThrow(idStr);
        UUID userId = parseUuidOrThrow(userIdStr);
        try {
            memberService.remove(id, userId,
                    actorEmail(http), actorRole(http), clientIp(http));
            return ResponseEntity.ok(Map.of("data", Map.of("user_id", userId)));
        } catch (MemberNotFoundException e) {
            return problem(404, "/docs/errors/member-not-found", "Member not found", e.getMessage());
        } catch (LastManagerException e) {
            return problem(409, "/docs/errors/last-manager",
                    "Cannot remove last manager", e.getMessage());
        } catch (EnterpriseNotProvisionedException e) {
            return problem(409, "/docs/errors/enterprise-not-provisioned",
                    "Enterprise not provisioned", e.getMessage());
        }
    }

    // =========================================================================
    // Billing — F-008 expansion
    //   GET /workspaces/{id}/billing
    // =========================================================================
    @GetMapping("/{id}/billing")
    public ResponseEntity<?> getBilling(@PathVariable("id") String idStr) {
        UUID id = parseUuidOrThrow(idStr);
        try {
            BillingSummary b = workspaceService.getBillingSummary(id);
            return ResponseEntity.ok(Map.of("data", toBillingJson(b)));
        } catch (WorkspaceNotFoundException e) {
            return problem(404, "/docs/errors/workspace-not-found", "Workspace not found", e.getMessage());
        } catch (EnterpriseNotProvisionedException e) {
            return problem(409, "/docs/errors/enterprise-not-provisioned",
                    "Enterprise not provisioned", e.getMessage());
        }
    }

    // =========================================================================
    // Audit — F-008 expansion
    //   GET /workspaces/{id}/audit?cursor=&limit=
    // =========================================================================
    @GetMapping("/{id}/audit")
    public ResponseEntity<?> listAudit(
            @PathVariable("id") String idStr,
            @RequestParam(value = "cursor", required = false) String cursor,
            @RequestParam(value = "limit",  required = false) Integer limit) {

        UUID id = parseUuidOrThrow(idStr);

        int effectiveLimit = (limit == null) ? DEFAULT_LIMIT : limit;
        if (effectiveLimit < 1 || effectiveLimit > MAX_LIMIT) {
            return problem(400, "/docs/errors/invalid-request", "Invalid limit",
                    "limit must be between 1 and " + MAX_LIMIT);
        }

        try {
            AuditPage page = workspaceService.listAudit(id, cursor, effectiveLimit);
            Map<String, Object> meta = new LinkedHashMap<>();
            meta.put("cursor", page.nextCursor());
            meta.put("total",  page.total());
            return ResponseEntity.ok(Map.of(
                    "data", page.items().stream().map(WorkspaceController::toAuditJson).toList(),
                    "meta", meta
            ));
        } catch (WorkspaceNotFoundException e) {
            return problem(404, "/docs/errors/workspace-not-found", "Workspace not found", e.getMessage());
        } catch (InvalidCursorException e) {
            return problem(400, "/docs/errors/invalid-cursor", "Invalid cursor", e.getMessage());
        }
    }

    // =========================================================================
    // Keys — F-009 (additive, nested deepening pattern)
    //   GET    /workspaces/{id}/keys
    //   POST   /workspaces/{id}/keys              { label? }
    //   DELETE /workspaces/{id}/keys/{keyId}
    //
    // Reuses PlatformKeyService for hashing + rate-limiting; the flat
    // /api/v1/platform/keys routes in PlatformController remain unchanged
    // and keep serving AuthService.activateWorkspace().
    // =========================================================================

    @GetMapping("/{id}/keys")
    public ResponseEntity<?> listKeys(@PathVariable("id") String idStr) {
        UUID id = parseUuidOrThrow(idStr);
        try {
            List<WorkspaceKey> keys = keyService.list(id);
            return ResponseEntity.ok(Map.of(
                    "data", keys.stream().map(WorkspaceController::toKeyJson).toList()
            ));
        } catch (WorkspaceNotFoundException e) {
            return problem(404, "/docs/errors/workspace-not-found", "Workspace not found", e.getMessage());
        }
    }

    @PostMapping("/{id}/keys")
    public ResponseEntity<?> generateKey(
            @PathVariable("id") String idStr,
            @Valid @RequestBody(required = false) GenerateKeyRequest req,
            HttpServletRequest http) {

        UUID id = parseUuidOrThrow(idStr);
        String label = (req == null || req.getLabel() == null) ? null : req.getLabel().trim();
        if (label != null && label.isEmpty()) label = null;

        try {
            GeneratedKey result = keyService.generate(
                    id, label, actorEmail(http), actorRole(http), clientIp(http));

            log.info("platform.key.generated workspace_id={} label={}", id, label);

            Map<String, Object> data = new LinkedHashMap<>();
            data.put("key_id",     result.keyId());
            data.put("raw_key",    result.rawKey());
            data.put("label",      result.label() == null ? "" : result.label());
            data.put("status",     "active");
            data.put("created_at", result.createdAt());
            data.put("revoked_at", null);

            return ResponseEntity.status(HttpStatus.CREATED).body(Map.of(
                    "data", data,
                    "meta", Map.of("warning",
                            "Store this key immediately. It will not be shown again.")
            ));
        } catch (WorkspaceNotFoundException e) {
            return problem(404, "/docs/errors/workspace-not-found", "Workspace not found", e.getMessage());
        } catch (RateLimitException e) {
            return problem(429, "/docs/errors/rate-limit-exceeded", "Rate limit exceeded", e.getMessage());
        }
    }

    @DeleteMapping("/{id}/keys/{keyId}")
    public ResponseEntity<?> revokeKey(
            @PathVariable("id")    String idStr,
            @PathVariable("keyId") String keyIdStr,
            HttpServletRequest http) {

        UUID id    = parseUuidOrThrow(idStr);
        UUID keyId = parseUuidOrThrow(keyIdStr);

        try {
            RevokedKey r = keyService.revoke(
                    id, keyId, actorEmail(http), actorRole(http), clientIp(http));
            log.info("platform.key.revoked workspace_id={} key_id={}", id, keyId);

            Map<String, Object> data = new LinkedHashMap<>();
            data.put("key_id",     r.keyId());
            data.put("status",     "revoked");
            data.put("revoked_at", r.revokedAt());
            return ResponseEntity.ok(Map.of("data", data));
        } catch (WorkspaceNotFoundException e) {
            return problem(404, "/docs/errors/workspace-not-found", "Workspace not found", e.getMessage());
        } catch (KeyNotFoundException e) {
            return problem(404, "/docs/errors/key-not-found", "Key not found", e.getMessage());
        }
    }

    // =========================================================================
    // Helpers
    // =========================================================================

    private static Map<String, Object> toJson(WorkspaceView w) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("workspace_id", w.workspaceId());
        m.put("name",         w.name());
        m.put("plan_code",    w.planCode());
        m.put("industry",     w.industry() == null ? "" : w.industry());
        m.put("status",       w.status());
        m.put("created_at",   w.createdAt());
        m.put("updated_at",   w.updatedAt());
        return m;
    }

    private static ResponseEntity<Map<String, Object>> problem(
            int status, String type, String title, String detail) {
        return ResponseEntity.status(status).body(Map.of(
                "type",   type,
                "title",  title,
                "status", status,
                "detail", detail
        ));
    }

    private static UUID parseUuidOrThrow(String s) {
        try { return UUID.fromString(s); }
        catch (IllegalArgumentException e) {
            throw new InvalidIdException("Invalid UUID: " + s);
        }
    }

    private static Map<String, Object> toMemberJson(MemberView m) {
        Map<String, Object> j = new LinkedHashMap<>();
        j.put("user_id",       m.userId());
        j.put("email",         m.email());
        j.put("full_name",     m.fullName());
        j.put("role",          m.role());
        j.put("status",        m.status());
        j.put("last_login_at", m.lastLoginAt());
        j.put("created_at",    m.createdAt());
        return j;
    }

    private static Map<String, Object> toBillingJson(BillingSummary b) {
        Map<String, Object> j = new LinkedHashMap<>();
        j.put("workspace_id",       b.workspaceId());
        j.put("plan_code",          b.planCode());
        j.put("billing_month",      b.billingMonth());
        j.put("unique_customers",   b.uniqueCustomers());
        j.put("quota",              b.quota());
        j.put("overage_units",      b.overageUnits());
        j.put("base_amount_vnd",    b.baseAmountVnd());
        j.put("overage_amount_vnd", b.overageAmountVnd());
        j.put("total_amount_vnd",   b.totalAmountVnd());
        j.put("quota_warn_at_pct",  b.quotaWarnAtPct());
        j.put("status",             b.status());
        j.put("next_invoice_date",  b.nextInvoiceDate() == null ? null : b.nextInvoiceDate().toString());
        return j;
    }

    private static Map<String, Object> toKeyJson(WorkspaceKey k) {
        Map<String, Object> j = new LinkedHashMap<>();
        j.put("key_id",     k.getKeyId());
        j.put("label",      k.getLabel() == null ? "" : k.getLabel());
        j.put("status",     k.isActive() ? "active" : "revoked");
        j.put("created_at", k.getCreatedAt());
        j.put("revoked_at", k.getRevokedAt());
        return j;
    }

    private static Map<String, Object> toAuditJson(AuditView ev) {
        Map<String, Object> j = new LinkedHashMap<>();
        j.put("event_id",   ev.eventId());
        j.put("event_type", ev.eventType());
        j.put("actor_email", ev.actorEmail());
        j.put("actor_role",  ev.actorRole());
        j.put("resource",    ev.resource());
        j.put("detail",      ev.detail());
        j.put("ip_address",  ev.ipAddress());
        j.put("created_at",  ev.createdAt());
        return j;
    }

    /** Trusted gateway forwards user identity headers; nullable in dev / direct hits. */
    private static String actorEmail(HttpServletRequest req) {
        String h = req.getHeader("X-User-Email");
        return (h == null || h.isBlank()) ? null : h;
    }
    private static String actorRole(HttpServletRequest req) {
        String h = req.getHeader("X-User-Role");
        return (h == null || h.isBlank()) ? null : h;
    }
    private static String clientIp(HttpServletRequest req) {
        String forwarded = req.getHeader("X-Forwarded-For");
        if (forwarded != null && !forwarded.isBlank()) {
            int comma = forwarded.indexOf(',');
            return comma > 0 ? forwarded.substring(0, comma).trim() : forwarded.trim();
        }
        return req.getRemoteAddr();
    }

    public static class InvalidIdException extends RuntimeException {
        public InvalidIdException(String msg) { super(msg); }
    }

    @ExceptionHandler(InvalidIdException.class)
    public ResponseEntity<Map<String, Object>> handleInvalidId(InvalidIdException e) {
        return problem(400, "/docs/errors/invalid-id", "Invalid ID", e.getMessage());
    }

    // =========================================================================
    // Request DTOs
    // =========================================================================

    @Data
    public static class CreateWorkspaceRequest {
        @jakarta.validation.constraints.NotBlank
        @Size(min = 2, max = 200)
        private String name;

        @jakarta.validation.constraints.NotBlank
        @Size(max = 20)
        @Pattern(regexp = "^[A-Za-z0-9_-]{2,20}$",
                 message = "plan_code must be 2-20 alphanumeric characters (hyphen/underscore allowed)")
        @JsonProperty("plan_code")
        private String planCode;

        @Size(max = 100)
        private String industry;
    }

    @Data
    public static class UpdateWorkspaceRequest {
        @Size(min = 2, max = 200)
        private String name;

        @Size(max = 20)
        @Pattern(regexp = "^[A-Za-z0-9_-]{2,20}$",
                 message = "plan_code must be 2-20 alphanumeric characters (hyphen/underscore allowed)")
        @JsonProperty("plan_code")
        private String planCode;

        @Pattern(regexp = "^(active|inactive|suspended)$",
                 message = "status must be one of: active, inactive, suspended")
        private String status;

        public boolean isEmpty() {
            return name == null && planCode == null && status == null;
        }
    }

    @Data
    public static class InviteMemberRequest {
        @NotBlank
        private String email;

        @NotBlank
        @Pattern(regexp = "^(MANAGER|OPERATOR|ANALYST|VIEWER)$",
                 message = "role must be one of: MANAGER, OPERATOR, ANALYST, VIEWER")
        private String role;
    }

    @Data
    public static class UpdateMemberRequest {
        @NotBlank
        @Pattern(regexp = "^(MANAGER|OPERATOR|ANALYST|VIEWER)$",
                 message = "role must be one of: MANAGER, OPERATOR, ANALYST, VIEWER")
        private String role;
    }

    @Data
    public static class GenerateKeyRequest {
        @Size(max = 100, message = "label must be 100 characters or fewer")
        private String label;
    }

}
