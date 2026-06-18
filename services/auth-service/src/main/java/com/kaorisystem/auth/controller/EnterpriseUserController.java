package com.kaorisystem.auth.controller;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.kaorisystem.auth.service.EnterpriseUserService;
import com.kaorisystem.auth.service.EnterpriseUserService.EmptyUpdateException;
import com.kaorisystem.auth.service.EnterpriseUserService.InvalidEmailException;
import com.kaorisystem.auth.service.EnterpriseUserService.InvalidRoleException;
import com.kaorisystem.auth.service.EnterpriseUserService.InvalidStatusException;
import com.kaorisystem.auth.service.EnterpriseUserService.LastManagerException;
import com.kaorisystem.auth.service.EnterpriseUserService.UserAlreadyExistsException;
import com.kaorisystem.auth.service.EnterpriseUserService.UserNotFoundException;
import com.kaorisystem.auth.service.EnterpriseUserService.UserPage;
import com.kaorisystem.auth.service.EnterpriseUserService.UserView;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
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

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

/**
 * F-015 — Enterprise User & Role Management.
 *
 * <pre>
 *   GET    /api/v1/enterprises/users?page=&limit=&role=&status=   any enterprise role
 *   POST   /api/v1/enterprises/users                              MANAGER only
 *   PATCH  /api/v1/enterprises/users/{userId}                     MANAGER only
 *   DELETE /api/v1/enterprises/users/{userId}                     MANAGER only
 * </pre>
 *
 * <p>tenant_id is taken from the gateway-trusted {@code X-Enterprise-ID}
 * header — never from a query string or request body (K-12). Min-MANAGER
 * invariant enforced in the service layer (see {@link EnterpriseUserService}).
 */
@RestController
@RequestMapping("/api/v1/enterprises/users")
@RequiredArgsConstructor
@Slf4j
public class EnterpriseUserController {

    private final EnterpriseUserService userService;

    // =========================================================================
    // GET /api/v1/enterprises/users
    // =========================================================================
    @GetMapping
    public ResponseEntity<?> list(
            @RequestHeader(value = "X-Enterprise-ID", required = false) String enterpriseHeader,
            @RequestParam(value = "page",   required = false, defaultValue = "1") int page,
            @RequestParam(value = "limit",  required = false, defaultValue = "20") int limit,
            @RequestParam(value = "role",   required = false) String role,
            @RequestParam(value = "status", required = false) String status) {

        UUID enterpriseId = parseEnterpriseHeader(enterpriseHeader);
        if (enterpriseId == null) return missingEnterpriseHeader();

        try {
            UserPage p = userService.list(enterpriseId, role, status, page, limit);

            Map<String, Object> meta = new LinkedHashMap<>();
            meta.put("total", p.total());
            meta.put("page",  p.page());
            meta.put("limit", p.limit());
            return ResponseEntity.ok(Map.of(
                    "data", p.items().stream().map(EnterpriseUserController::toJson).toList(),
                    "meta", meta
            ));
        } catch (InvalidRoleException e) {
            return problem(400, "/docs/errors/invalid-role", "Invalid role", e.getMessage());
        }
    }

    // =========================================================================
    // POST /api/v1/enterprises/users
    // =========================================================================
    @PostMapping
    public ResponseEntity<?> invite(
            @RequestHeader(value = "X-Enterprise-ID", required = false) String enterpriseHeader,
            @RequestHeader(value = "X-User-Role",     required = false) String actorRole,
            @Valid @RequestBody InviteRequest body) {

        UUID enterpriseId = parseEnterpriseHeader(enterpriseHeader);
        if (enterpriseId == null) return missingEnterpriseHeader();
        if (!"MANAGER".equalsIgnoreCase(actorRole)) return forbiddenManagerOnly();

        try {
            UserView created = userService.invite(
                    enterpriseId, body.getEmail(),
                    body.getFullName(), body.getRole());
            return ResponseEntity.status(HttpStatus.CREATED).body(Map.of("data", toJson(created)));
        } catch (UserAlreadyExistsException e) {
            return problem(409, "/docs/errors/user-already-exists",
                    "User already exists", e.getMessage());
        } catch (InvalidRoleException e) {
            return problem(400, "/docs/errors/invalid-role", "Invalid role", e.getMessage());
        } catch (InvalidEmailException e) {
            return problem(400, "/docs/errors/invalid-email", "Invalid email", e.getMessage());
        }
    }

