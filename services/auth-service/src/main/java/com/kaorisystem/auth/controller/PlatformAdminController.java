package com.kaorisystem.auth.controller;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.kaorisystem.auth.service.PlatformAdminService;
import com.kaorisystem.auth.service.PlatformAdminService.AdminAlreadyExistsException;
import com.kaorisystem.auth.service.PlatformAdminService.AdminNotFoundException;
import com.kaorisystem.auth.service.PlatformAdminService.AdminView;
import com.kaorisystem.auth.service.PlatformAdminService.InvalidEmailException;
import com.kaorisystem.auth.service.PlatformAdminService.InvalidFullNameException;
import com.kaorisystem.auth.service.PlatformAdminService.InvalidRoleException;
import com.kaorisystem.auth.service.PlatformAdminService.ResetResult;
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
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * F-010 — Platform admin user management (P1 portal).
 *
 * Security: SUPER_ADMIN / ADMIN only — enforced at api-gateway JWT filter
 * (consistent with WorkspaceController + PlatformController).
 *
 * Contract:
 *   GET    /api/v1/platform/admins
 *   GET    /api/v1/platform/admins/{id}
 *   POST   /api/v1/platform/admins                     { email, full_name, role }
 *   PATCH  /api/v1/platform/admins/{id}                { full_name?, role?, is_active? }
 *   POST   /api/v1/platform/admins/{id}/reset-password
 *
 * Envelope: { data, meta? } on success; RFC 7807 Problem Details on error (K-14).
 */
@RestController
@RequestMapping("/api/v1/platform/admins")
@RequiredArgsConstructor
@Slf4j
public class PlatformAdminController {

    private final PlatformAdminService adminService;

    @GetMapping
    public ResponseEntity<?> list() {
        List<AdminView> admins = adminService.list();
        return ResponseEntity.ok(Map.of(
                "data", admins.stream().map(PlatformAdminController::toJson).toList()
        ));
    }

    @GetMapping("/{id}")
    public ResponseEntity<?> get(@PathVariable("id") String idStr) {
        UUID id = parseUuidOrThrow(idStr);
        return ResponseEntity.ok(Map.of("data", toJson(adminService.get(id))));
    }

    @PostMapping
    public ResponseEntity<?> invite(
            @Valid @RequestBody InviteAdminRequest req,
            HttpServletRequest http) {

        UUID invitedBy = parseUuidOrNull(http.getHeader("X-User-Id"));
        AdminView created = adminService.invite(
                req.getEmail(), req.getFullName(), req.getRole(), invitedBy);
        log.info("platform.admin.invited admin_id={} role={} by={}",
                created.adminId(), created.role(), invitedBy);
        return ResponseEntity.status(HttpStatus.CREATED).body(Map.of("data", toJson(created)));
    }

    @PatchMapping("/{id}")
    public ResponseEntity<?> update(
            @PathVariable("id") String idStr,
            @Valid @RequestBody UpdateAdminRequest req) {

        UUID id = parseUuidOrThrow(idStr);
        if (req.isEmpty()) {
            return problem(400, "/docs/errors/invalid-request", "Empty update",
                    "At least one of full_name, role, or is_active must be provided");
        }
        AdminView updated = adminService.update(id, req.getFullName(), req.getRole(), req.getIsActive());
        log.info("platform.admin.updated admin_id={}", id);
        return ResponseEntity.ok(Map.of("data", toJson(updated)));
    }

    @PostMapping("/{id}/reset-password")
    public ResponseEntity<?> resetPassword(@PathVariable("id") String idStr) {
        UUID id = parseUuidOrThrow(idStr);
        ResetResult r = adminService.resetPassword(id);
        log.info("platform.admin.password_reset_requested admin_id={}", id);
        return ResponseEntity.ok(Map.of("data", Map.of(
                "id",                  r.adminId(),
                "reset_token_sent_to", r.emailSentTo()
        )));
    }

    // =========================================================================
    // Exception handlers
    // =========================================================================

    @ExceptionHandler(AdminNotFoundException.class)
    public ResponseEntity<Map<String, Object>> handleNotFound(AdminNotFoundException e) {
        return problem(404, "/docs/errors/admin-not-found", "Platform admin not found", e.getMessage());
    }

    @ExceptionHandler(AdminAlreadyExistsException.class)
    public ResponseEntity<Map<String, Object>> handleConflict(AdminAlreadyExistsException e) {
        return problem(409, "/docs/errors/admin-already-exists",
                "Platform admin already exists", e.getMessage());
    }

    @ExceptionHandler({InvalidEmailException.class, InvalidRoleException.class, InvalidFullNameException.class})
    public ResponseEntity<Map<String, Object>> handleBadInput(RuntimeException e) {
        return problem(400, "/docs/errors/invalid-request", "Invalid request", e.getMessage());
    }

    @ExceptionHandler(InvalidIdException.class)
    public ResponseEntity<Map<String, Object>> handleInvalidId(InvalidIdException e) {
        return problem(400, "/docs/errors/invalid-id", "Invalid ID", e.getMessage());
    }

    // =========================================================================
    // Helpers
    // =========================================================================

    private static Map<String, Object> toJson(AdminView a) {
        Map<String, Object> j = new LinkedHashMap<>();
        j.put("id",            a.adminId());
        j.put("email",         a.email());
        j.put("full_name",     a.fullName());
        j.put("role",          a.role());
        j.put("is_active",     a.isActive());
        j.put("mfa_enabled",   a.mfaEnabled());
        j.put("last_login_at", a.lastLoginAt());
        j.put("created_at",    a.createdAt());
        return j;
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

    private static UUID parseUuidOrNull(String s) {
        if (s == null || s.isBlank()) return null;
        try { return UUID.fromString(s); }
        catch (IllegalArgumentException e) { return null; }
    }

    public static class InvalidIdException extends RuntimeException {
        public InvalidIdException(String msg) { super(msg); }
    }

    // =========================================================================
    // Request DTOs
    // =========================================================================

    @Data
    public static class InviteAdminRequest {
        @NotBlank
        @Size(max = 254)
        private String email;

        @NotBlank
        @JsonProperty("full_name")
        @Size(min = 1, max = 200)
        private String fullName;

        @NotBlank
        @Pattern(regexp = "^(SUPER_ADMIN|ADMIN|SUPPORT)$",
                 message = "role must be one of: SUPER_ADMIN, ADMIN, SUPPORT")
        private String role;
    }

    @Data
    public static class UpdateAdminRequest {
        @JsonProperty("full_name")
        @Size(min = 1, max = 200)
        private String fullName;

        @Pattern(regexp = "^(SUPER_ADMIN|ADMIN|SUPPORT)$",
                 message = "role must be one of: SUPER_ADMIN, ADMIN, SUPPORT")
        private String role;

        @JsonProperty("is_active")
        private Boolean isActive;

        public boolean isEmpty() {
            return fullName == null && role == null && isActive == null;
        }
    }
}
