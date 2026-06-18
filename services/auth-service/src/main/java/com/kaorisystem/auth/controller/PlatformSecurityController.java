package com.kaorisystem.auth.controller;

import com.kaorisystem.auth.model.AdminSession;
import com.kaorisystem.auth.service.AdminSecurityService;
import com.kaorisystem.auth.service.AdminSecurityService.AdminNotFoundException;
import com.kaorisystem.auth.service.AdminSecurityService.EnableResult;
import com.kaorisystem.auth.service.AdminSecurityService.InvalidTotpException;
import com.kaorisystem.auth.service.AdminSecurityService.MfaNotInitiatedException;
import com.kaorisystem.auth.service.AdminSecurityService.MfaVerifyLockedException;
import com.kaorisystem.auth.service.AdminSecurityService.RevokeOthersResult;
import com.kaorisystem.auth.service.AdminSecurityService.RevokeResult;
import com.kaorisystem.auth.service.AdminSecurityService.SessionNotFoundException;
import com.kaorisystem.auth.service.AdminSecurityService.VerifyResult;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
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
 * Module 3 — Platform admin security endpoints.
 *
 * <pre>
 *   POST   /api/v1/platform/security/mfa/enable
 *   POST   /api/v1/platform/security/mfa/verify           { code }
 *   GET    /api/v1/platform/security/sessions
 *   DELETE /api/v1/platform/security/sessions/{sessionId}
 * </pre>
 *
 * Identity comes from the trusted-gateway {@code X-User-ID} header. The
 * session revoke endpoint scopes the WHERE clause to (session_id, admin_id)
 * so callers can only kill their own sessions.
 */
@RestController
@RequestMapping("/api/v1/platform/security")
@RequiredArgsConstructor
@Slf4j
public class PlatformSecurityController {

    private final AdminSecurityService securityService;

    // =========================================================================
    // MFA
    // =========================================================================

    @PostMapping("/mfa/enable")
    public ResponseEntity<?> enableMfa(HttpServletRequest http) {
        UUID adminId;
        try {
            adminId = resolveAdminId(http);
        } catch (UnauthorizedException e) {
            return problem(401, "/docs/errors/unauthenticated", "Unauthenticated", e.getMessage());
        }

        try {
            EnableResult r = securityService.enableMfa(adminId, clientIp(http));
            Map<String, Object> data = new LinkedHashMap<>();
            data.put("secret",       r.secret());
            data.put("otpauth_url",  r.otpauthUrl());
            data.put("issuer",       r.issuer());
            data.put("account",      r.account());
            return ResponseEntity.ok(Map.of(
                    "data", data,
                    "meta", Map.of("warning",
                            "Scan the QR code in Google Authenticator and verify a code within 30 seconds.")
            ));
        } catch (AdminNotFoundException e) {
            return problem(404, "/docs/errors/admin-not-found", "Admin not found", e.getMessage());
        }
    }

    @PostMapping("/mfa/verify")
    public ResponseEntity<?> verifyMfa(
            @Valid @RequestBody VerifyMfaRequest req,
            HttpServletRequest http) {

        UUID adminId;
        try {
            adminId = resolveAdminId(http);
        } catch (UnauthorizedException e) {
            return problem(401, "/docs/errors/unauthenticated", "Unauthenticated", e.getMessage());
        }

        try {
            VerifyResult r = securityService.verifyMfa(adminId, req.getCode(), clientIp(http));
            return ResponseEntity.ok(Map.of("data", Map.of(
                    "mfa_enabled", r.mfaEnabled(),
                    "verified_at", r.verifiedAt()
            )));
        } catch (AdminNotFoundException e) {
            return problem(404, "/docs/errors/admin-not-found", "Admin not found", e.getMessage());
        } catch (MfaNotInitiatedException e) {
            return problem(409, "/docs/errors/mfa-not-initiated",
                    "MFA not initiated", e.getMessage());
        } catch (MfaVerifyLockedException e) {
            // RFC 7807 423 — surface remaining seconds so the FE can render
            // "Try again in N min" instead of polling. Mirrors /auth/login's
            // 423 response with the additional `lockout_remaining_seconds` field.
            Map<String, Object> body = new LinkedHashMap<>();
            body.put("type",   "/docs/errors/mfa-verify-locked");
            body.put("title",  "Too many failed attempts");
            body.put("status", 423);
            body.put("detail", e.getMessage());
            body.put("lockout_remaining_seconds", e.getRemainingSeconds());
            return ResponseEntity.status(423).body(body);
        } catch (InvalidTotpException e) {
            return problem(400, "/docs/errors/invalid-code",
                    "Invalid or expired code", e.getMessage());
        }
    }

    // =========================================================================
    // Sessions
    // =========================================================================

    @GetMapping("/sessions")
    public ResponseEntity<?> listSessions(HttpServletRequest http) {
        UUID adminId;
        try {
            adminId = resolveAdminId(http);
        } catch (UnauthorizedException e) {
            return problem(401, "/docs/errors/unauthenticated", "Unauthenticated", e.getMessage());
        }

        try {
            List<AdminSession> sessions = securityService.listActiveSessions(adminId);
            String currentSessionId = http.getHeader("X-Session-Id"); // best-effort; gateway may set this
            List<Map<String, Object>> data = sessions.stream()
                    .map(s -> toSessionJson(s, currentSessionId))
                    .toList();
            return ResponseEntity.ok(Map.of("data", data));
        } catch (AdminNotFoundException e) {
            return problem(404, "/docs/errors/admin-not-found", "Admin not found", e.getMessage());
        }
    }