    // =========================================================================
    // PATCH /api/v1/enterprises/users/{userId}
    // =========================================================================
    @PatchMapping("/{userId}")
    public ResponseEntity<?> update(
            @RequestHeader(value = "X-Enterprise-ID", required = false) String enterpriseHeader,
            @RequestHeader(value = "X-User-Role",     required = false) String actorRole,
            @PathVariable("userId") String userIdStr,
            @Valid @RequestBody UpdateRequest body) {

        UUID enterpriseId = parseEnterpriseHeader(enterpriseHeader);
        if (enterpriseId == null) return missingEnterpriseHeader();
        if (!"MANAGER".equalsIgnoreCase(actorRole)) return forbiddenManagerOnly();

        UUID userId = parseUuid(userIdStr);
        if (userId == null) {
            return problem(400, "/docs/errors/invalid-id", "Invalid user ID",
                    "user_id must be a valid UUID");
        }

        try {
            UserView updated = userService.update(
                    enterpriseId, userId, body.getRole(), body.getStatus());
            return ResponseEntity.ok(Map.of("data", toJson(updated)));
        } catch (UserNotFoundException e) {
            return problem(404, "/docs/errors/user-not-found", "User not found", e.getMessage());
        } catch (LastManagerException e) {
            return problem(409, "/docs/errors/last-manager", "Last manager", e.getMessage());
        } catch (InvalidRoleException e) {
            return problem(400, "/docs/errors/invalid-role", "Invalid role", e.getMessage());
        } catch (InvalidStatusException e) {
            return problem(400, "/docs/errors/invalid-status", "Invalid status", e.getMessage());
        } catch (EmptyUpdateException e) {
            return problem(400, "/docs/errors/invalid-request", "Empty update", e.getMessage());
        }
    }

    // =========================================================================
    // DELETE /api/v1/enterprises/users/{userId}  (soft delete → status='deleted')
    // =========================================================================
    @DeleteMapping("/{userId}")
    public ResponseEntity<?> softDelete(
            @RequestHeader(value = "X-Enterprise-ID", required = false) String enterpriseHeader,
            @RequestHeader(value = "X-User-Role",     required = false) String actorRole,
            @PathVariable("userId") String userIdStr) {

        UUID enterpriseId = parseEnterpriseHeader(enterpriseHeader);
        if (enterpriseId == null) return missingEnterpriseHeader();
        if (!"MANAGER".equalsIgnoreCase(actorRole)) return forbiddenManagerOnly();

        UUID userId = parseUuid(userIdStr);
        if (userId == null) {
            return problem(400, "/docs/errors/invalid-id", "Invalid user ID",
                    "user_id must be a valid UUID");
        }

        try {
            userService.softDelete(enterpriseId, userId);
            return ResponseEntity.ok(Map.of("data", Map.of(
                    "user_id", userId.toString(),
                    "status",  "deleted"
            )));
        } catch (UserNotFoundException e) {
            return problem(404, "/docs/errors/user-not-found", "User not found", e.getMessage());
        } catch (LastManagerException e) {
            return problem(409, "/docs/errors/last-manager", "Last manager", e.getMessage());
        }
    }

    // =========================================================================
    // Helpers
    // =========================================================================

    private static UUID parseEnterpriseHeader(String s) {
        return parseUuid(s);
    }

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
        return problem(403, "/docs/errors/forbidden",
                "Forbidden",
                "Only MANAGER can manage enterprise users");
    }

    private static Map<String, Object> toJson(UserView u) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("id",            u.userId());
        m.put("user_id",       u.userId());
        m.put("email",         u.email());
        m.put("full_name",     u.fullName());
        m.put("role",          u.role());
        m.put("status",        u.status());
        m.put("is_active",     "active".equalsIgnoreCase(u.status()));
        m.put("last_login_at", u.lastLoginAt());
        m.put("created_at",    u.createdAt());
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
    // Request DTOs (Jackson snake_case)
    // =========================================================================

    @Data
    public static class InviteRequest {
        @NotBlank
        private String email;

        @JsonProperty("full_name")
        private String fullName;

        @NotBlank
        private String role;
    }

    @Data
    public static class UpdateRequest {
        private String role;
        private String status;
    }
}