    /**
     * 3.3 — bulk-revoke every other session for the calling admin. Keeps the
     * caller's current session alive (resolved from {@code X-Session-Id}) so
     * they don't sign themselves out by clicking "Revoke all" on the page
     * they're currently using.
     */
    @PostMapping("/sessions/revoke-others")
    public ResponseEntity<?> revokeOtherSessions(HttpServletRequest http) {
        UUID adminId;
        try {
            adminId = resolveAdminId(http);
        } catch (UnauthorizedException e) {
            return problem(401, "/docs/errors/unauthenticated", "Unauthenticated", e.getMessage());
        }

        UUID currentSessionId = parseSessionIdHeader(http);

        try {
            RevokeOthersResult r = securityService.revokeOtherSessions(
                    adminId, currentSessionId, clientIp(http));
            log.info("platform.session.revoke_others admin_id={} count={}",
                    adminId, r.revokedCount());

            Map<String, Object> data = new LinkedHashMap<>();
            data.put("revoked_count", r.revokedCount());
            data.put("kept_session_id", currentSessionId);
            data.put("revoked_at", r.revokedAt());
            return ResponseEntity.ok(Map.of("data", data));
        } catch (AdminNotFoundException e) {
            return problem(404, "/docs/errors/admin-not-found", "Admin not found", e.getMessage());
        }
    }

    @DeleteMapping("/sessions/{sessionId}")
    public ResponseEntity<?> revokeSession(
            @PathVariable("sessionId") String sessionIdStr,
            HttpServletRequest http) {

        UUID adminId;
        try {
            adminId = resolveAdminId(http);
        } catch (UnauthorizedException e) {
            return problem(401, "/docs/errors/unauthenticated", "Unauthenticated", e.getMessage());
        }

        UUID sessionId;
        try {
            sessionId = UUID.fromString(sessionIdStr);
        } catch (IllegalArgumentException e) {
            return problem(400, "/docs/errors/invalid-id", "Invalid session ID",
                    "session_id must be a valid UUID");
        }

        try {
            RevokeResult r = securityService.revokeSession(adminId, sessionId, clientIp(http));
            String currentSessionId = http.getHeader("X-Session-Id");
            boolean signedOutSelf = currentSessionId != null
                    && currentSessionId.equalsIgnoreCase(sessionId.toString());
            Map<String, Object> data = new LinkedHashMap<>();
            data.put("session_id", r.sessionId());
            data.put("revoked_at", r.revokedAt());
            return ResponseEntity.ok(Map.of(
                    "data", data,
                    "meta", Map.of("signed_out", signedOutSelf)
            ));
        } catch (SessionNotFoundException e) {
            return problem(404, "/docs/errors/session-not-found",
                    "Session not found", e.getMessage());
        } catch (AdminNotFoundException e) {
            return problem(404, "/docs/errors/admin-not-found", "Admin not found", e.getMessage());
        }
    }

    // =========================================================================
    // Helpers
    // =========================================================================

    private static Map<String, Object> toSessionJson(AdminSession s, String currentSessionId) {
        Map<String, Object> j = new LinkedHashMap<>();
        j.put("session_id",     s.getSessionId());
        j.put("ip_address",     s.getIpAddress());
        j.put("user_agent",     s.getUserAgent());
        j.put("device_label",   s.getDeviceLabel());
        j.put("created_at",     s.getCreatedAt());
        j.put("last_active_at", s.getLastActiveAt());
        j.put("is_current",     currentSessionId != null
                && currentSessionId.equalsIgnoreCase(String.valueOf(s.getSessionId())));
        return j;
    }

    /** Same X-Forwarded-For-aware extraction WorkspaceController uses. */
    private static String clientIp(HttpServletRequest req) {
        String forwarded = req.getHeader("X-Forwarded-For");
        if (forwarded != null && !forwarded.isBlank()) {
            int comma = forwarded.indexOf(',');
            return comma > 0 ? forwarded.substring(0, comma).trim() : forwarded.trim();
        }
        return req.getRemoteAddr();
    }

    /**
     * 3.3 — extract the caller's current session id from X-Session-Id (set by
     * the gateway from the JWT). Returns null when absent or malformed —
     * caller treats null as "no current session to keep alive".
     */
    private static UUID parseSessionIdHeader(HttpServletRequest http) {
        String header = http.getHeader("X-Session-Id");
        if (header == null || header.isBlank()) return null;
        try { return UUID.fromString(header.trim()); }
        catch (IllegalArgumentException e) { return null; }
    }

    private static UUID resolveAdminId(HttpServletRequest http) {
        String header = http.getHeader("X-User-ID");
        if (header == null || header.isBlank()) {
            throw new UnauthorizedException("X-User-ID header missing");
        }
        try {
            return UUID.fromString(header.trim());
        } catch (IllegalArgumentException e) {
            throw new UnauthorizedException("X-User-ID is not a valid UUID");
        }
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

    private static class UnauthorizedException extends RuntimeException {
        UnauthorizedException(String msg) { super(msg); }
    }

    // =========================================================================
    // Request DTOs
    // =========================================================================

    @Data
    public static class VerifyMfaRequest {
        @NotBlank
        @Pattern(regexp = "^\\d{6}$", message = "code must be exactly 6 digits")
        private String code;
    }
}
